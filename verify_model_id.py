import os
import requests
import sys

def test_model_detection():
    print("Testing model auto-detection...")
    try:
        # Defaults
        base_url = "http://localhost:1234/v1"
        
        # Logic from main.py
        if base_url.endswith("/"): base_url = base_url[:-1]
        
        if not base_url.endswith("/v1"):
             models_url = f"{base_url}/v1/models"
        else:
             models_url = f"{base_url}/models"
             
        print(f"Querying: {models_url}")
        resp = requests.get(models_url, timeout=2.0)
        
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                loaded_id = data["data"][0]["id"]
                print(f"✅ SUCCESS! Found loaded model: '{loaded_id}'")
                print("This ID will now be used automatically by your chatbot.")
                return
            else:
                print("⚠️ Server reachable, but no data/models found in response.")
        else:
            print(f"❌ Server returned status code: {resp.status_code}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("Make sure LM Studio server is running on port 1234.")

if __name__ == "__main__":
    test_model_detection()
