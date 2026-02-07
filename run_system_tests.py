import requests
import uuid
import time
import sys

BASE_URL = "http://localhost:8000"

# --- CREDENTIALS FROM USER ---
TEST_EMAIL = "testuser@example.com"
TEST_PASS = "testpass123"

def login_and_get_token():
    print(f"Logging in as {TEST_EMAIL}...")
    try:
        resp = requests.post(f"{BASE_URL}/login", json={"email": TEST_EMAIL, "password": TEST_PASS})
        resp.raise_for_status()
        token = resp.json().get("access_token")
        print("Login successful.")
        return token
    except Exception as e:
        print(f"LOGIN FAILED: {e}")
        # Wir machen weiter, aber ohne Token greift evtl. der Fallback User=1 (falls Backend so konfiguriert)
        # aber eigentlich wollen wir User=7
        return None

def run_scenario(name, steps, token):
    print(f"\n{'='*60}")
    print(f"SCENARIO: {name}")
    print(f"{'='*60}")
    
    conv_id = str(uuid.uuid4())
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    for i, user_text in enumerate(steps):
        print(f"\n[Step {i+1}] User: {user_text}")
        
        try:
            payload = {
                "prompt": user_text,
                "conversation_id": conv_id
            }
            # Add headers here
            resp = requests.post(f"{BASE_URL}/chat", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            bot_text = data["response"]
            task_id = data.get("auto_created_task_id")
            
            print(f"Bot: {bot_text}")
            if task_id:
                print(f">> SYSTEM: Task Created! ID={task_id}")
                print(f">> SYSTEM: Task Created! ID={task_id}")
            else:
                print(f">> SYSTEM: No Task ID returned.")
            
        except Exception as e:
            print(f"ERROR: {e}")
            break
        
        time.sleep(1) # kurzen Moment warten

def main():
    token = login_and_get_token()

    # --- SCENARIO 12: Wiederkehrende Termine & Sichtbarkeit ---
    # Testet, ob tägliche Termine an ALLEN Tagen der Woche angezeigt werden
    run_scenario("12. Recurrence Visibility (Daily Standup)", [
        "Trage 'Morning Briefing' täglich um 08:30 Uhr ein.",
        "Wie sieht meine nächste Woche aus?" 
    ], token)

    # --- SCENARIO 13: Habit Suggestion (Squash) ---
    # Trainieren: Einmal Squash am Dienstag.
    # Abfragen: Vorschlag für nächste Woche (sollte wieder Dienstag sein).
    run_scenario("13. Habit Suggestion (Squash)", [
        "Trage Squash am Dienstag den 20.01.2026 um 18:00 Uhr ein.",
        "Schlag mir einen Termin für Squash in der Woche vom 26. Januar vor."
    ], token)

    # --- SCENARIO 14: Limited Recurrence (Bis-Datum) ---
    # Testet, ob 'täglich bis 25.01.' am 26.01. NICHT mehr angezeigt wird.
    run_scenario("14. Limited Recurrence (Project Sprint)", [
        "Trage 'Sprint Meeting' täglich um 10:00 bis zum 25.01.2026 ein.",
        "Wie sieht meine Woche vom 26. Januar aus?"  # Sollte Sprint Meeting NICHT enthalten
    ], token)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
