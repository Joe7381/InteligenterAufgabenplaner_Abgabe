from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from openai import OpenAI
from datetime import datetime, timedelta
import re
import os
import uuid
import ast
import threading
from collections import deque
from typing import Optional, List, Dict

from database import SessionLocal, TaskDB
from dependencies import get_current_user_id_optional, limiter
from schemas import ChatRequest, ChatResponse

router = APIRouter()

# --- Configuration & Constants ---
MONTH_MAP = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
}

RESPONDER_SYSTEM_PROMPT = (
    "Du bist ein intelligenter Aufgabenplaner-Assistent. "
    "Deine Aufgabe ist es, Termine zu verwalten und Fragen zu beantworten.\n\n"
    "REGELN:\n"
    "1. WRITE: Wenn der User einen Termin nennt, bestätige ihn.\n"
    "2. SUGGEST/READ (Kalender-Fragen): Nutze IMMER die Daten aus 'SYSTEM-INFO'.\n"
    "   - Fall A (Übersicht): Wenn der User fragt 'Wie sieht meine Woche aus?' oder 'Welche Termine habe ich?', dann LISTE ALLE TERMINE aus SYSTEM-INFO chronologisch auf. \n"
    "     -> WICHTIG: Kein 'zum Beispiel'. Nenne ALLE Termine. Ignoriere hierbei das 2-Satz-Limit.\n"
    "   - Fall B (Freie Zeit): Wenn der User fragt 'Wann habe ich Zeit?', nenne VOR ALLEM die freien Lücken/Tage ('KOMPLETT FREI').\n"
    "     -> ABER: Zur besseren Orientierung, nenne auch kurz die Tage, an denen schon Termine sind (damit der User weiß, warum keine Zeit ist).\n" 
    "     -> Ausgabe-Format: Pro Tag eine Zeile. Sortiere die Ausgabe STRENG CHRONOLOGISCH.\n"
    "   - Fall C (Vorschlag): Wenn der User einen Vorschlag will, nenne IMMER einen konkreten Slot (Tag UND Uhrzeit). Sag nicht nur 'am Donnerstag', sondern z.B. 'am Donnerstag um 18:00 Uhr'. Nutze vorzugsweise 'KI-HINWEIS' (Gewohnheiten), wenn vorhanden.\n"
    "   - ACHTUNG: Die Infos sind nach KALENDERWOCHEN gruppiert. Nenne Termine aus der FALSCHEN Woche NICHT.\n\n"
    "3. FEHLER: Wenn [SYSTEM-ERROR], antworte: 'Fehler beim Speichern: [Fehler]. Bitte versuche es erneut.'\n\n"
    "4. CHAT: Für allgemeine Gespräche antworte kurz (max. 2 Sätze) und freundlich. (Gilt NICHT für Kalender-Listen).\n\n"
    "ABSOLUT KRITISCH:\n"
    "- Antworte AUSSCHLIESSLICH auf Deutsch. Keine Denkprozesse, keine anderen Sprachen.\n"
    "- Keine internen Monologe oder 'Chain of Thought' Ausgaben.\n"
    "- ERFINDE NIEMALS Informationen.\n"
    "- Wenn 'erfolgreich gespeichert' in SYSTEM-INFO, BESTÄTIGE EINFACH.\n"
    "- Wenn 'SYSTEM-INFO: Termin NICHT gespeichert' kommt, MALE KEINE Bestätigung aus. Sag dem User KLIPP UND KLAR: 'Konnte nicht gespeichert werden, weil...'.\n"
    "- Wenn 'SYSTEM-INFO: Termin NICHT gespeichert' kommt, dann hat es NICHT geklappt. Ignoriere deine eigene Annahme, dass du es 'verstanden' hast.\n"
    "- Stelle KEINE Gegenfragen zu gespeicherten Terminen.\n"
)

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.environ.get("LM_STUDIO_API_KEY", "")
LM_STUDIO_MODEL = os.environ.get("LM_STUDIO_MODEL", "local-model")

# --- Global State (Moved from main.py) ---
# In-memory recent chats buffer for debugging
RECENT_CHATS = deque(maxlen=100)
# Simple in-memory conversation store 
CONVERSATIONS = {}
CONVERSATION_TASKS = {}
PENDING_TASKS = {}
CONV_LOCK = threading.Lock()
CONV_PROCESSING_LOCKS = {}
CONV_PROCESSING_LOCKS_LOCK = threading.Lock()


# --- Helper Functions ---

def detect_intent(text: str) -> str:
    text = text.lower()
    write_keywords = [
        "eintragen", "neuer termin", "erinnere mich", "aufgabe", "planen", 
        "hinzufügen", "termin am", "termin um", "notiere", "schreibe auf",
        "kannst du mir", "trag mir", "trage", "trag",
        "ich würde gerne", "ich möchte", "ich will", "brauche einen termin"
    ]
    suggest_keywords = [
        "schlag mir", "schlag vor", "wann passt", "finde einen termin", 
        "wann habe ich zeit", "wann ist platz", "lücke", "frei", "empfehle",
        "vorschlag", "wie sieht es aus", "was liegt an", "termine",
        "nächste woche", "meine woche", "wochenübersicht", "zeig mir meine termine",
        "wie sieht meine nächste woche aus", "wie sieht meine woche aus", "was habe ich"
    ]

    if any(k in text for k in write_keywords): return "WRITE"
    if any(k in text for k in suggest_keywords): return "SUGGEST"
    if ("wann" in text or "habe" in text or "hab" in text) and "zeit" in text: return "SUGGEST"
    return "CHAT"

def get_habit_suggestion(db: Session, user_id: int, topic: str) -> Optional[str]:
    if not topic: return None
    past_tasks = db.query(TaskDB).filter(
        TaskDB.user_id == user_id,
        TaskDB.title.ilike(f"%{topic}%"),
        TaskDB.deadline.isnot(None)
    ).all()
    if not past_tasks: return None
    
    counts = {}
    for t in past_tasks:
        wd = t.deadline.weekday()
        hr = t.deadline.hour
        mn = t.deadline.minute
        k = (wd, hr, mn)
        counts[k] = counts.get(k, 0) + 1
        
    if not counts: return None
    best_slot = max(counts.items(), key=lambda x: x[1])
    (wd_idx, hr, mn) = best_slot[0]
    weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    return f"{weekdays[wd_idx]} um {hr}:{mn:02d} Uhr"

def execute_suggest_action(text: str, user_id: int, topic: Optional[str] = None) -> str:
    db = SessionLocal()
    try:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        days_to_check = 14
        txt_low = text.lower()
        if "nächsten monat" in txt_low or "nächster monat" in txt_low:
            if now.month == 12: start = datetime(now.year + 1, 1, 1)
            else: start = datetime(now.year, now.month + 1, 1)
            days_to_check = 31
        elif "nächste woche" in txt_low or "kommende woche" in txt_low:
            days_ahead = 7 - now.weekday()
            start = start + timedelta(days=days_ahead)
            days_to_check = 7
        elif "diese woche" in txt_low or "meine woche" in txt_low or "aktuelle woche" in txt_low:
            dcb = 7 - now.weekday()
            if now.weekday() >= 4: days_to_check = dcb + 7
            else: days_to_check = dcb
            if days_to_check < 1: days_to_check = 1

        end = start + timedelta(days=days_to_check)
        
        habit_hint = None
        if topic:
            habit_slot = get_habit_suggestion(db, user_id, topic)
            if habit_slot:
                habit_hint = f"KI-HINWEIS: Gewohnheit erkannt: '{topic}' meist '{habit_slot}'. Dies ist KEIN Termin, sondern nur ein Vorschlag! Wenn der Tag frei ist, schlage diesen Slot vor."

        tasks = db.query(TaskDB).filter(
            TaskDB.user_id == user_id,
            TaskDB.deadline >= start,
            TaskDB.deadline <= end,
            TaskDB.done == False
        ).order_by(TaskDB.deadline).all()
        
        tasks_by_date = {}
        for t in tasks:
            if t.deadline:
                d = t.deadline.date()
                if d not in tasks_by_date: tasks_by_date[d] = []
                tasks_by_date[d].append(t)
        
        recurring_tasks = db.query(TaskDB).filter(
            TaskDB.user_id == user_id,
            TaskDB.recurrence.isnot(None),
            TaskDB.recurrence != "",
            TaskDB.done == False,
            TaskDB.deadline <= end
        ).all()

        for rt in recurring_tasks:
            if not rt.deadline: continue
            rec_end_date = None
            if rt.custom_fields:
                try:
                    cf = ast.literal_eval(rt.custom_fields)
                    if isinstance(cf, dict) and cf.get("recurrence_end"):
                        rec_end_date = datetime.strptime(cf["recurrence_end"], '%Y-%m-%d').date()
                except: pass
            
            curr = start
            while curr <= end:
                if rec_end_date and curr.date() > rec_end_date: break
                is_occurrence = False
                rt_date = rt.deadline.date()
                if curr.date() >= rt_date:
                    if rt.recurrence == 'daily': is_occurrence = True
                    elif rt.recurrence == 'weekly': 
                        if curr.weekday() == rt.deadline.weekday(): is_occurrence = True
                    elif rt.recurrence == 'monthly':
                        if curr.day == rt.deadline.day: is_occurrence = True
                
                if is_occurrence:
                    d_key = curr.date()
                    if d_key not in tasks_by_date: tasks_by_date[d_key] = []
                    already_in = any(x.id == rt.id for x in tasks_by_date[d_key] if hasattr(x, 'id'))
                    if not already_in:
                         t_time = rt.deadline.time()
                         t_datetime = datetime.combine(curr.date(), t_time)
                         class VirtualTask:
                             def __init__(self, title, deadline, priority):
                                 self.title = title
                                 self.deadline = deadline
                                 self.priority = priority
                         tasks_by_date[d_key].append(VirtualTask(rt.title, t_datetime, rt.priority))
                curr += timedelta(days=1)
        
        weekdays = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        output_lines = []
        output_lines.append(f"SYSTEM-INFO (Kalender-Übersicht vom {start.strftime('%d.%m.')} bis {end.strftime('%d.%m.')}):")
        if habit_hint: output_lines.append(habit_hint)
        
        current_iso_week = None
        for i in range(days_to_check):
            current_day = start + timedelta(days=i)
            iso_year, iso_week, _ = current_day.isocalendar()
            if (iso_year, iso_week) != current_iso_week:
                current_iso_week = (iso_year, iso_week)
                output_lines.append(f"\n--- KALENDERWOCHE {iso_week} ({iso_year}) ---")

            d_date = current_day.date()
            wd_name = weekdays[current_day.weekday()]
            date_str = current_day.strftime('%d.%m.')
            day_tasks = tasks_by_date.get(d_date, [])
            
            if not day_tasks:
                output_lines.append(f"- {wd_name} ({date_str}): KOMPLETT FREI")
            else:
                task_summaries = []
                for t in day_tasks:
                    time_s = t.deadline.strftime('%H:%M')
                    prio_mark = "[!]" if t.priority > 1 else ""
                    task_summaries.append(f"{time_s} {t.title}{prio_mark}")
                joined_tasks = ", ".join(task_summaries)
                output_lines.append(f"- {wd_name} ({date_str}): Termine: {joined_tasks}")
        return "\n".join(output_lines)
    finally:
        db.close()

def _get_runtime_lm_model() -> str:
    try:
        base_url = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1")
        if base_url.endswith("/"): base_url = base_url[:-1]
        if not base_url.endswith("/v1"): models_url = f"{base_url}/v1/models"
        else: models_url = f"{base_url}/models"
        
        import requests
        resp = requests.get(models_url, timeout=1.0)
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                loaded_id = data["data"][0]["id"]
                return loaded_id
    except Exception: pass

    v = os.environ.get("LM_STUDIO_MODEL")
    if v: return v
    return LM_STUDIO_MODEL

def _clean_assistant_text(s: str) -> str:
    if s is None: return s
    try:
        s = re.sub(r"\*+", "", s)
        s = s.replace('`', '')
        lines = [line.strip() for line in s.splitlines()]
        s = "\n".join([ln for ln in lines if ln != ''])
        s = re.sub(r"[ \t]{2,}", " ", s)
        return s.strip()
    except Exception: return s

def parse_task(payload: dict):
    text = payload.get("text") if isinstance(payload, dict) else None
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' in payload")

    text_lower = text.lower()
    now = datetime.now()
    deadline_dt = None
    time_explicit = False
    date_explicit = False
    is_all_day = False
    
    priority = 1
    if any(w in text_lower for w in ["wichtig", "dringend", "eilig", "hohe priorität", "alarm", "priorität hoch", "!"]):
        priority = 3
    elif "mittel" in text_lower or "normale priorität" in text_lower:
        priority = 2

    color = None
    unsupported_color = None
    valid_colors = ["rot", "grün", "blau", "gelb"]
    known_invalid_colors = ["lila", "orange", "schwarz", "weiß", "grau", "pink", "braun", "türkis", "violett", "gold", "silber", "bunt", "magenta", "beige"]
    
    for c in valid_colors:
        if re.search(rf"\b{c}\b", text_lower):
            color = c
            break
    if not color:
        for c in known_invalid_colors:
             if re.search(rf"\b{c}\b", text_lower):
                unsupported_color = c
                break

    recurrence = None
    recurrence_end_str = None
    if "täglich" in text_lower or "jeden tag" in text_lower: recurrence = "daily"
    elif any(w in text_lower for w in ["wöchentlich", "jede woche", "jeden montag", "jeden dienstag", "jeden mittwoch", "jeden donnerstag", "jeden freitag", "jeden samstag", "jeden sonntag"]):
        recurrence = "weekly"
    elif "monatlich" in text_lower or "jeden monat" in text_lower: recurrence = "monthly"

    if recurrence:
        m_end = re.search(r"bis\s+(?:zum\s+)?(\d{1,2})\.(\d{1,2})\.?(\d{2,4})?", text_lower)
        if m_end:
            try:
                ed, em = int(m_end.group(1)), int(m_end.group(2))
                ey = int(m_end.group(3)) if m_end.group(3) else now.year
                if ey < 100: ey += 2000
                cand_end = datetime(ey, em, ed, 23, 59, 59)
                if not m_end.group(3) and cand_end < now: cand_end = datetime(ey + 1, em, ed, 23, 59, 59)
                recurrence_end_str = cand_end.strftime('%Y-%m-%d')
            except: pass
        
        m_for_weeks = re.search(r"für\s+(\d+)\s+wochen?", text_lower)
        if m_for_weeks and recurrence == 'weekly':
             weeks = int(m_for_weeks.group(1))
             recurrence_end_str = f"weeks={weeks}"

    target_date = None
    if any(k in text_lower for k in ["übermorgen", "uebermorgen", "über morgen"]):
        target_date = now + timedelta(days=2)
        date_explicit = True
    elif re.search(r"\b(morgen|moregn|morgne|morgn|tomorrow|mrgn)\b", text_lower):
        target_date = now + timedelta(days=1)
        date_explicit = True
    elif any(k in text_lower for k in ["heute", "huete", "today", "heut"]):
        target_date = now
        date_explicit = True
    
    if not target_date:
        m_days = re.search(r"in\s+(\d+)\s+tag", text_lower)
        if m_days: 
            target_date = now + timedelta(days=int(m_days.group(1)))
            date_explicit = True
        m_weeks = re.search(r"in\s+(\d+)\s+woche", text_lower)
        if m_weeks: 
            target_date = now + timedelta(weeks=int(m_weeks.group(1)))
            date_explicit = True
        if "in einer woche" in text_lower or "nächste woche" in text_lower or "naechste woche" in text_lower:
             if not any(wd in text_lower for wd in ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]):
                target_date = now + timedelta(weeks=1)
                date_explicit = True

    date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.?(\d{2,4})?", text_lower)
    if date_match:
        try:
            day, month = int(date_match.group(1)), int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else now.year
            if year < 100: year += 2000
            target_date = datetime(year, month, day)
            date_explicit = True
        except: pass
    
    if not date_explicit or not target_date:
            day_match = re.search(r"\b(\d{1,2})\.(?!\d)", text_lower)
            if day_match:
                try:
                    day = int(day_match.group(1))
                    candidate = datetime(now.year, now.month, day)
                    if candidate.date() < now.date():
                        month = now.month + 1
                        year = now.year
                        if month > 12: month, year = 1, year + 1
                        candidate = datetime(year, month, day)
                    target_date = candidate
                    date_explicit = True
                except: pass
        
    if not date_explicit or not target_date:
        if not target_date:
            day_match_no_dot = re.search(r"\bam\s+(\d{1,2})\b", text_lower)
            if day_match_no_dot:
                try:
                    day = int(day_match_no_dot.group(1))
                    candidate = datetime(now.year, now.month, day)
                    if candidate.date() < now.date():
                        month = now.month + 1
                        year = now.year
                        if month > 12: month, year = 1, year + 1
                        candidate = datetime(year, month, day)
                    target_date = candidate
                    date_explicit = True
                except: pass

        if not target_date:
            for m_name, m_num in MONTH_MAP.items():
                if m_name in text_lower:
                    m_date = re.search(rf"(\d{{1,2}})\.?\s*{m_name}", text_lower)
                    if m_date:
                        day = int(m_date.group(1))
                        year = now.year
                        try:
                            candidate = datetime(year, m_num, day)
                            if candidate.date() < now.date(): candidate = datetime(year + 1, m_num, day)
                            target_date = candidate
                            date_explicit = True
                        except: pass
                        break

    if not target_date:
        weekdays = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]
        for i, wd in enumerate(weekdays):
            if wd in text_lower:
                days_ahead = (i - now.weekday() + 7) % 7
                if days_ahead == 0: days_ahead = 7
                target_date = now + timedelta(days=days_ahead)
                date_explicit = True
                break

    target_time = None
    time_match = re.search(r"(?<![\d\.])(\d{1,2})[:\.](\d{2})(?!\.\d)", text_lower) 
    if time_match:
        h, m = int(time_match.group(1)), int(time_match.group(2))
        try:
            if 0 <= h <= 23 and 0 <= m <= 59:
                target_time = (h, m)
                time_explicit = True
        except: pass
    else:
        uhr_match = re.search(r"(\d{1,2})\s*uhr", text_lower)
        if uhr_match:
            h = int(uhr_match.group(1))
            try:
                if 0 <= h <= 23:
                    target_time = (h, 0)
                    time_explicit = True
            except: pass

    if target_time:
        h_raw, m_raw = target_time
        is_pm = any(w in text_lower for w in ["abend", "abends", "nachmittag", "nachmittags", "spät", "später"])
        is_night = any(w in text_lower for w in ["nacht", "nachts"])
        h_new = h_raw
        if is_pm and h_raw < 12: h_new += 12
        elif is_night:
            if 6 <= h_raw <= 11: h_new += 12
            elif h_raw == 12: h_new = 0
        target_time = (h_new, m_raw)

    if not target_date and target_time:
        now_check = datetime.now()
        candidate = datetime(now_check.year, now_check.month, now_check.day, target_time[0], target_time[1])
        if candidate < now_check: target_date = now_check + timedelta(days=1)
        else: target_date = now_check
    
    if target_date:
        if target_time:
            deadline_dt = target_date.replace(hour=target_time[0], minute=target_time[1], second=0, microsecond=0)
        else:
            deadline_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    remove_words = [
        "morgen", "übermorgen", "heute", "uhr", "am", "um", "den", "der", "die", "das",
        "termin", "eintragen", "planen", "bitte", "ich", "brauche", "einen", "habe",
        "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag",
        "hätte", "gerne", "mit", "dem", "titel", "namens", "betreff", "für", "ein", "eine",
        "mir", "uns", "wir", "wollen", "möchte", "möchten", "soll", "heißen", "lauten",
        "erinnere", "mich", "an", "aufgabe", "notiere", "schreibe", "auf", "kannst", "du", "trag",
        "fürs", "ans", "ins", "vom", "zum", "zur",
        "hallo", "hi", "hey", "guten", "tag", "moin", "servus",
        "abend", "mittag", "morgen", "nacht", "vormittag", "nachmittag", "früh", "spät",
        "mal", "eben", "schnell", "kurz", "bitte", "danke",
        "trage", "nächsten", "nächste", "kommenden", "kommende", "nächstes", "dieses", "diesen",
        "muss", "musst", "sry", "sorry", "ups", "upps", "entschuldigung", "pardon", "verzeihung",
        "spielen", "gehen", "machen", "tun", "lernen", "üben", "treffen", "sehen",
        "egal", "ganz", "einerlei", "entscheide", "entscheidest", "wählen", "wähle", "such", "aussuchen",
        "mach", "machst", "nimm", "nehmen", "ok", "okay", "gut", "alles", "klar", "passt",
        "dann", "aber", "sonst", "bitte",
        "wann", "habe", "hast", "ich", "du", "zeit", "passen", "würde", "passt", "lücke", "frei",
        "schlag", "schlage", "mir", "uns", "vor", "empfehle", "empfehlen", "welcher", "welche", "welchem",
        "wichtig", "dringend", "eilig", "alarm", "hohe", "priorität", "mittel", "normale",
        "rot", "grün", "blau", "gelb", "farbe", "markiere", "in",
        "täglich", "wöchentlich", "monatlich", "jeden", "tag", "woche", "monat"
    ]
    clean_text = re.sub(r"\d{1,2}[:\.]\d{2}", "", text_lower)
    clean_text = re.sub(r"\d{1,2}\s*uhr", "", clean_text)
    clean_text = re.sub(r"\d{1,2}\.\d{1,2}\.?", "", clean_text)
    clean_text = clean_text.replace(".", " ").replace(",", " ").replace("!", " ").replace("?", " ").replace("'", "").replace('"', "")
    
    for m_name in MONTH_MAP.keys(): clean_text = clean_text.replace(m_name, "")

    words = clean_text.split()
    filtered_words = [w for w in words if w not in remove_words and not w.isdigit()]
    
    if len(filtered_words) > 4: title = None
    else: title = " ".join(filtered_words).strip().title()
    if not title: title = None 

    if recurrence_end_str and recurrence_end_str.startswith("weeks=") and deadline_dt:
        try:
             w_count = int(recurrence_end_str.split("=")[1])
             end_dt = deadline_dt + timedelta(weeks=w_count)
             recurrence_end_str = end_dt.strftime('%Y-%m-%d')
        except: recurrence_end_str = None
    
    return {
        "deadline": deadline_dt.strftime('%Y-%m-%d %H:%M') if deadline_dt else None,
        "raw_date": deadline_dt.strftime('%Y-%m-%d') if deadline_dt else None,
        "raw_time": deadline_dt.strftime('%H:%M') if deadline_dt else None,
        "title": title,
        "priority": priority,
        "color": color,
        "unsupported_color": unsupported_color,
        "recurrence": recurrence,
        "recurrence_end": recurrence_end_str,
        "is_all_day": is_all_day,
        "time_explicitly_mentioned": time_explicit,
        "date_explicitly_mentioned": date_explicit,
    }

# --- Routes ---

@router.post("/parse_task")
async def parse_task_endpoint(request: Request):
    payload = await request.json()
    return parse_task(payload)

@router.post("/chat", response_model=ChatResponse)
def chat_with_lm_studio(request: ChatRequest, user_id: Optional[int] = Depends(get_current_user_id_optional)):
    rid = str(uuid.uuid4())
    if not user_id: user_id = 1 

    api_key = LM_STUDIO_API_KEY if LM_STUDIO_API_KEY else ""
    # Use global timeout if available or increase
    client = OpenAI(api_key=api_key, base_url=LM_STUDIO_URL, timeout=300.0)
    model_to_use = _get_runtime_lm_model() 
    
    conv_id = request.conversation_id or str(uuid.uuid4())
    user_entry = {"role": "user", "content": request.prompt}
    current_intent = detect_intent(request.prompt)
    
    auto_created_task_id = None
    task_already_exists = False
    task_time_conflict = None

    try:
        with CONV_LOCK:
            if conv_id not in CONVERSATIONS: CONVERSATIONS[conv_id] = []
            chat_history = CONVERSATIONS[conv_id]
            chat_history.append(user_entry)
            MAX_MESSAGES = 20
            if len(chat_history) > MAX_MESSAGES: chat_history = chat_history[-MAX_MESSAGES:]
            CONVERSATIONS[conv_id] = list(chat_history)
            history_copy = list(chat_history)
    except Exception: history_copy = [user_entry]

    auto_created_task_title = None
    auto_created_task_deadline = None
    
    try:
        if user_id and not auto_created_task_id:
            current_prompt = request.prompt
            try:
                parsed_quick = parse_task({"text": current_prompt})
            except Exception: parsed_quick = None
            
            auto_pick_keywords = ["entscheide", "wähle", "such aus", "egal", "mach du", "nimm einen", "nimm den"]
            if any(k in current_prompt.lower() for k in auto_pick_keywords):
                needs_pick = False
                if not parsed_quick: needs_pick = True
                elif not parsed_quick.get("deadline"): needs_pick = True
                
                if needs_pick:
                    found_slot = None
                    bot_msgs = [m for m in reversed(history_copy) if m.get("role") == "assistant"]
                    for msg in bot_msgs[:5]:
                        content = msg.get("content", "")
                        matches = re.findall(r"(\d{1,2})\.(\d{1,2})\.?,?.*?(\d{1,2}):(\d{2})", content)
                        if matches:
                            day, month, hour, minute = matches[0]
                            try:
                                now = datetime.now()
                                year = now.year
                                if int(month) < now.month and now.month > 10: year += 1
                                pick_dt = datetime(year, int(month), int(day), int(hour), int(minute))
                                found_slot = pick_dt
                                break
                            except: continue
                    if found_slot:
                        if not parsed_quick: parsed_quick = {}
                        parsed_quick["deadline"] = found_slot.strftime('%Y-%m-%d %H:%M')
                        parsed_quick["raw_date"] = found_slot.strftime('%Y-%m-%d')
                        parsed_quick["raw_time"] = found_slot.strftime('%H:%M')
                        parsed_quick["time_explicitly_mentioned"] = True
                        if "priority" not in parsed_quick: parsed_quick["priority"] = 1
                        if "title" not in parsed_quick: parsed_quick["title"] = None

            if parsed_quick:
                with CONV_LOCK: pending = PENDING_TASKS.get(conv_id, {})
                if not parsed_quick.get("title") and pending.get("title"):
                    parsed_quick["title"] = pending["title"]

                new_date = parsed_quick.get("raw_date")
                new_time = parsed_quick.get("raw_time")
                old_date = pending.get("raw_date")
                old_time = pending.get("raw_time") 

                if parsed_quick.get("date_explicitly_mentioned"): final_date = new_date
                else: final_date = old_date if old_date else new_date
                
                final_time = new_time if new_time else old_time
                parsed_quick["time_explicitly_mentioned"] = bool(final_time) or pending.get("time_explicitly_mentioned", False)

                if final_date and final_time:
                    try:
                        dt_str = f"{final_date} {final_time}"
                        datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                        parsed_quick["deadline"] = dt_str
                        parsed_quick["raw_date"] = final_date
                        parsed_quick["raw_time"] = final_time
                    except: pass
                elif final_date and not final_time:
                    if not parsed_quick.get("deadline") and pending.get("deadline"):
                         parsed_quick["deadline"] = pending["deadline"]
                
                if not parsed_quick.get("color") and pending.get("color"): parsed_quick["color"] = pending["color"]
                if not parsed_quick.get("unsupported_color") and pending.get("unsupported_color"): parsed_quick["unsupported_color"] = pending["unsupported_color"]
                if parsed_quick.get("priority") == 1 and pending.get("priority", 1) > 1: parsed_quick["priority"] = pending["priority"]
                if not parsed_quick.get("recurrence") and pending.get("recurrence"): parsed_quick["recurrence"] = pending["recurrence"]

            if parsed_quick:
                if not parsed_quick.get("title") and parsed_quick.get("deadline"):
                    for msg in reversed(history_copy):
                        if msg.get("role") == "assistant":
                            content = msg.get("content", "")
                            m_title = re.search(r"Termin '([^']+)'|Aufgabe '([^']+)'", content)
                            if m_title:
                                found_title = m_title.group(1) or m_title.group(2)
                                if found_title:
                                    parsed_quick["title"] = found_title
                                    break

                deadline_val_q = parsed_quick.get("deadline")
                if deadline_val_q:
                    deadline_dt_q = None
                    try:
                        deadline_dt_q = datetime.fromisoformat(deadline_val_q.replace(' ', 'T'))
                    except Exception: deadline_dt_q = None
                    
                    should_create = ((parsed_quick.get("time_explicitly_mentioned") or parsed_quick.get("is_all_day")) and parsed_quick.get("title"))
                    
                    if deadline_dt_q and should_create:
                        db = SessionLocal()
                        try:
                            exists = db.query(TaskDB).filter(TaskDB.user_id == user_id, TaskDB.title == parsed_quick.get("title"), TaskDB.deadline == deadline_dt_q).first()
                            if not exists:
                                conflict = db.query(TaskDB).filter(TaskDB.user_id == user_id, TaskDB.deadline == deadline_dt_q, TaskDB.done == False).first()
                                if conflict:
                                    task_time_conflict = conflict.title
                                    auto_created_task_title = parsed_quick.get("title")
                                    auto_created_task_deadline = deadline_dt_q
                                else:
                                    custom_fields_dict = {}
                                    if parsed_quick.get("recurrence_end"): custom_fields_dict["recurrence_end"] = parsed_quick.get("recurrence_end")
                                    db_task = TaskDB(
                                        title=parsed_quick.get("title") or "Termin",
                                        description=parsed_quick.get("notes"),
                                        deadline=deadline_dt_q,
                                        priority=parsed_quick.get("priority") or 1,
                                        done=False,
                                        user_id=user_id,
                                        color=parsed_quick.get("color"),
                                        recurrence=parsed_quick.get("recurrence"),
                                        notes=parsed_quick.get("notes"),
                                        custom_fields=str(custom_fields_dict) if custom_fields_dict else None
                                    )
                                    db.add(db_task)
                                    db.commit()
                                    db.refresh(db_task)
                                    auto_created_task_id = db_task.id
                                    auto_created_task_title = db_task.title
                                    auto_created_task_deadline = db_task.deadline
                                    with CONV_LOCK:
                                        if conv_id in PENDING_TASKS: del PENDING_TASKS[conv_id]
                            else:
                                task_already_exists = True
                                auto_created_task_title = exists.title
                                auto_created_task_deadline = exists.deadline
                        finally: db.close()
                    else:
                        has_date = bool(parsed_quick.get("deadline"))
                        has_title = bool(parsed_quick.get("title"))
                        if (has_date or has_title):
                            with CONV_LOCK:
                                pending = PENDING_TASKS.get(conv_id, {})
                                new_pending = {}
                                if parsed_quick.get("date_explicitly_mentioned") and parsed_quick.get("raw_date"): new_pending["raw_date"] = parsed_quick["raw_date"]
                                elif pending.get("raw_date"): new_pending["raw_date"] = pending["raw_date"]
                                elif parsed_quick.get("raw_date"): new_pending["raw_date"] = parsed_quick["raw_date"]
                                
                                if parsed_quick.get("raw_time"): new_pending["raw_time"] = parsed_quick["raw_time"]
                                elif pending.get("raw_time"): new_pending["raw_time"] = pending["raw_time"]

                                if new_pending.get("raw_date"):
                                    d_p = new_pending["raw_date"]
                                    t_p = new_pending.get("raw_time", "00:00")
                                    new_pending["deadline"] = f"{d_p} {t_p}"
                                elif parsed_quick.get("deadline"): new_pending["deadline"] = parsed_quick["deadline"]
                                elif pending.get("deadline"): new_pending["deadline"] = pending["deadline"]
                                
                                new_pending["time_explicitly_mentioned"] = parsed_quick.get("time_explicitly_mentioned") or pending.get("time_explicitly_mentioned")
                                new_pending["date_explicitly_mentioned"] = parsed_quick.get("date_explicitly_mentioned") or pending.get("date_explicitly_mentioned")

                                if has_title: new_pending["title"] = parsed_quick["title"]
                                elif pending.get("title"): new_pending["title"] = pending["title"]
                                
                                if parsed_quick.get("color"): new_pending["color"] = parsed_quick["color"]
                                elif pending.get("color"): new_pending["color"] = pending["color"]
                                if parsed_quick.get("unsupported_color"): new_pending["unsupported_color"] = parsed_quick["unsupported_color"]
                                elif pending.get("unsupported_color"): new_pending["unsupported_color"] = pending.get("unsupported_color")
                                
                                p1 = parsed_quick.get("priority", 1)
                                p2 = pending.get("priority", 1)
                                new_pending["priority"] = max(p1, p2)
                                
                                if parsed_quick.get("recurrence"): new_pending["recurrence"] = parsed_quick["recurrence"]
                                elif pending.get("recurrence"): new_pending["recurrence"] = pending["recurrence"]

                                PENDING_TASKS[conv_id] = new_pending
    except Exception as e:
        auto_created_task_id = None
        system_info = f"SYSTEM-INFO: Termin KONNTE NICHT gespeichert werden (Interner Fehler: {e}). Sag dem User, dass es einen Fehler gab."

    messages = [{"role": "system", "content": RESPONDER_SYSTEM_PROMPT}]
    messages.extend(history_copy)
    
    if "system_info" not in locals(): system_info = ""
    if auto_created_task_id:
        details = []
        if auto_created_task_deadline:
            deadline_str = auto_created_task_deadline.strftime('%d.%m.%Y %H:%M')
            details.append(f"Datum='{deadline_str}'")
        try:
            db_check = SessionLocal()
            t_check = db_check.query(TaskDB).filter(TaskDB.id == auto_created_task_id).first()
            if t_check:
                if t_check.priority > 1: details.append("Priorität='Hoch/Wichtig'")
                if t_check.color: details.append(f"Farbe='{t_check.color}'")
                elif parsed_quick and parsed_quick.get("unsupported_color"):
                    details.append(f"WARNUNG: Farbe '{parsed_quick['unsupported_color']}' nicht unterstützt (nur: rot, grün, blau, gelb)")
                if t_check.recurrence == 'weekly': details.append("Wiederholung='Wöchentlich'")
                elif t_check.recurrence == 'daily': details.append("Wiederholung='Täglich'")
                elif t_check.recurrence == 'monthly': details.append("Wiederholung='Monatlich'")
            db_check.close()
        except: pass
        
        info_str = ", ".join(details)
        system_info = f"SYSTEM-INFO: Termin '{auto_created_task_title}' erfolgreich gespeichert ({info_str})."
    elif task_time_conflict:
        deadline_str = auto_created_task_deadline.strftime('%d.%m.%Y %H:%M') if auto_created_task_deadline else "diesem Zeitpunkt"
        system_info = f"SYSTEM-INFO: Termin KONNTE NICHT gespeichert werden. Es gibt bereits einen Termin um diese Zeit ({deadline_str}): '{task_time_conflict}'. Frage den User, ob er ihn verschieben möchte."
    elif task_already_exists:
        if auto_created_task_deadline:
            deadline_str = auto_created_task_deadline.strftime('%d.%m.%Y %H:%M')
            system_info = f"SYSTEM-INFO: Ein Termin mit diesem Titel und Datum existiert bereits: Titel='{auto_created_task_title}', Datum='{deadline_str}'. Sag dem User, dass der Termin schon existiert."
        else:
             system_info = f"SYSTEM-INFO: Ein Termin mit diesem Titel existiert bereits: Titel='{auto_created_task_title}'."
    elif current_intent == "WRITE" and not system_info:
        with CONV_LOCK:
             p = PENDING_TASKS.get(conv_id)
             if p:
                  missing = []
                  if not p.get("deadline") and not p.get("raw_date"): missing.append("Datum")
                  if not p.get("title"): missing.append("Titel")
                  has_time = bool(p.get("time_explicitly_mentioned") or p.get("is_all_day") or p.get("raw_time"))
                  if not has_time: missing.append("Uhrzeit")
                  if missing: system_info = f"SYSTEM-INFO: Termin unvollständig. Es fehlen: {', '.join(missing)}."
                  else: system_info = f"SYSTEM-INFO: Termin konnte nicht erstellt werden (Unbekannter Grund). Vorhandene Daten: {p}"
    else:
        pending_check = None
        with CONV_LOCK: pending_check = PENDING_TASKS.get(conv_id)
        should_suggest = (current_intent == "SUGGEST")
        topic_for_suggest = None
        if pending_check and pending_check.get("title") and not pending_check.get("deadline"):
            should_suggest = True
            topic_for_suggest = pending_check.get("title")

        if should_suggest:
            cal_str = execute_suggest_action(request.prompt, user_id, topic=topic_for_suggest)
            system_info = cal_str

    if system_info:
        messages.append({"role": "user", "content": system_info})
    
    try:
        completion = client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            temperature=0.7,
            max_tokens=-1
        )
        assistant_reply = completion.choices[0].message.content
        assistant_reply = _clean_assistant_text(assistant_reply)

        with CONV_LOCK:
            CONVERSATIONS[conv_id].append({"role": "assistant", "content": assistant_reply})
            if auto_created_task_id: CONVERSATION_TASKS[conv_id] = auto_created_task_id
        
        return ChatResponse(
            response=assistant_reply,
            conversation_id=conv_id,
            auto_created_task_id=auto_created_task_id,
            intent=current_intent
        )
    except Exception as e:
        ra