import sys
try:
    import database
    print("Attributes:", dir(database))
    from database import SessionLocal
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
