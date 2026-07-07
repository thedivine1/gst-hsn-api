import os

raw_file = r"C:\Users\chaitanya.patankar\gst-hsn-api\scratch\raw_clipboard.txt"
scratch_dir = r"C:\Users\chaitanya.patankar\gst-hsn-api\scratch"

if not os.path.exists(raw_file):
    print("Error: raw_clipboard.txt does not exist!")
    exit(1)

with open(raw_file, "r", encoding="utf-8-sig") as f:
    content = f.read()

print(f"Total clipboard character length: {len(content)}")

# Split by '<!DOCTYPE html>'
parts = content.split("<!DOCTYPE html>")
print(f"Parts split by <!DOCTYPE html>: {len(parts)}")

articles = []
for i, part in enumerate(parts):
    if not part.strip():
        continue
    # Add back the DOCTYPE
    art = "<!DOCTYPE html>\n" + part.strip()
    articles.append(art)

print(f"Extracted {len(articles)} articles.")

# Write them to files
for idx, art in enumerate(articles):
    out_path = os.path.join(scratch_dir, f"clipboard_article_{idx+1}.html")
    with open(out_path, "w", encoding="utf-8") as out_f:
        out_f.write(art)
    print(f"Wrote clipboard article {idx+1} to {out_path} (length: {len(art)})")
