from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
import bleach

# --- Chat Models ---
class ChatRequest(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: Optional[str] = None
    auto_created_task_id: Optional[int] = None
    intent: Optional[str] = None

# --- Task Models ---
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Optional[int] = 1  # 1 = niedrig, 2 = mittel, 3 = hoch
    done: bool = False
    project_id: Optional[int] = None
    recurrence: Optional[str] = None  # z.B. 'daily', 'weekly', 'monthly'
    color: Optional[str] = None  # "rot", "grün", "gelb", "blau" (immer NUR Name, nie Hex!)
    notes: Optional[str] = None  # Notizen
    custom_fields: Optional[dict] = None  # Benutzerdefinierte Felder
    attachments: Optional[List[str]] = None  # Dateinamen/URLs

    @field_validator('title', 'description', 'notes', 'recurrence', 'color')
    @classmethod
    def sanitize_input(cls, v: Optional[str]) -> Optional[str]:
        if v:
            # Bleach entfernt alle HTML-Tags (tags=[]) und Attribute
            return bleach.clean(v, tags=[], attributes={}, strip=True)
        return v

class Task(TaskCreate):
    id: int
