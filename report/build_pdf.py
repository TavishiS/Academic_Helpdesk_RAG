"""
Builds report/report.pdf from report/report.md (Markdown -> HTML -> PDF with headless Chrome).

  pip install markdown           # only needed for this script
  python report/build_pdf.py

Needs the `markdown` package and a Chrome/Chromium binary (google-chrome, chromium or chromium-browser).
The report has to fit on 4 pages; the script prints the page count and warns if it is more.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("Install the Markdown converter first:  pip install markdown")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "report" / "report.md"
OUT = ROOT / "report" / "report.pdf"
MAX_PAGES = 4

CSS = """
@page { size: A4; margin: 12mm 13mm 12mm 13mm; }
body { font-family: 'DejaVu Sans', 'Noto Sans', Arial, sans-serif; font-size: 9pt; line-height: 1.34; color: #1a1a1a; }
h1 { font-size: 17pt; margin: 0 0 3pt; border-bottom: 2px solid #333; padding-bottom: 2pt; }
h2 { font-size: 11.5pt; margin: 9pt 0 3pt; border-bottom: 1px solid #999; padding-bottom: 1pt; page-break-after: avoid; }
p { margin: 3pt 0; }
ul { margin: 2pt 0; padding-left: 13pt; }
li { margin: 1.5pt 0; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 7.9pt; background: #f1f1f1; padding: 0 1.5pt; border-radius: 2pt; overflow-wrap: anywhere; }
blockquote { margin: 3pt 0; padding: 2.5pt 7pt; border-left: 3px solid #888; background: #f6f6f6; color: #333; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 1pt; font-size: 7.9pt; }
th, td { border: 1px solid #b5b5b5; padding: 1.6pt 3.5pt; vertical-align: top; text-align: left; overflow-wrap: break-word; }
th { background: #e9edf2; }
table { page-break-inside: avoid; }
tr { page-break-inside: avoid; }
tbody tr:nth-child(even) td { background: #fafafa; }
em { color: #333; }
"""


def find_chrome():
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("No Chrome/Chromium found on the PATH.")


def main():
    body = markdown.markdown(SRC.read_text(), extensions=["tables", "fenced_code", "sane_lists"])
    html = (f"<!doctype html><html><head><meta charset='utf-8'><title>Academic Helpdesk Agent: Report</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "report.html"
        page.write_text(html)
        subprocess.run([find_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={OUT}", f"file://{page}"], check=True, capture_output=True, timeout=180)
    pages = None
    if shutil.which("pdfinfo"):
        info = subprocess.run(["pdfinfo", str(OUT)], capture_output=True, text=True).stdout
        pages = int(next(l.split()[1] for l in info.splitlines() if l.startswith("Pages:")))
    print(f"wrote {OUT.relative_to(ROOT)}" + (f" ({pages} pages)" if pages else ""))
    if pages and pages > MAX_PAGES:
        print(f"WARNING: {pages} pages, the limit is {MAX_PAGES}: shorten report/report.md")


if __name__ == "__main__":
    main()
