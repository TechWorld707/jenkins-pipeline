# WebTech Technologies enquiry app

This project has three services:

- **Frontend:** static HTML served by Nginx.
- **Backend:** Python FastAPI validates and stores enquiries.
- **Database:** PostgreSQL stores each name and email address.

The frontend and backend have separate Dockerfiles and are built as separate images. PostgreSQL is required; the app has no SQLite fallback.

## Run locally

From this directory, run:

```bash
docker compose up --build
```

Open http://localhost:8080. The form posts to `/api/enquiries`; Nginx forwards that request to the private backend container. The backend waits for PostgreSQL to become healthy before starting.

Stop with `Ctrl+C`. To also remove the local PostgreSQL data volume:

```bash
docker compose down -v
```

The Compose database password is only for local learning. In AWS, ECS tasks should receive the PostgreSQL connection string from Secrets Manager, and the database should be Amazon RDS PostgreSQL. Do not put production passwords in Git or a Docker image.

## Endpoints

- `GET /` — enquiry form, served by Nginx.
- `GET /healthz` — backend health check, proxied through Nginx.
- `GET /api/health/db` — database health check.
- `POST /api/enquiries` — validate and save an enquiry.

For the CI/CD pipeline, build and tag the frontend and backend images separately. Promote the same two image digests from staging to production; do not rebuild them between environments.

This short learning project creates the table at backend startup. A production system should use database migrations as a controlled deployment step.
