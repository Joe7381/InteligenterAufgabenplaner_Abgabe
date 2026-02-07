from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
from jose import jwt
import os
from database import SessionLocal
from slowapi import Limiter
from slowapi.util import get_remote_address

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Auth Dependency ---
def get_current_user_id(token: str = Depends(lambda x: x)): 
    # Placeholder implementation, will utilize the logic from auth_router.py 
    # or main.py. To avoid circular imports, re-implementing clean logic here 
    # is often best, but for now we keep it simple.
    # In a full refactor, we would move the JWT decode logic here.
    # However, auth_router has it's own dependency injection.
    pass

# We duplicate the detailed logic here to extract it cleanly from main.py
def get_current_user_id_optional(authorization: Optional[str] = Header(None)) -> Optional[int]:
    """Try to decode Authorization header and return user_id or None if missing/invalid."""
    try:
        if not authorization:
            return None
        # header like: Bearer <token>
        parts = authorization.split()
        if len(parts) < 2:
            return None
        token = parts[1]
        
        # Get secret from env or auth_utils
        secret = os.environ.get("SECRET_KEY", "devsecret")
        # Try to import from auth_utils if available
        try:
             from auth_utils import SECRET_KEY as AU_SECRET
             secret = AU_SECRET
        except: pass

        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return int(payload.get("user_id")) if payload.get("user_id") is not None else None
    except Exception:
        return None

# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)
