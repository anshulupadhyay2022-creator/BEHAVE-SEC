import sys
try:
    import pypdf
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
    import pypdf

reader = pypdf.PdfReader("10258088.pdf")
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n--- PAGE BREAK ---\n"

with open("pdf_extracted.txt", "w", encoding="utf-8") as f:
    f.write(text)

print("PDF Extracted successfully.")
