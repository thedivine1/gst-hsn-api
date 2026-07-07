import json

transcript_path = r"C:\Users\chaitanya.patankar\.gemini\antigravity-ide\brain\3568848f-ce58-49e3-8c92-6330bee7f6e5\.system_generated\logs\transcript_full.jsonl"
out_path = r"C:\Users\chaitanya.patankar\gst-hsn-api\scratch\second_user_input.txt"

user_inputs = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("source") == "USER_EXPLICIT" and data.get("type") == "USER_INPUT":
            user_inputs.append(data["content"])

print(f"Total user inputs found: {len(user_inputs)}")
if len(user_inputs) >= 2:
    last_input = user_inputs[-1]
    print(f"Last input length: {len(last_input)}")
    with open(out_path, "w", encoding="utf-8") as out_f:
        out_f.write(last_input)
    print(f"Wrote last user input to {out_path}")
else:
    print("Fewer than 2 user inputs found!")
