import re

text = "termin am 12.01.2026 um 14:00 uhr zahnarzt"
# Old regex
old_regex = r"(\d{1,2})[:\.](\d{2})(?!\.)"
# New regex
new_regex = r"(?<![\d\.])(\d{1,2})[:\.](\d{2})(?!\.)"

print(f"Text: {text}")

print("--- Old Regex ---")
matches = re.finditer(old_regex, text)
for m in matches:
    print(f"Match: {m.group(0)} at {m.start()}")

print("--- New Regex ---")
matches = re.finditer(new_regex, text)
for m in matches:
    print(f"Match: {m.group(0)} at {m.start()}")
