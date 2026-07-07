import json
import os

transcript_path = r"C:\Users\chaitanya.patankar\.gemini\antigravity-ide\brain\3568848f-ce58-49e3-8c92-6330bee7f6e5\.system_generated\logs\transcript_full.jsonl"
scratch_dir = r"C:\Users\chaitanya.patankar\gst-hsn-api\scratch"

if not os.path.exists(scratch_dir):
    os.makedirs(scratch_dir)

with open(transcript_path, "r", encoding="utf-8") as f:
    line = f.readline()
    data = json.loads(line)
    content = data["content"]

# Let's split by '<!DOCTYPE html>'
# Note: the first part might be the preamble (the text before the first HTML article).
parts = content.split("<!DOCTYPE html>")

print(f"Number of parts found: {len(parts)}")

articles = []
for i, part in enumerate(parts):
    # The first element before '<!DOCTYPE html>' is the preamble, skip it if it doesn't contain HTML tags.
    if i == 0 and "html" not in part.lower():
        continue
    if not part.strip():
        continue
    # Add the <!DOCTYPE html> back
    article_content = "<!DOCTYPE html>\n" + part.strip()
    # Let's clean up any trailing user request tags if they exist
    if "</USER_REQUEST>" in article_content:
        article_content = article_content.split("</USER_REQUEST>")[0].strip()
    
    articles.append(article_content)
    
    out_path = os.path.join(scratch_dir, f"article_{len(articles)}.html")
    with open(out_path, "w", encoding="utf-8") as out_f:
        out_f.write(article_content)
    print(f"Wrote article {len(articles)} to {out_path} (length: {len(article_content)})")
