import sys

# Update main.py
with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('12,000+', '48,000+')
content = content.replace('12,000', '48,000')

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\main.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Update docs.html
with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\docs.html', 'r', encoding='utf-8') as f:
    content2 = f.read()

content2 = content2.replace('"total_hsn": 12054,', '"total_hsn": 48752,')
content2 = content2.replace('"total_sac": 845,', '"total_sac": 681,')

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\docs.html', 'w', encoding='utf-8') as f:
    f.write(content2)
