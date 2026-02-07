import pytest
from fastapi.testclient import TestClient
from main import app
from routers.auth import UserCreate
import uuid

# --- Setup ---
# Wir nutzen eine separate DB oder mocken sie idealerweise. 
# Für diesen schnellen "Smoke Test" nutzen wir die existierende, 
# erstellen aber einen Random User, damit wir keine Konflikte haben.

# client = TestClient(app)
# Create a test client with a trusted host (Host header matching TrustedHostMiddleware)
client = TestClient(app, base_url="http://localhost:8000")

def create_random_user():
    """Hilfsfunktion: Erstellt einen User mit zufälliger E-Mail."""
    unique_email = f"test_{uuid.uuid4()}@example.com"
    password = "testpassword123"
    
    # 1. Register
    reg_response = client.post("/register", json={"email": unique_email, "password": password})
    assert reg_response.status_code == 200
    
    # 2. Login & Token holen
    login_response = client.post("/login", json={"email": unique_email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    return token, unique_email

# --- Funktionale Tests ---

def test_create_and_read_task():
    """
    Testet den gesamten Lebenszyklus einer Aufgabe:
    1. User erstellen & einloggen
    2. Aufgabe erstellen (POST /tasks)
    3. Aufgaben liste abrufen (GET /tasks)
    4. Prüfen, ob die erstellte Aufgabe in der Liste ist.
    """
    try:
        token, email = create_random_user()
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Aufgabe erstellen
        task_data = {
            "title": "Funktionaler Test Task",
            "description": "Erstellt durch pytest",
            "priority": 2,
            "color": "rot"
        }
        
        create_res = client.post("/tasks", json=task_data, headers=headers)
        assert create_res.status_code == 200, f"Task Creation failed: {create_res.text}"
        created_task = create_res.json()
        
        assert created_task["title"] == "Funktionaler Test Task"
        assert created_task["id"] is not None
        task_id = created_task["id"]
        
        # 3. Liste abrufen
        get_res = client.get("/tasks", headers=headers)
        assert get_res.status_code == 200
        tasks = get_res.json()
        
        # 4. Prüfen
        # Liste filtern nach unserer ID (falls DB noch alte Daten hat)
        found_task = next((t for t in tasks if t["id"] == task_id), None)
        assert found_task is not None, "Erstellte Aufgabe wurde in der Liste nicht gefunden!"
        assert found_task["title"] == "Funktionaler Test Task"
        
        print("\n[SUCCESS] Task Creation & Reading verifiziert.")
        
    except Exception as e:
        pytest.fail(f"Test failed logic: {e}")

def test_task_done_workflow():
    """
    Testet das Erledigen einer Aufgabe:
    1. Aufgabe erstellen
    2. Als erledigt markieren (POST /tasks/{id}/done)
    3. Prüfen, ob status 'done' ist.
    """
    token, _ = create_random_user()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Erstellen
    create_res = client.post("/tasks", json={"title": "To Do Task"}, headers=headers)
    task_id = create_res.json()["id"]
    
    # Als Done markieren
    done_res = client.post(f"/tasks/{task_id}/done", headers=headers)
    assert done_res.status_code == 200
    
    # Prüfen
    # Wir laden die Liste neu oder den spezifischen Task (falls Endpoint vorhanden)
    # Hier nehmen wir die Liste
    get_res = client.get("/tasks", headers=headers)
    tasks = get_res.json()
    my_task = next(t for t in tasks if t["id"] == task_id)
    
    assert my_task["done"] is True, "Aufgabe sollte als DONE markiert sein."
    print("\n[SUCCESS] Task Done Workflow verifiziert.")

