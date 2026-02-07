import requests
import json
import time

BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{BASE_URL}/chat"
HEADERS = {"Content-Type": "application/json"}

def print_separator():
    print("-" * 60)

def test_chat(prompt, description):
    print_separator()
    print(f"TEST: {description}")
    print(f"User: \"{prompt}\"")
    
    payload = {
        "prompt": prompt,
        "conversation_id": "demo-presentation-test" 
    }
    
    try:
        start_time = time.time()
        response = requests.post(CHAT_ENDPOINT, json=payload, headers=HEADERS)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            bot_response = data.get("response", "")
            intent = data.get("intent", "UNKNOWN")
            task_id = data.get("auto_created_task_id")
            
            print(f"Bot ({duration:.2f}s): {bot_response}")
            print(f"[DEBUG Info] Intent: {intent}, Created Task ID: {task_id}")
            return True
        else:
            print(f"ERROR: Status Code {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Konnte Server nicht erreichen. Läuft uvicorn auf Port 8000?")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def run_presentation_check():
    print("\nSTARTE SYSTEM-CHECK FÜR PRÄSENTATION...\n")
    
    # 1. Termin eintragen
    # Wir nehmen "Zahnarzt morgen um 10 Uhr", das ist eindeutig.
    success_1 = test_chat("Trage Zahnarzt morgen um 10 Uhr ein", "Termin eintragen (Normal)")
    
    if not success_1:
        print("\nABBRUCH: Server scheint nicht erreichbar zu sein.")
        return

    # Kurze Pause für Realismus
    time.sleep(1)

    # 2. Fragen wann Zeit ist
    test_chat("Wann habe ich nächste Woche Zeit?", "Freie Zeit abfragen")

    time.sleep(1)
    
    # 3. Termin vorschlagen lassen (Klavier)
    # Hier erwarten wir, dass er die Gewohnheit pickt (falls vorhanden) oder einen freien Slot sucht
    test_chat("Schlag mir einen Termin zum Klavier spielen vor", "Vorschlag (Gewohnheit)")

if __name__ == "__main__":
    run_presentation_check()
