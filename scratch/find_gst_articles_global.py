import os

base_path = r"C:\Users\chaitanya.patankar"
print("Scanning entire home directory for 'Compliance Time Bomb'...")

found = []
ignored_dirs = {
    "venv", ".git", "node_modules", ".pytest_cache", ".ruff_cache",
    "AppData", "Local", "Roaming", ".gemini"
}

for root, dirs, files in os.walk(base_path):
    # Prune ignored directories to speed up search
    dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
    
    for file in files:
        # Check text-like files and Word/PDF if simple
        if file.endswith((".html", ".txt", ".md", ".json", ".py", ".docx", ".js", ".ts", ".tsx", ".jsx", ".css")):
            full_path = os.path.join(root, file)
            # Skip files we just created in the scratch directory to avoid noise
            if "gst-hsn-api\\scratch" in full_path:
                continue
            try:
                size = os.path.getsize(full_path)
                if size > 5000000: # skip files > 5MB
                    continue
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "Compliance Time Bomb" in content:
                        print(f"Match found: {full_path} (size: {size})")
                        found.append(full_path)
            except Exception as e:
                pass

print(f"Total matches: {len(found)}")
