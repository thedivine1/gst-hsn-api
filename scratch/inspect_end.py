import json
import os

transcript_path = r"C:\Users\chaitanya.patankar\.gemini\antigravity-ide\brain\3568848f-ce58-49e3-8c92-6330bee7f6e5\.system_generated\logs\transcript_full.jsonl"
out_txt = r"C:\Users\chaitanya.patankar\gst-hsn-api\scratch\end_output.txt"

with open(transcript_path, "r", encoding="utf-8") as f:
    line = f.readline()
    data = json.loads(line)
    content = data["content"]

print(f"Content length: {len(content)}")
with open(out_txt, "w", encoding="utf-8") as out_f:
    out_f.write(content[-2000:])
print(f"Wrote last 2000 chars to {out_txt}")
