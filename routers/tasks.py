from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import TaskDB # Using database for models
from dependencies import get_db, get_current_user_id_optional
from routers.auth import get_current_user_id
from schemas import Task, TaskCreate
import ast

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"]
)

# Colors for mapping
COLOR_NAME_TO_HEX = {
    "rot": "#FF0000",
    "grün": "#00FF00",
    "blau": "#0000FF",
    "gelb": "#FFFF00",
}

@router.post("", response_model=Task)
async def create_task(task: TaskCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id), request: Request = None):
    # Docstring is preserved from main.py if needed, removed for brevity here
    try:
        if task.deadline:
            # Naive comparison
            if task.deadline.replace(tzinfo=None) < datetime.now().replace(tzinfo=None):
                raise HTTPException(status_code=400, detail="Termine können nicht in der Vergangenheit angelegt werden.")

        if task.color and task.color.startswith('#'):
            reverse_map = {v: k for k, v in COLOR_NAME_TO_HEX.items()}
            color_name = reverse_map.get(task.color.lower())
            if color_name:
                task.color = color_name
        db_task = TaskDB(
            title=task.title,
            description=task.description,
            deadline=task.deadline,
            priority=task.priority,
            done=task.done,
            project_id=task.project_id,
            recurrence=task.recurrence,
            color=task.color,
            notes=task.notes,
            custom_fields=str(task.custom_fields) if task.custom_fields else None,
            attachments=str(task.attachments) if task.attachments else None,
            user_id=user_id
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return Task(
            id=db_task.id,
            title=db_task.title,
            description=db_task.description,
            deadline=db_task.deadline,
            priority=db_task.priority,
            done=db_task.done,
            project_id=db_task.project_id,
            recurrence=db_task.recurrence,
            color=db_task.color,
            notes=db_task.notes,
            custom_fields=ast.literal_eval(db_task.custom_fields) if db_task.custom_fields else None,
            attachments=ast.literal_eval(db_task.attachments) if db_task.attachments else None
        )
    except Exception as e:
        # Catch basic DB errors
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[Task])
def read_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    tasks = db.query(TaskDB).filter(TaskDB.user_id == user_id).offset(skip).limit(limit).all()
    # Serialize manually to handle internal encryptions or dict fields
    results = []
    for t in tasks:
        results.append(Task(
            id=t.id,
            title=t.title,
            description=t.description,
            deadline=t.deadline,
            priority=t.priority,
            done=t.done,
            project_id=t.project_id,
            recurrence=t.recurrence,
            color=t.color,
            notes=t.notes,
            custom_fields=ast.literal_eval(t.custom_fields) if t.custom_fields else None,
            attachments=ast.literal_eval(t.attachments) if t.attachments else None
        ))
    return results

@router.put("/{task_id}", response_model=Task)
def update_task(task_id: int, task: TaskCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    db_task = db.query(TaskDB).filter(TaskDB.id == task_id, TaskDB.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Update logic
    if task.title is not None: db_task.title = task.title
    if task.description is not None: db_task.description = task.description
    if task.deadline is not None: db_task.deadline = task.deadline
    if task.priority is not None: db_task.priority = task.priority
    if task.done is not None: db_task.done = task.done
    if task.recurrence is not None: db_task.recurrence = task.recurrence
    if task.color is not None: db_task.color = task.color
    if task.notes is not None: db_task.notes = task.notes
    if task.custom_fields is not None: db_task.custom_fields = str(task.custom_fields)
    
    db.commit()
    db.refresh(db_task)
    return Task(
            id=db_task.id,
            title=db_task.title,
            description=db_task.description,
            deadline=db_task.deadline,
            priority=db_task.priority,
            done=db_task.done,
            project_id=db_task.project_id,
            recurrence=db_task.recurrence,
            color=db_task.color,
            notes=db_task.notes,
            custom_fields=ast.literal_eval(db_task.custom_fields) if db_task.custom_fields else None,
            attachments=ast.literal_eval(db_task.attachments) if db_task.attachments else None
        )

@router.post("/{task_id}/done")
def mark_task_done(task_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    db_task = db.query(TaskDB).filter(TaskDB.id == task_id, TaskDB.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db_task.done = True
    db.commit()
    return {"status": "success", "task_id": task_id, "done": True}

@router.post("/{task_id}/undone")
def mark_task_undone(task_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    db_task = db.query(TaskDB).filter(TaskDB.id == task_id, TaskDB.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db_task.done = False
    db.commit()
    return {"status": "success", "task_id": task_id, "done": False}

@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    db_task = db.query(TaskDB).filter(TaskDB.id == task_id, TaskDB.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    return {"detail": "Task deleted"}
