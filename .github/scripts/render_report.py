"""Render the generated security Markdown tables as a standalone HTML report."""

import html
import re
import sys
from pathlib import Path
from time import gmtime, strftime


def inline(text):
    escaped = html.escape(html.unescape(text))
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def render(source):
    parts = []
    in_table = False
    header = False
    title = "Security scan report"
    for line in source.splitlines():
        line = line.strip()
        if in_table and not line.startswith("|"):
            parts.append("</tbody></table></div>")
            in_table = False
        if line.startswith("|"):
            cells = [value.strip() for value in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", value) for value in cells):
                continue
            if not in_table:
                parts.append('<div class="table-wrap"><table><thead>')
                in_table = True
                header = True
            tag = "th" if header else "td"
            row = []
            for value in cells:
                text = inline(value)
                status = html.unescape(value).upper()
                if not header and status in {"OK", "PASSED", "PASS", "ERROR", "FAILED", "HIGH", "CRITICAL", "WARN", "WARNING"}:
                    colour = "good" if status in {"OK", "PASSED", "PASS"} else "warn" if status in {"WARN", "WARNING"} else "bad"
                    text = f'<span class="badge {colour}">{text}</span>'
                row.append(f"<{tag}>{text}</{tag}>")
            parts.append("<tr>" + "".join(row) + "</tr>")
            if header:
                parts.append("</thead><tbody>")
                header = False
        elif line.startswith("## "):
            title = html.unescape(line[3:])
            parts.append(f'<h1>{inline(line[3:])}</h1>')
        elif line.startswith("### "):
            parts.append(f"<h2>{inline(line[4:])}</h2>")
        elif line:
            parts.append(f"<p>{inline(line)}</p>")
    if in_table:
        parts.append("</tbody></table></div>")
    timestamp = strftime("%Y-%m-%d %H:%M UTC", gmtime())
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + html.escape(title) + """</title>
<style>
:root { color-scheme: light; font-family: system-ui, sans-serif; color: #17243b; background: #edf2f8; }
* { box-sizing: border-box; }
body { margin: 0; padding: 36px 18px; }
main { max-width: 1200px; margin: auto; background: white; border-radius: 18px; padding: clamp(20px, 4vw, 48px); box-shadow: 0 12px 40px #17243b12; border-top: 7px solid #6366f1; }
h1 { margin-top: 0; font-size: clamp(26px, 4vw, 38px); color: #263b80; }
h2 { margin-top: 32px; font-size: 21px; }
p { line-height: 1.7; color: #52627b; }
.meta { font-size: 13px; color: #64748b; border-bottom: 1px solid #e2e8f0; padding-bottom: 18px; }
.table-wrap { overflow-x: auto; border: 1px solid #dce4ef; border-radius: 10px; margin: 16px 0 24px; }
table { width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }
th { background: #263b80; color: white; padding: 13px 16px; white-space: nowrap; }
td { padding: 13px 16px; border-top: 1px solid #e2e8f0; overflow-wrap: anywhere; min-width: 80px; vertical-align: top; }
tbody tr:nth-child(even) { background: #f4f7fc; }
tbody tr:hover { background: #edf0ff; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 999px; font-weight: 700; font-size: 12px; }
.good { background: #dcfce7; color: #166534; }
.bad { background: #fee2e2; color: #991b1b; }
.warn { background: #fef3c7; color: #92400e; }
@media print { body { padding: 0; background: white; } main { box-shadow: none; } th { color: #17243b; background: #edf2f8; } }
</style></head><body><main>
""" + f'<div class="meta">SECURITY REPORT · Generated {timestamp}</div>\n' + "\n".join(parts) + "\n</main></body></html>\n"


if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.with_suffix(".html").write_text(render(path.read_text(encoding="utf-8")), encoding="utf-8")
