import os
import requests
import sys

def check_remote_connection():
    print("--- CHECKING CONNECTION CONFIGURATION ---")
    
    # 1. Read .env file manually to see EXACTLY what is written on disk
    env_path = os.path.join(os.getcwd(), ".env")
    url_from_file = None
    
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("LM_STUDIO_URL="):
                    url_from_file = line.split("=", 1)[1].strip()
                    break
    
    if not url_from_file:
        print("❌ ERROR: Could not find 'LM_STUDIO_URL' in .env file!")
        return

    print(f"📍 URL found in .env:  '{url_from_file}'")
    
    if "localhost" in url_from_file or "127.0.0.1" in url_from_file:
        print("⚠️ WARNING: This URL points to your LOCAL computer (localhost).")
        print("   If you want to connect to another server, change the IP in .env!")
    else:
        print("✅ GOOD: This looks like a remote/network address.")

    # 2. Try to connect
    target_url = url_from_file
    if target_url.endswith("/"): target_url = target_url[:-1]
    
    # Construct models endpoint
    if not target_url.endswith("/v1"):
         models_url = f"{target_url}/v1/models"
    else:
         models_url = f"{target_url}/models"

    print(f"\n📡 Attempting to connect to: {models_url} ...")
    
    try:
        resp = requests.get(models_url, timeout=5.0)
        
        if resp.status_code == 200:
            print("✅ CONNECTION SUCCESSFUL!")
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                print(f"   Loaded Model ID on Remote Server: '{data['data'][0]['id']}'")
            else:
                print("   Connected, but no models returned.")
        else:
            print(f"❌ CONNECTION FAILED: Server responded with Status Code {resp.status_code}")
            
    except Exception as e:
        print(f"❌ CONNECTION FAILED: Could not reach server.")
        print(f"   Error: {e}")
        print("\nPossible causes:")
        print("   1. The IP or Port is wrong.")
        print("   2. The Server (LM Studio) is not running.")
        print("   3. Firewall on the Server blocks port 1234.")
        print("   4. Server is listening on 'localhost' instead of '0.0.0.0' or specific IP.")

if __name__ == "__main__":
    check_remote_connection()
