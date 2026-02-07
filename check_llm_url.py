import os
import requests
from dotenv import load_dotenv

load_dotenv()

lm_url = os.environ.get("LM_STUDIO_URL")
print(f"Testing URL: {lm_url}")

try:
    print(f"Testing URL: {lm_url}")
    
    import httpx
    try:
        # Lower-level connection check
        print(f"Pinging {lm_url}/models with 5s timeout...")
        resp = httpx.get(f"{lm_url}/models", timeout=5.0)
        print(f"Status Code: {resp.status_code}")
    except Exception as e:
        print(f"HTTPX Check Failed: {e}")

    # OpenAI Client Check
    from openai import OpenAI
    client = OpenAI(base_url=lm_url, api_key="lm-studio", timeout=60.0)
    
    print("Attempting chat completion...")
    completion = client.chat.completions.create(
        model="local-model", # Usually ignored by LM Studio but required
        messages=[
            {"role": "system", "content": "Always answer in one word."},
            {"role": "user", "content": "Hello!"}
        ],
        temperature=0.7,
    )
    print(f"Response: {completion.choices[0].message.content}")

except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
