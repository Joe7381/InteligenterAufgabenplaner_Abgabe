import requests
import datetime
import sys
import os
import uuid
import time

# Add current directory to path so we can import local modules
sys.path.append(os.getcwd())

from database import SessionLocal
from task_models import TaskDB
from sqlalchemy import desc

BASE_URL = "http://127.0.0.1:8000"

def send_chat(prompt, conversation_id=None):
    url = f"{BASE_URL}/chat"
    payload = {"prompt": prompt}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Request failed: {e}")
        return None

def verify_latest_task(expected_title_part, expected_hour=None):
    db = SessionLocal()
    try:
        # Get the latest task for user 1
        latest_task = db.query(TaskDB).filter(TaskDB.user_id == 1).order_by(desc(TaskDB.id)).first()
        
        if not latest_task:
            print("❌ DB Check: Kein Task gefunden.")
            return False

        print(f"   DB Check: ID={latest_task.id}, Title='{latest_task.title}', Deadline={latest_task.deadline}")
        
        title_ok = expected_title_part.lower() in latest_task.title.lower()
        time_ok = True
        if expected_hour is not None and latest_task.deadline:
            if latest_task.deadline.hour != expected_hour:
                print(f"❌ Zeit falsch: Erwartet {expected_hour} Uhr, gefunden {latest_task.deadline.hour} Uhr")
                time_ok = False
        
        if title_ok and time_ok:
            print("✅ DB Check: OK")
            return True
        else:
            print(f"❌ DB Check: Titel-Match={title_ok}, Zeit-Match={time_ok}")
            return False
    finally:
        db.close()

def run_test_case(name, prompt, expected_title=None, expected_hour=None, conversation_id=None):
    print(f"\n🔹 TEST: {name}")
    print(f"   Prompt: '{prompt}'")
    
    data = send_chat(prompt, conversation_id)
    if not data:
        return conversation_id

    print(f"   Bot: '{data['response']}'")
    
    if expected_title:
        # Wait a moment for DB write (though it should be sync in this app)
        verify_latest_task(expected_title, expected_hour)
    
    return data.get("conversation_id")

def run_all_tests():
    print("🧹 Bereinige alte Tasks...")
    db = SessionLocal()
    try:
        db.query(TaskDB).filter(TaskDB.user_id == 1).delete()
        db.commit()
    except Exception as e:
        print(f"Fehler beim Bereinigen: {e}")
    finally:
        db.close()

    print("🚀 Starte umfangreiche Test-Suite...")
    
    # 1. Explizites Datum & Zeit
    run_test_case(
        "Explizit", 
        "Termin am 12.01.2026 um 14:00 Uhr Zahnarzt", 
        expected_title="Zahnarzt", 
        expected_hour=14
    )

    # 2. Relatives Datum (Übermorgen)
    # Wir müssen wissen, welcher Tag übermorgen ist, um es manuell zu prüfen, 
    # aber hier reicht uns, dass ein Task erstellt wird.
    run_test_case(
        "Relativ (Übermorgen)", 
        "Übermorgen um 10 Uhr Team-Meeting", 
        expected_title="Team-Meeting", 
        expected_hour=10
    )

    # 3. Wochentag
    run_test_case(
        "Wochentag (Nächsten Montag)", 
        "Nächsten Montag Sport um 18 Uhr", 
        expected_title="Sport", 
        expected_hour=18
    )

    # 4. "am 15." (ohne Monat)
    run_test_case(
        "Nur Tag (am 15.)", 
        "Ich muss am 15. um 9 Uhr zur Bank", 
        expected_title="Bank", 
        expected_hour=9
    )

    # 5. Multi-Turn (Kontext)
    print("\n🔹 TEST: Multi-Turn (Kontext)")
    conv_id = str(uuid.uuid4())
    # Schritt 1: Nur Datum
    conv_id = run_test_case(
        "Multi-Turn 1 (Datum)", 
        "Ich brauche einen Termin am Freitag um 12 Uhr", 
        expected_title=None, # Noch kein Task erwartet
        conversation_id=conv_id
    )
    # Schritt 2: Titel nachliefern
    run_test_case(
        "Multi-Turn 2 (Titel)", 
        "Mittagessen mit Chef", 
        expected_title="Mittagessen Chef", 
        expected_hour=12,
        conversation_id=conv_id
    )

    # 6. Suggest / Freie Zeiten
    run_test_case(
        "Suggest (Wann Zeit?)", 
        "Wann habe ich nächste Woche Zeit?", 
        expected_title=None
    )

    print("\n✅ Alle Tests abgeschlossen.")

if __name__ == "__main__":
    run_all_tests()
