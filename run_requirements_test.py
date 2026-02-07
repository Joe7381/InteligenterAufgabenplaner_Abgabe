import requests
import time
import os
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Konfiguration laden
load_dotenv()
BASE_URL = "http://localhost:8000"

# Farben für Output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Globale Variablen für Tests
TEST_USER_TOKEN = None 
TEST_USER_ID = 1
CREATED_TASK_IDS = []

def log(message, status="INFO"):
    if status == "PASS":
        print(f"[{GREEN}PASS{RESET}] {message}")
    elif status == "FAIL":
        print(f"[{RED}FAIL{RESET}] {message}")
    elif status == "WARN":
        print(f"[{YELLOW}WARN{RESET}] {message}")
    else:
        print(f"[INFO] {message}")

def get_auth_token():
    """Holt einen validen Token für die Tests (Login)"""
    global TEST_USER_TOKEN
    global TEST_USER_ID
    
    # Eindeutige E-Mail generieren
    unique_id = uuid.uuid4().hex[:6]
    email = f"test_{unique_id}@example.com"
    password = "testpassword123"
    
    # 1. Registrieren
    # Endpoint laut auth_router.py: /register (UserCreate: email, password)
    reg_payload = {"email": email, "password": password}
    try:
        requests.post(f"{BASE_URL}/register", json=reg_payload)
    except:
        pass 

    # 2. Login
    # Endpoint laut auth_router.py: /login (UserLogin: email, password)
    login_payload = {"email": email, "password": password}
    resp = requests.post(f"{BASE_URL}/login", json=login_payload)
    
    if resp.status_code == 200:
        data = resp.json()
        TEST_USER_TOKEN = data.get("access_token")
        
        # User ID aus Token extrahieren (einfaches Base64 decoding payload)
        try:
            import base64
            import json
            # JWT ist header.payload.signature
            payload_part = TEST_USER_TOKEN.split('.')[1]
            # Padding korrigieren
            payload_part += '=' * (-len(payload_part) % 4)
            payload_json = base64.b64decode(payload_part).decode('utf-8')
            payload_data = json.loads(payload_json)
            TEST_USER_ID = payload_data.get("user_id")
            log(f"Login erfolgreich. User ID: {TEST_USER_ID}", "INFO")
        except Exception as e:
            log(f"Konnte User ID nicht aus Token lesen: {e}", "WARN")
            # Fallback falls Decoding fehlschlägt, aber Token existiert
            
        return True
    
    log(f"Login fehlgeschlagen: {resp.text}", "FAIL")
    return False

def get_headers():
    return {"Authorization": f"Bearer {TEST_USER_TOKEN}"}

# --- 1. PERFORMANCE TESTS (Nicht-Funktional 2.3) ---
def test_backend_performance():
    print("\n--- 1. PERFORMANCE & HEALTH (Ziel: < 300ms) ---")
    start = time.time()
    try:
        resp = requests.get(f"{BASE_URL}/tasks?user_id={TEST_USER_ID}", headers=get_headers())
        duration_ms = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            if duration_ms <= 300:
                log(f"Tasks laden: {duration_ms:.2f}ms (OK)", "PASS")
            else:
                log(f"Tasks laden: {duration_ms:.2f}ms (SLOW > 300ms)", "WARN")
        else:
            log(f"API Fehler: {resp.status_code}", "FAIL")
    except Exception as e:
        log(f"Verbindung fehlgeschlagen: {e}", "FAIL")

# --- 2. AUFGABENVERWALTUNG & ATTRIBUTE (Funktional 2.2) ---
def test_task_lifecycle():
    print("\n--- 2. AUFGABEN LIFECYCLE & ATTRIBUTE ---")
    
    # A. Erstellen (Create)
    new_task = {
        "title": "Systemtest Aufgabe",
        "description": "Testet Attribute wie Farbe und Prio",
        "priority": 3,
        "color": "rot",
        "deadline": (datetime.now() + timedelta(days=1)).isoformat(),
        "recurrence": "weekly",
        "user_id": TEST_USER_ID
    }
    
    resp = requests.post(f"{BASE_URL}/tasks", json=new_task, headers=get_headers())
    task_id = None
    
    if resp.status_code == 200:
        data = resp.json()
        task_id = data.get("id")
        CREATED_TASK_IDS.append(task_id)
        
        # Validierung Attribute
        if (data["priority"] == 3 and data["color"] == "rot" and 
            data["recurrence"] == "weekly" and data["title"] == "Systemtest Aufgabe"):
            log("Aufgabe erstellt mit korrekten Attributen (Prio, Farbe, Wiederholung)", "PASS")
        else:
            log(f"Attribute stimmen nicht: {data}", "FAIL")
    else:
        log(f"Erstellen fehlgeschlagen: {resp.text}", "FAIL")
        return

    # B. Status ändern (Erledigt markieren)
    # Check if we can change status (PUT /tasks/{id})
    # PUT erfordert oft das komplette Objekt. Wir senden Titel und ID mit.
    update_payload = new_task.copy()
    update_payload["id"] = task_id
    update_payload["done"] = True
    # user_id ist nicht Teil des Pydantic Models und sollte entfernt werden, 
    # falls Pydantic "extra fields" forbid hat, sonst wird es ignoriert.
    if "user_id" in update_payload:
        del update_payload["user_id"]

    resp_up = requests.put(f"{BASE_URL}/tasks/{task_id}", json=update_payload, headers=get_headers())
    if resp_up.ok and resp_up.json().get("done") is True:
        log("Aufgabe als 'erledigt' markiert", "PASS")
    else:
        log(f"Status-Update fehlgeschlagen: {resp_up.text}", "FAIL")

    # C. Löschen
    # (Wir löschen später im Cleanup)

# --- 3. FILTER & SUCHE (Funktional 2.2) ---
def test_filtering():
    print("\n--- 3. FILTER & SUCHE ---")
    # Wir erstellen 2 Tasks: 1x Prio 1, 1x Prio 3
    t1 = {"title": "Filter Low", "priority": 1, "user_id": TEST_USER_ID}
    t2 = {"title": "Filter High", "priority": 3, "user_id": TEST_USER_ID}
    
    res1 = requests.post(f"{BASE_URL}/tasks", json=t1, headers=get_headers())
    res2 = requests.post(f"{BASE_URL}/tasks", json=t2, headers=get_headers())
    
    if res1.ok and res2.ok:
        CREATED_TASK_IDS.extend([res1.json().get("id"), res2.json().get("id")])
    
    # Test: Laden aller Tasks und prüfen ob unsere da sind (Basis für Frontend-Filter)
    resp = requests.get(f"{BASE_URL}/tasks?user_id={TEST_USER_ID}", headers=get_headers())
    tasks = resp.json()
    found_high = any(t["title"] == "Filter High" for t in tasks)
    
    if found_high:
        log("Tasks für Filterung abrufbar (Konsistenz)", "PASS")
    else:
        log("Erstellte Tasks nicht in Liste gefunden", "FAIL")

# --- 4. KI CHAT & ROBUSTHEIT (Nicht-Funktional 2.3) ---
def test_ai_robustness():
    print("\n--- 4. KI CHAT & ROBUSTHEIT ---")
    
    # A. Normaler Chat
    payload = {"prompt": "Hallo, wer bist du?", "conversation_id": "test-robustness"}
    start = time.time()
    resp = requests.post(f"{BASE_URL}/chat", json=payload, headers=get_headers())
    duration = time.time() - start
    
    if resp.status_code == 200:
        log(f"KI antwortet ({duration:.2f}s)", "PASS")
    else:
        log(f"KI Fehler: {resp.status_code}", "FAIL")

    # B. Robustheit (Leere Eingabe / Fehlerhafte Daten)
    try:
        resp_err = requests.post(f"{BASE_URL}/chat", json={}, headers=get_headers()) # Kein Prompt
        if resp_err.status_code == 422: # Validation Error erwartet (FastAPI Standard)
            log("API fängt ungültige Payloads ab (422 Unprocessable Entity)", "PASS")
        else:
            log(f"API verhält sich unerwartet bei leerem Body: {resp_err.status_code}", "WARN")
    except:
        log("API abgestürzt bei leerem Body", "FAIL")

# --- 5. SECURITY (Nicht-Funktional 2.3) ---
def test_security():
    print("\n--- 5. SECURITY & SECRETS ---")
    
    # A. Zugriff ohne Token
    # Wir versuchen Tasks ohne Header abzurufen
    resp = requests.get(f"{BASE_URL}/tasks", headers={}) # Kein Header
    # FastAPI liefert 401 Not Authenticated standardmäßig bei Depends(get_current_user)
    # oder 403 Forbidden
    if resp.status_code == 401 or resp.status_code == 403:
        log("Unautorisierter Zugriff blockiert (401/403)", "PASS")
    else:
        # Falls Route nicht geschützt ist, ist das ein Security-Fail
        log(f"Sicherheitslücke: Zugriff ohne Token möglich! Code: {resp.status_code}", "FAIL")
    
    # B. Secrets Check (Environment)
    # Wir prüfen nicht die API, sondern lokal, ob .env existiert und geladen wird (simuliert)
    if os.environ.get("SECRET_KEY") or os.path.exists(".env"):
        log("Secrets via .env oder Environment konfiguriert", "PASS")
    else:
        log("Keine .env gefunden - Gefahr von Hardcoded Secrets?", "WARN")

def cleanup():
    print("\n--- CLEANUP ---")
    deleted_count = 0
    for tid in CREATED_TASK_IDS:
        if tid:
            r = requests.delete(f"{BASE_URL}/tasks/{tid}", headers=get_headers())
            if r.ok: deleted_count += 1
    log(f"{deleted_count} von {len(CREATED_TASK_IDS)} Test-Tasks bereinigt.", "INFO")

if __name__ == "__main__":
    print(f"Starte Systemtests gegen {BASE_URL}...")
    
    # Wir müssen uns erst authentifizieren
    if get_auth_token():
        test_backend_performance()
        test_task_lifecycle()
        test_filtering()
        test_ai_robustness()
        test_security()
        cleanup()
    else:
        print("Tests abgebrochen wegen Auth-Fehler. (Stelle sicher, dass der Server läuft!)")
