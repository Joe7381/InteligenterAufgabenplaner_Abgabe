import sys
import os
from datetime import datetime, timedelta

# Add current directory to path
sys.path.append(os.getcwd())

from main import execute_suggest_action
from database import SessionLocal
from task_models import TaskDB

def test_calendar_order():
    user_id = 1
    prompt = "Wann habe ich Zeit nächste Woche"
    
    print(f"--- Simuliere Anfrage: '{prompt}' ---")
    
    # We catch the output of execute_suggest_action (which returns the SYSTEM-INFO string)
    try:
        system_info = execute_suggest_action(prompt, user_id)
        print("--- SYSTEM-INFO Generated ---")
        print(system_info)
        print("-----------------------------")
        
        # Simple check if dates appear in order
        lines = system_info.split('\n')
        dates = []
        for line in lines:
            if "SYSTEM-INFO" in line or "KALENDERWOCHE" in line:
                continue
            # Try to extract date like "Montag (26.01.)" or similar
            # The format in main.py is: f"- {wd_name} ({date_str}): ..."
            if "(" in line and ")" in line:
                try:
                    part = line.split('(')[1].split(')')[0] # e.g. "26.01."
                    # parse day.month.
                    day, month = part.split('.')[:2]
                    # assume current year or close
                    dt = datetime(datetime.now().year, int(month), int(day))
                    # Handle year wrap if needed (not strictly needed for simple sort check)
                    dates.append(dt)
                except:
                    pass
        
        # Check sorted
        is_sorted = all(dates[i] <= dates[i+1] for i in range(len(dates)-1))
        
        if is_sorted:
            print(f"✅ SUCCESS: {len(dates)} Datumseinträge gefunden und sie sind chronologisch sortiert.")
            for d in dates:
                print(f"  - {d.strftime('%d.%m.')}")
        else:
            print("❌ FAILURE: Einträge sind NICHT sortiert!")
            for d in dates:
                print(f"  - {d.strftime('%d.%m.')}")

    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    test_calendar_order()
