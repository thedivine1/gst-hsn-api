import sys

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

contact_route = '''@app.get("/contact", include_in_schema=False, response_class=HTMLResponse)
async def serve_contact():
    try:
        with open("contact.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Contact template not found.")

'''

# Insert it before the /terms route
content = content.replace('@app.get("/terms", include_in_schema=False, response_class=HTMLResponse)', contact_route + '@app.get("/terms", include_in_schema=False, response_class=HTMLResponse)')

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\main.py', 'w', encoding='utf-8') as f:
    f.write(content)
