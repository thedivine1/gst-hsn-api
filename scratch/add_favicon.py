import os

link_tag = '<link rel="icon" type="image/x-icon" href="/favicon.ico">'

for filename in os.listdir('.'):
    if filename.endswith('.html'):
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'favicon.ico' not in content and '<head>' in content:
            content = content.replace('<head>', f'<head>\n    {link_tag}')
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'Processed {filename}')
        else:
            print(f'Skipped {filename}')
