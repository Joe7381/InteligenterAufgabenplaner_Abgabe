from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta

from database import TaskDB
from dependencies import get_db, get_current_user_id

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"]
)

COLOR_NAME_TO_HEX = {
    "grün": "#b2ffb2",
    "rot": "#ef4444",
    "blau": "#3b82f6",
    "gelb": "#eab308",
}

def color_name_to_hex(color_name: str) -> str:
    if not color_name: return None
    return COLOR_NAME_TO_HEX.get(color_name.lower(), color_name)

@router.get("")
def get_calendar_events(priority: Optional[int] = None, done: Optional[bool] = None, search: Optional[str] = None, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    events = []
    db_tasks = db.query(TaskDB).filter(TaskDB.user_id == user_id).all()
    for task in db_tasks:
        try:
            deadline = task.deadline
            if isinstance(deadline, str):
                try:
                    deadline = datetime.fromisoformat(deadline)
                except Exception:
                    deadline = None
            if deadline:
                if task.recurrence:
                    for i in range(5):
                        if task.recurrence == 'daily':
                            event_date = deadline + timedelta(days=i)
                        elif task.recurrence == 'weekly':
                            event_date = deadline + timedelta(weeks=i)
                        elif task.recurrence == 'monthly':
                            event_date = deadline + timedelta(days=30*i)
                        else:
                            event_date = deadline
                        events.append({
                            "id": f"{task.id}-{i}",
                            "title": task.title,
                            "start": event_date,
                            "end": event_date,
                            "description": task.description,
                            "project_id": task.project_id,
                            "priority": task.priority,
                            "done": task.done,
                            "color": task.color,
                            "color_hex": color_name_to_hex(task.color),
                            "recurrence": task.recurrence,
                            "notes": task.notes,
                            "custom_fields": task.custom_fields,
                            "attachments": task.attachments
                        })
                else:
                    events.append({
                        "id": task.id,
                        "title": task.title,
                        "start": deadline,
                        "end": deadline,
                        "description": task.description,
                        "project_id": task.project_id,
                        "priority": task.priority,
                        "done": task.done,
                        "color": task.color,
                        "color_hex": color_name_to_hex(task.color),
                        "recurrence": task.recurrence,
                        "notes": task.notes,
                        "custom_fields": task.custom_fields,
                        "attachments": task.attachments
                    })
        except Exception as e:
            continue
    
    if priority is not None:
        events = [e for e in events if e["priority"] == priority]
    if done is not None:
        events = [e for e in events if e["done"] == done]
    if search:
        search_lower = search.lower()
        events = [e for e in events if search_lower in e["title"].lower() or (e["description"] and search_lower in e["description"].lower())]
    return events
