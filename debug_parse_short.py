import re
from datetime import datetime

def parse_date(text):
    text_lower = text.lower()
    now = datetime(2026, 1, 18) # Simulation date
    target_date = None

    print(f"Testing text: '{text_lower}'")

    # Versuch 1: DD.MM.YYYY oder DD.MM.
    # Regex from main.py
    date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.?(\d{2,4})?", text_lower)
    if date_match:
        print("Match regex 1:", date_match.groups())
        day, month = int(date_match.group(1)), int(date_match.group(2))
        try:
            year_grp = date_match.group(3)
            year = int(year_grp) if year_grp else now.year
            if year < 100: year += 2000
            target_date = datetime(year, month, day)
            print(f"Parsed Date 1: {target_date}")
        except Exception as e:
            print("Error 1:", e)
    else:
        print("No match regex 1")

    # Versuch 2: Nur DD. (z.B. "am 21.")
    day_match = re.search(r"\b(\d{1,2})\.(?!\d)", text_lower)
    if day_match:
        print("Match regex 2:", day_match.groups())
    
    return target_date

def main():
    parse_date("ich würde gerne am 5.2 schwimmen gehen")
    parse_date("am 5.2. schwimmen")
    parse_date("am 05.02 schwimmen")

if __name__ == "__main__":
    main()
