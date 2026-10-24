"""Render the scan's exact JSON findings and enforce the image gate."""
import html
import json
import sys
from pathlib import Path

component, commit = sys.argv[1:]
report = json.loads(Path(f"reports/{component}-trivy.json").read_text())
if report.get("SchemaVersion") != 2 or not isinstance(report.get("Results", []), list):
    raise SystemExit("Unsupported scan report; refusing to push")
findings = [v for result in report.get("Results", []) for v in result.get("Vulnerabilities", [])
            if v.get("Severity") in {"HIGH", "CRITICAL"}]
for v in findings:
    print(v.get("Severity"), v.get("VulnerabilityID"), v.get("PkgName"), v.get("InstalledVersion"),
          "fix:", v.get("FixedVersion", "unavailable"))
if findings:
    raise SystemExit(f"STOP: {component} contains {len(findings)} HIGH/CRITICAL vulnerabilities")
Path(f"reports/{component}-trivy.html").write_text(
    '<!doctype html><html><head><meta charset="utf-8"><title>Trivy image scan</title></head><body>'
    f'<h1>{html.escape(component)}: PASS</h1><p>Commit: {html.escape(commit)}</p>'
    '<p>No HIGH/CRITICAL package vulnerabilities reported. Lower severities were not evaluated by this gate.</p>'
    f'<pre>{html.escape(json.dumps(report, indent=2))}</pre></body></html>')
