try:
    from encryption import EncryptedString
    print("Encryption loaded")
except Exception:
    import traceback
    traceback.print_exc()
