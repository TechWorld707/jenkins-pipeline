#!/usr/bin/env bash
set -euo pipefail
: "${CODEBUILD_RESOLVED_SOURCE_VERSION:?Missing source SHA}"
: "${EXPECTED_COMMIT:?Start through Jenkins with an exact commit SHA}"
: "${SCAN_REPORT_BUCKET:?Missing report bucket}"
: "${AWS_ACCOUNT_ID:?Missing account ID}"
: "${AWS_DEFAULT_REGION:?Missing AWS region}"
: "${FRONTEND_ECR_REPOSITORY:?Missing frontend repository}"
: "${BACKEND_ECR_REPOSITORY:?Missing backend repository}"
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]]
[[ "$CODEBUILD_RESOLVED_SOURCE_VERSION" == "$EXPECTED_COMMIT" ]]
[[ "$(git rev-parse HEAD)" == "$EXPECTED_COMMIT" ]]
registry="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com"
mkdir -p reports
for component in frontend backend; do
  repo_var="${component^^}_ECR_REPOSITORY"
  docker build -f "app/$component/Dockerfile" -t "$registry/${!repo_var}:$EXPECTED_COMMIT" "app/$component"
done
# Each scan writes local findings and fails immediately on a blocking result.
# Nothing uploads or pushes until BOTH scans succeed. Scanner errors also fail closed.
for component in frontend backend; do
  repo_var="${component^^}_ECR_REPOSITORY"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v trivy-cache:/root/.cache/ -v "$PWD/reports:/reports" \
    aquasec/trivy:0.76.1 image --scanners vuln --severity HIGH,CRITICAL \
    --format json --output "/reports/$component-trivy.json" \
    "$registry/${!repo_var}:$EXPECTED_COMMIT"
  python3 ci/image-report.py "$component" "$EXPECTED_COMMIT"
done
# Only successful scan reports reach S3. No post_build/finally upload exists.
run_id="${CODEBUILD_BUILD_ID##*:}"
report_prefix="reports/$EXPECTED_COMMIT/$run_id"
aws s3 cp reports/ "s3://$SCAN_REPORT_BUCKET/$report_prefix/" --recursive --only-show-errors
aws ecr get-login-password --region "$AWS_DEFAULT_REGION" | docker login --username AWS --password-stdin "$registry"
for component in frontend backend; do
  repo_var="${component^^}_ECR_REPOSITORY"
  docker push "$registry/${!repo_var}:$EXPECTED_COMMIT"
done
# Resolve remote immutable digests; Jenkins deploys these, never mutable tags.
python3 ci/release.py "$EXPECTED_COMMIT" "$registry" > release.json
aws s3 cp release.json "s3://$SCAN_REPORT_BUCKET/$report_prefix/release.json" --only-show-errors
