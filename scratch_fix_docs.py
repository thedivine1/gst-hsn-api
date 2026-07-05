import re

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\docs.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Check for charset
if not re.search(r'<meta charset=[\'\"]?utf-8[\'\"]?', text, re.IGNORECASE):
    text = text.replace('<head>', '<head>\n  <meta charset=\"UTF-8\">')

# Fix title
text = re.sub(r'<title>.*?</title>', '<title>API Docs - GST Accelerator</title>', text)

# Fix body broken characters
text = text.replace('â€“', '-')
text = text.replace('â†’', '→')
text = text.replace('â‚¹', '₹')

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\docs.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Fixed docs.html encoding bugs.')
