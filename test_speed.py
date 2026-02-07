import time
import requests
import json

url = "http://localhost:8000/chat"
payload = {
    "prompt": "morgen 19:00 Abendessen",
    "conversation_id": "test-speed-2"
}
headers = {
    "Content-Type": "application/json"
}

print(f"Sending request to {url} with payload: {payload}")
start_time = time.time()
try:
    response = requests.post(url, json=payload, headers=headers)
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Status Code: {response.status_code}")
    print(f"Time taken: {duration:.4f} seconds")
    
    if response.status_code == 200:
        data = response.json()
        print("Response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("Error response:", response.text)
        
except Exception as e:
    print(f"Request failed: {e}")
