import os

base_path = r"C:\Users\chaitanya.patankar"
print("Scanning entire home directory for 'GST on Health Insurance'...")

found = []
ignored_dirs = {
    "venv", ".git", "node_modules", ".pytest_cache", ".ruff_cache",
    "AppData", "Local", "Roaming", ".gemini"
}

for root, dirs, files in os.walk(base_path):
    dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
    for file in files:
        if file.endswith((".html", ".txt", ".md", ".json", ".py", ".docx")):
            full_path = os.path.join(root, file)
            if "gst-hsn-api\\scratch" in full_path:
                continue
            try:
                size = os.path.getsize(full_path)
                if size > 5000000:
                    continue
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "GST on Health Insurance" in content or "health-insurance" in content:
                        print(f"Match: {full_path} (size: {size})")
                        found.append(full_path)
            except Exception as e:
                pass

print(f"Total matches: {len(found)}")
