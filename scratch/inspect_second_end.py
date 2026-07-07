with open(r"C:\Users\chaitanya.patankar\gst-hsn-api\scratch\second_user_input.txt", "r", encoding="utf-8") as f:
    text = f.read()

print(f"Total length: {len(text)}")
print("--- LAST 1000 CHARACTERS ---")
# Use safe printing to avoid encoding error in terminal
print(text[-1000:].encode("ascii", errors="replace").decode("ascii"))
