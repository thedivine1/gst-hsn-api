import os
import glob
import json

brain_dir = r"C:\Users\chaitanya.patankar\.gemini\antigravity-ide\brain"
print("Scanning brain directory...")

matches = []

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file.endswith(".html") or file.endswith(".jsonl") or file.endswith(".md"):
            path = os.path.join(root, file)
            try:
                # check size to avoid reading massive files
                size = os.path.getsize(path)
                if size > 10000000: # skip >10MB
                    continue
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "Why Hardcoding GST Rates Is a Compliance Time Bomb" in content:
                        print(f"Found match in {path} (size: {size})")
                        matches.append((path, size))
            except Exception as e:
                pass

print(f"Total matches found: {len(matches)}")
