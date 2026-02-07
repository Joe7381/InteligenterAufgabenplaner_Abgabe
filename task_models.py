from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from models import Base
from encryption import EncryptedString

class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    # Sensible Daten werden verschlüsselt gespeichert!
    title = Column(EncryptedString, nullable=False)
    description = Column(EncryptedString)
    deadline = Column(DateTime)
    priority = Column(Integer, default=1)
    done = Column(Boolean, default=False)
    project_id = Column(Integer)
    recurrence = Column(String)
    color = Column(String)
    # Notizen auch verschlüsseln
    notes = Column(EncryptedString)
    custom_fields = Column(String)  # JSON als String speichern
    attachments = Column(String)    # Dateinamen/URLs als String speichern
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="tasks")
