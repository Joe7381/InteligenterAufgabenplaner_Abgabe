from database import SessionLocal, TaskDB
from datetime import datetime

db = SessionLocal()
tasks = db.query(TaskDB).all()
print(f"Total tasks: {len(tasks)}")
for t in tasks:
    print(f"ID: {t.id} | Title: {t.title} | Deadline: {t.deadline} | Recurrence: {t.recurrence}")
db.close()
