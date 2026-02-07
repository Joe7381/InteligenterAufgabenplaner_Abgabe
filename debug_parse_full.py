import re
from datetime import datetime, timedelta

MONTH_MAP = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
}

def parse_task(payload: dict):
    text = payload.get("text", "")
    text_lower = text.lower()
    now = datetime.now()
    
    time_explicit = False
    is_all_day = False
    
    # --- 1. DATUM ERKENNEN ---
    target_date = None
    
    # "morgen"
    if "morgen" in text_lower or "tomorrow" in text_lower:
        target_date = now + timedelta(days=1)
    # "übermorgen"
    elif "übermorgen" in text_lower:
        target_date = now + timedelta(days=2)
    # "heute"
    elif "heute" in text_lower or "today" in text_lower:
        target_date = now
    # "montag", "dienstag", ...
    else:
        weekdays = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]
        for i, wd in enumerate(weekdays):
            if wd in text_lower:
                # Finde den nächsten Wochentag
                days_ahead = (i - now.weekday() + 7) % 7
                if days_ahead == 0: days_ahead = 7
                target_date = now + timedelta(days=days_ahead)
                break
    
    # Datum im Format DD.MM.
    if not target_date:
        # Versuch 1: DD.MM.YYYY oder DD.MM.
        date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.?(\d{2,4})?", text_lower)
        if date_match:
            day, month = int(date_match.group(1)), int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else now.year
            if year < 100: year += 2000
            try:
                target_date = datetime(year, month, day)
            except:
                pass
        if not target_date:
            # Versuch 2: Nur DD. (z.B. "am 21.")
            # Lookahead (?!\d) verhindert Match bei Uhrzeiten wie 18.30
            day_match = re.search(r"\b(\d{1,2})\.(?!\d)", text_lower)
            if day_match:
                try:
                    day = int(day_match.group(1))
                    # Wir nehmen erst mal den aktuellen Monat an
                    candidate = datetime(now.year, now.month, day)
                    # Wenn der Tag schon vorbei ist, nehmen wir den nächsten Monat
                    if candidate.date() < now.date():
                        # Add 1 month logic
                        month = now.month + 1
                        year = now.year
                        if month > 12:
                            month = 1
                            year += 1
                        candidate = datetime(year, month, day)
                    target_date = candidate
                except:
                    pass
        
        if not target_date:
            # Versuch 2b: "am 15" ohne Punkt (z.B. "am 15")
            day_match_no_dot = re.search(r"\bam\s+(\d{1,2})\b", text_lower)
            if day_match_no_dot:
                try:
                    day = int(day_match_no_dot.group(1))
                    candidate = datetime(now.year, now.month, day)
                    if candidate.date() < now.date():
                        month = now.month + 1
                        year = now.year
                        if month > 12:
                            month = 1
                            year += 1
                        candidate = datetime(year, month, day)
                    target_date = candidate
                except:
                    pass

        if not target_date:
            # Versuch 3: DD. Monat (z.B. "28. januar")
            # Wir nutzen MONTH_MAP für die Erkennung
            for m_name, m_num in MONTH_MAP.items():
                if m_name in text_lower:
                    # Suche nach Zahl vor dem Monatsnamen
                    # Pattern: Zahl + optional Punkt + optional Space + Monatsname
                    # z.B. "28. januar", "28 januar", "am 28. januar"
                    m_date = re.search(rf"(\d{{1,2}})\.?\s*{m_name}", text_lower)
                    if m_date:
                        day = int(m_date.group(1))
                        year = now.year
                        # Wenn Datum in Vergangenheit, dann nächstes Jahr
                        try:
                            candidate = datetime(year, m_num, day)
                            if candidate.date() < now.date():
                                candidate = datetime(year + 1, m_num, day)
                            target_date = candidate
                        except:
                            pass
                        break

    # --- 2. UHRZEIT ERKENNEN ---
    target_time = None
    # HH:MM oder H Uhr
    # Fix: (?!\.) verhindert, dass 12.01.2026 als 12:01 erkannt wird
    # Fix 2: (?<![\d\.]) verhindert, dass Teile von 12.01.2026 als Uhrzeit erkannt werden
    time_match = re.search(r"(?<![\d\.])(\d{1,2})[:\.](\d{2})(?!\.)", text_lower) 
    if time_match:
        h, m = int(time_match.group(1)), int(time_match.group(2))
        target_time = (h, m)
        time_explicit = True
    else:
        # "18 uhr"
        uhr_match = re.search(r"(\d{1,2})\s*uhr", text_lower)
        if uhr_match:
            h = int(uhr_match.group(1))
            target_time = (h, 0)
            time_explicit = True
    
    # --- 3. ZUSAMMENBAUEN ---
    if target_date:
        if target_time:
            deadline_dt = target_date.replace(hour=target_time[0], minute=target_time[1], second=0, microsecond=0)
        else:
            # Standard: Wenn Datum aber keine Zeit -> Ganztägig oder Standardzeit?
            # Wir setzen es auf 00:00 und is_all_day=False (oder True, je nach Logik)
            # Hier: Wenn keine Zeit, nehmen wir an es ist ein Datum-Merker
            deadline_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            # Wenn User nur "morgen zahnarzt" sagt, ist es oft ganztägig oder flexibel
            # Wir lassen time_explicit = False
    else:
        deadline_dt = None

    # --- 4. TITEL EXTRAHIEREN (Heuristik) ---
    # Entferne Datum/Zeit-Wörter aus dem Text, der Rest ist der Titel
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
        "muss", "musst"
    ]
    # Entferne Zeit-Patterns
    clean_text = re.sub(r"\d{1,2}[:\.]\d{2}", "", text_lower)
    clean_text = re.sub(r"\d{1,2}\s*uhr", "", clean_text)
    clean_text = re.sub(r"\d{1,2}\.\d{1,2}\.?", "", clean_text)
    
    # Entferne Satzzeichen am Ende von Wörtern (einfach)
    clean_text = clean_text.replace(".", " ").replace(",", " ").replace("!", " ").replace("?", " ")
    
    # Entferne Monatsnamen aus dem Text, damit sie nicht im Titel landen
    for m_name in MONTH_MAP.keys():
        clean_text = clean_text.replace(m_name, "")

    words = clean_text.split()
    filtered_words = [w for w in words if w not in remove_words and not w.isdigit()]
    
    title = " ".join(filtered_words)
    if not title:
        title = None
    else:
        # Capitalize first letter
        title = title[0].upper() + title[1:]

    return {
        "title": title,
        "deadline": deadline_dt.isoformat() if deadline_dt else None,
        "time_explicitly_mentioned": time_explicit,
        "is_all_day": is_all_day
    }

# Test cases
prompts = [
    "Termin am 12.01.2026 um 14:00 Uhr Zahnarzt",
    "Übermorgen um 10 Uhr Team-Meeting",
    "Nächsten Montag Sport um 18 Uhr",
    "Ich muss am 15. um 9 Uhr zur Bank"
]

for p in prompts:
    print(f"Prompt: '{p}'")
    print(f"Result: {parse_task({'text': p})}")
    print("-" * 20)
