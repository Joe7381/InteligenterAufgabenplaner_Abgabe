import requests
import json
import sys

def ask_model_identity():
    url = "http://localhost:1234/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    
    # First, get the model ID dynamically (as the main app does)
    try:
        models_resp = requests.get("http://localhost:1234/v1/models")
        model_id = models_resp.json()["data"][0]["id"]
        print(f"Server says model ID is: {model_id}")
    except:
        model_id = "unknown"
        print("Could not fetch model ID, trying generic...")

    data = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Which AI model are you? Please state your name and version exactly."}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }

    try:
        print("Sending 'Who are you?' to the model...")
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            print("\n--- MODEL ANSWER ---")
            print(answer)
            print("--------------------")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    ask_model_identity()
