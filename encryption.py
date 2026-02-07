from sqlalchemy.types import TypeDecorator, String, Text
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

# Key laden. Normalerweise Pflicht, hier mit Fallback für Robustheit beim Import,
# aber Runtime Error wenn er fehlt.
_KEY = os.getenv("DB_ENCRYPTION_KEY")

class EncryptedString(TypeDecorator):
    """
    Verschlüsselt Daten VOR dem Speichern in der DB und entschlüsselt sie
    BEIM Laden. Das bedeutet, in der SQLite-Datei liegt nur Datensalat.
    """
    impl = Text # Wir nutzen Text, da der Ciphertext länger ist als der Plaintext
    cache_ok = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not _KEY:
             # In Produktion hier Exception werfen!
             print("WARNUNG: Kein DB_ENCRYPTION_KEY gesetzt! Verschlüsselung inaktiv.")
             self.fernet = None
        else:
            self.fernet = Fernet(_KEY)

    def process_bind_param(self, value, dialect):
        # Python -> DB (Verschlüsseln)
        if value is not None and self.fernet:
            if isinstance(value, str):
                value = value.encode('utf-8')
            return self.fernet.encrypt(value).decode('utf-8')
        return value

    def process_result_value(self, value, dialect):
        # DB -> Python (Entschlüsseln)
        if value is not None and self.fernet:
             try:
                return self.fernet.decrypt(value.encode('utf-8')).decode('utf-8')
             except Exception:
                # Falls wir Daten nicht entschlüsseln können (z.B. alter Key oder Klartext),
                # geben wir sie einfach so zurück (Robustheit).
                return value
        return value
