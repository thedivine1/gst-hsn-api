import zipfile
import re

docx_path = r"C:\Users\chaitanya.patankar\gst-hsn-api\gst_related.docx"

try:
    with zipfile.ZipFile(docx_path) as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
        # Strip XML tags to get raw text
        text = re.sub(r'<[^>]+>', '', doc_xml)
        print(f"Docx raw text length: {len(text)}")
        print("First 1000 characters:")
        print(text[:1000])
        print("\nLast 1000 characters:")
        print(text[-1000:])
        
        # Look for titles or sections
        # e.g., "GST API vs Manual HSN Lookup"
        print("\nMatches for 'article' or titles:")
        matches = re.findall(r'.{0,50}(?:GST API|Manual HSN|CGST, SGST|compliance).{0,50}', text, re.IGNORECASE)
        for m in matches[:10]:
            print(f"- {m}")
except Exception as e:
    print(f"Error reading docx: {e}")
