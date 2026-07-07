import os
import glob

paths_to_scan = [
    r"C:\Users\chaitanya.patankar\Downloads",
    r"C:\Users\chaitanya.patankar\Desktop",
    r"C:\Users\chaitanya.patankar\Documents",
    r"C:\Users\chaitanya.patankar\gst-hsn-api"
]

print("Scanning directories for GST articles...")
found = []

for base_path in paths_to_scan:
    if not os.path.exists(base_path):
        continue
    for root, dirs, files in os.walk(base_path):
        # Skip large directories or venv
        if "venv" in root or ".git" in root or "node_modules" in root or ".pytest_cache" in root or ".ruff_cache" in root:
            continue
        for file in files:
            if file.endswith((".html", ".txt", ".md", ".json", ".py", ".docx")):
                full_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(full_path)
                    if size > 5000000: # skip files > 5MB
                        continue
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "Compliance Time Bomb" in content or "Split GST Correctly" in content:
                            print(f"Match: {full_path} (size: {size})")
                            found.append((full_path, size))
                except Exception as e:
                    pass

print(f"Total matches: {len(found)}")
