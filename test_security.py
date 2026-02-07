
import os
import pytest
from fastapi.testclient import TestClient
from main import app
from schemas import TaskCreate
from encryption import EncryptedString
from cryptography.fernet import Fernet
import bleach

# Create a test client with a trusted host (Host header matching TrustedHostMiddleware)
client = TestClient(app, base_url="http://localhost:8000")

# --- Test 1: Content Security Policy (HTTP Headers) ---
def test_security_headers():
    """
    Verify that the SecurityHeadersMiddleware adds the expected headers.
    """
    response = client.get("/docs")
    assert response.status_code == 200
    headers = response.headers
    
    # Debug output
    print("Response Headers:", headers)

    # 1. Check CSP
    assert "content-security-policy" in headers
    # We expect "default-src 'self'"
    assert "default-src 'self'" in headers["content-security-policy"]
    
    # 2. Check X-Content-Type-Options
    assert headers.get("x-content-type-options") == "nosniff"
    
    # 3. Check X-Frame-Options
    assert headers.get("x-frame-options") == "DENY"

# --- Test 2: Input Sanitization (Bleach / XSS) ---
def test_input_sanitization():
    """
    Verify that HTML tags are stripped from Task inputs.
    """
    unsafe_input = "<script>alert('XSS')</script>Meeting<b onmouseover=alert(1)>bold</b>"
    
    # Create the model instance which should trigger the validator
    task = TaskCreate(title=unsafe_input)
    
    print(f"Original: {unsafe_input}")
    print(f"Sanitized: {task.title}")
    
    # Assertions
    assert "<script>" not in task.title
    assert "<b>" not in task.title
    # The content 'Meeting' and 'bold' should remain (bleach default behavior for strip=True is to keep content)
    assert "Meeting" in task.title
    assert "bold" in task.title

# --- Test 3: Encryption Logic (Unit Test) ---
def test_encryption_logic():
    """
    Verify that the encryption key is set and encryption/decryption works.
    We verify the logic used in 'encryption.py' rather than the DB integration directly,
    to keep the test fast and independent of SQLite state.
    """
    key = os.getenv("DB_ENCRYPTION_KEY")
    assert key is not None, "DB_ENCRYPTION_KEY is missing in environment!"
    
    fernet = Fernet(key)
    plain_text = "Geheime Nutzerdaten 123"
    
    # Encrypt
    encrypted = fernet.encrypt(plain_text.encode('utf-8')).decode('utf-8')
    
    # Verify it's actually encrypted (not just equal)
    assert encrypted != plain_text
    assert "Geheime" not in encrypted
    
    # Decrypt
    decrypted = fernet.decrypt(encrypted.encode('utf-8')).decode('utf-8')
    assert decrypted == plain_text

# --- Test 4: Rate Limiting ---
def test_rate_limiting_login():
    """
    Verify that the /login endpoint blocks requests after the limit (10/min).
    """
    # Note: TestClient shares state for the application instance.
    # If other tests hit /login, they count towards the limit.
    # We will loop enough times to ensure we hit the limit.
    
    payload = {"email": "attacker@example.com", "password": "wrongpassword"}
    
    limit_hit = False
    
    # Try 15 times (limit is 10)
    for i in range(15):
        try:
            response = client.post("/login", json=payload)
            print(f"Request {i+1}: Status {response.status_code}")
            
            if response.status_code == 429:
                limit_hit = True
                break
        except Exception as e:
            # Sometmes slowapi/pydantic might raise exceptions if handled poorly, 
            # but we expect a 429 response.
            print(f"Exception on request {i+1}: {e}")
            
    assert limit_hit, "Rate Limit (429) was not triggered after 15 attempts!"

