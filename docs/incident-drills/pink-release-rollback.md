# Pink release and rollback exercise

The second release uses a light pink page background (`#fce4ec`) and a very pale pink form card (`#fff5f8`). The existing Dockerfile includes this HTML in the frontend image. This is a second version of the same application, deployed to the existing service.

## 1. Save the current frontend revision before deploying

Run from your repository terminal while the original release is running:

```bash
mkdir -p .local-state/pink-release
aws ecs describe-services \
  --cluster webtech-production \
  --services webtech-production-frontend \
  --region eu-west-2 \
  --query 'services[0].taskDefinition' --output text \
  > .local-state/pink-release/original-frontend-task-definition.txt
cat .local-state/pink-release/original-frontend-task-definition.txt
```

Keep this file until the exercise is finished. Capture it before the pink deployment so it refers to the original release. Do not overwrite it after deploying pink.

## 2. Build and deploy the pink release

Commit only the intended frontend change and this guide, then push/merge through your normal main-branch workflow. A new commit gives the build a new immutable release identity. Do not reuse or overwrite the original image tag.

Use the existing `webtech-production-only` Jenkins job with `BUILD_ONLY` unchecked and `PRODUCTION_OBSERVABILITY_ENABLED` checked for this running observability environment. Keep the established production parameters and review the image scan results before approving deployment.

The pipeline builds the existing frontend/backend image pair. The visible change is in the frontend. No new ECS service or database is needed.

After deployment, open https://d36rzp0gjk5fiq.cloudfront.net and check the pink background. If the browser shows the previous page, perform a hard refresh. Check the actual ECS task definition and image digest before interpreting stale browser or CDN content as a failed deployment.

```bash
curl --connect-timeout 5 --max-time 15 -sS \
  https://d36rzp0gjk5fiq.cloudfront.net/ | rg '#fce4ec|#fff5f8'
curl --connect-timeout 5 --max-time 15 -sS \
  -w '\nHTTP %{http_code}\n' \
  https://d36rzp0gjk5fiq.cloudfront.net/api/health/db
```

## 3. Roll back the frontend when ready

The following changes the live frontend service. Run it only when you want to undo the pink deployment. Reusing the saved task definition restores its original image and configuration; no image rebuild is required.

```bash
original_frontend_task_definition=$(cat .local-state/pink-release/original-frontend-task-definition.txt)
aws ecs update-service \
  --cluster webtech-production \
  --service webtech-production-frontend \
  --task-definition "$original_frontend_task_definition" \
  --region eu-west-2 --no-cli-pager
aws ecs wait services-stable \
  --cluster webtech-production \
  --services webtech-production-frontend \
  --region eu-west-2
```

Verify the service uses the saved revision, the original background returns and `/api/health/db` still returns HTTP 200. This is a frontend rollback exercise; the backend remains on its deployed revision. A coordinated full-release rollback would need both service revisions recorded and restored.

An ECS rollback changes the running deployment, not Git. The pink code remains on main, so a later pipeline deployment can bring pink back. To make the original appearance the desired source state again, revert the dedicated pink-release commit through the normal review/build/deployment workflow.
