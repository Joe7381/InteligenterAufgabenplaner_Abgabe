from sqlalchemy.orm import Session
from database import SessionLocal
from models import User

def check_user_one():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if user:
            print(f"User ID 1 Info:")
            print(f"Email: {user.email}")
            print(f"Hashed Password: {user.hashed_password} (Passwörter sind verschlüsselt und können nicht direkt ausgelesen werden)")
        else:
            print("User ID 1 nicht gefunden!")
    finally:
        db.close()

if __name__ == "__main__":
    check_user_one()
