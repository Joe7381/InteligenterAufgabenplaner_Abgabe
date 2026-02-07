from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import User
from database import SessionLocal
from auth_utils import hash_password, verify_password
from jose import jwt
import os
from dotenv import load_dotenv

# Rate Limiting Imports
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "devsecret" 
ALGORITHM = os.getenv("ALGORITHM", "HS256")

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Registriert einen neuen Benutzer im System.
    
    Prüft, ob die E-Mail bereits existiert und speichert das Passwort sicher gehasht (bcrypt).

    Args:
        user (UserCreate): Objekt mit E-Mail und Klartext-Passwort.
        db (Session): Datenbank-Session.

    Returns:
        dict: Erfolgsmeldung {"msg": "Registrierung erfolgreich"}
    
    Raises:
        HTTPException(400): Wenn die E-Mail bereits vergeben ist.
    """
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="E-Mail bereits registriert")
    hashed = hash_password(user.password)
    db_user = User(email=user.email, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"msg": "Registrierung erfolgreich"}

@router.post("/login")
@limiter.limit("10/minute") # Max 10 Login-Versuche pro Minute (Brute Force Schutz)
def login(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    """
    Authentifiziert einen Benutzer und stellt ein JWT Access Token aus.
    
    Implementiert Rate Limiting (10 Versuche/Min) durch `slowapi` zum Schutz vor Brute-Force-Angriffen.

    Args:
        request (Request): Das Request-Objekt (benötigt für IP-basiertes Rate Limiting).
        user (UserCreate): Login-Daten (E-Mail, Passwort).
        db (Session): Datenbank-Session.

    Returns:
        dict: Enthält das JWT Token ("access_token") und den Typ ("bearer").

    Raises:
        HTTPException(401): Bei falscher E-Mail oder falschem Passwort.
    """
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Falsche Zugangsdaten")
    # Token enthält jetzt auch die E-Mail-Adresse
    token = jwt.encode({"user_id": db_user.id, "email": db_user.email}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user_id(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
