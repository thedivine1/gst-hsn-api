import sys
import re

# 1. Fix UTF-8 characters
files_to_fix = [
    r'c:\Users\chaitanya.patankar\gst-hsn-api\docs.html',
    r'c:\Users\chaitanya.patankar\gst-hsn-api\dashboard.html',
    r'c:\Users\chaitanya.patankar\gst-hsn-api\main.py'
]

for file in files_to_fix:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if there is <meta charset="utf-8"> in HTML files
    if file.endswith('.html') and '<meta charset="utf-8">' not in content and '<meta charset' not in content:
        content = content.replace('<head>', '<head>\n  <meta charset="utf-8">')
    elif file.endswith('.html') and '<meta charset="UTF-8">' in content:
        pass

    # Replace the corrupted characters
    content = content.replace('â€”', '—')
    content = content.replace('â€"', '—')
    content = content.replace('â€“', '—')
    content = content.replace('â€', '—')
    
    # Fix twitter card
    if file.endswith('.py'):
        content = content.replace('content="summary"', 'content="summary_large_image"')
        # Add og:image if not exists
        if 'og:image' not in content:
            img_tag = '  <meta property="og:image" content="https://gstaccelerator.in/banner.png" />\n'
            content = content.replace('<meta name="twitter:card"', img_tag + '  <meta name="twitter:card"')

    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

print('Done')
