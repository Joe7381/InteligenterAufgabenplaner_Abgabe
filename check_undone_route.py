
import requests

API_URL = "http://localhost:8000"

# Assuming you have a user and token, but for now let's just create a user or use existing
# Just check if the endpoint is 404 or 401.

def test_undone_endpoint_existence():
    # We don't have a token readily available to run against the live server easily without login flow,
    # but we can check if the route is registered in FastAPI app.
    from main import app
    
    found = False
    for route in app.routes:
        if route.path == "/tasks/{task_id}/undone" and "POST" in route.methods:
            found = True
            print("Endpoint /tasks/{task_id}/undone FOUND.")
            break
    
    if not found:
        print("Endpoint /tasks/{task_id}/undone NOT found.")

if __name__ == "__main__":
    test_undone_endpoint_existence()
