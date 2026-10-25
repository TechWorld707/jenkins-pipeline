"""Produce the immutable release manifest after both pushes complete."""
import json
import os
import subprocess
import sys

commit, registry = sys.argv[1:]
images = {}
for component in ("frontend", "backend"):
    repo = os.environ[f"{component.upper()}_ECR_REPOSITORY"]
    data = json.loads(subprocess.check_output([
        "aws", "ecr", "describe-images", "--repository-name", repo,
        "--image-ids", f"imageTag={commit}", "--output", "json"]))
    digest = data["imageDetails"][0]["imageDigest"]
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise SystemExit("Invalid ECR digest")
    images[component] = f"{registry}/{repo}@{digest}"
print(json.dumps({"commit": commit, "images": images}, indent=2))
