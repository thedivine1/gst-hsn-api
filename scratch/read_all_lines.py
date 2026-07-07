import json

transcript_path = r"C:\Users\chaitanya.patankar\.gemini\antigravity-ide\brain\3568848f-ce58-49e3-8c92-6330bee7f6e5\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        try:
            data = json.loads(line)
            print(f"Line {idx}: step_index={data.get('step_index')}, source={data.get('source')}, type={data.get('type')}, length={len(line)}")
        except Exception as e:
            print(f"Line {idx}: error parsing: {e}")
