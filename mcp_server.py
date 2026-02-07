from mcp.server.fastmcp import FastMCP
from database import SessionLocal
from task_models import TaskDB
from datetime import datetime, timedelta
from sqlalchemy import and_

# Initialize FastMCP server
mcp = FastMCP("IntelligenterKalender")

@mcp.tool()
def check_availability(start_date_str: str = None, days: int = 7) -> str:
    """
    Prüft den Kalender auf Termine ab einem bestimmten Datum.
    Args:
        start_date_str: Startdatum im Format 'YYYY-MM-DD'. Wenn leer, wird heute genommen.
        days: Anzahl der zu prüfenden Tage (Standard: 7)
    Returns:
        Ein String mit der Liste der Termine oder einer Meldung, dass alles frei ist.
    """
    db = SessionLocal()
    try:
        if start_date_str:
            try:
                start = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                return "Fehler: Datum muss im Format 'YYYY-MM-DD' sein."
        else:
            start = datetime.now()
            
        end = start + timedelta(days=days)
        
        # Suche alle Tasks in diesem Zeitraum
        tasks = db.query(TaskDB).filter(
            and_(
                TaskDB.deadline >= start,
                TaskDB.deadline <= end,
                TaskDB.done == False
            )
        ).order_by(TaskDB.deadline).all()
        
        if not tasks:
            return f"Der Kalender ist vom {start.strftime('%d.%m.%Y')} für {days} Tage komplett leer."
            
        report = f"Termine vom {start.strftime('%d.%m.%Y')} bis {end.strftime('%d.%m.%Y')}:\n"
        for t in tasks:
            dt_str = t.deadline.strftime("%d.%m. %H:%M")
            report += f"- {dt_str}: {t.title} (Prio: {t.priority})\n"
            
        return report
    except Exception as e:
        return f"Fehler beim Lesen des Kalenders: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def add_calendar_entry(title: str, date_time_iso: str, description: str = "") -> str:
    """
    Trägt einen neuen Termin ein.
    Args:
        title: Titel des Termins
        date_time_iso: Datum und Zeit im Format 'YYYY-MM-DD HH:MM'
        description: Optionale Beschreibung
    """
    db = SessionLocal()
    try:
        try:
            dt = datetime.strptime(date_time_iso, "%Y-%m-%d %H:%M")
        except ValueError:
            return "Fehler: Datum muss im Format 'YYYY-MM-DD HH:MM' sein."

        new_task = TaskDB(
            title=title,
            deadline=dt,
            description=description,
            priority=1,
            done=False,
            user_id=1 # Standard-User für MCP
        )
        db.add(new_task)
        db.commit()
        return f"Erfolg: '{title}' wurde für {dt.strftime('%d.%m.%Y %H:%M')} eingetragen."
    except Exception as e:
        return f"Fehler beim Speichern: {str(e)}"
    finally:
        db.close()

if __name__ == "__main__":
    mcp.run()
