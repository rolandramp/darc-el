# DARC-EL UI

Django-based UI for the DARC-EL backend.

## Scope

This README documents UI-specific setup and operations.
For project-wide architecture and full-stack orchestration, see [`../README.md`](../README.md).

## Run locally

From the `darc-el-ui` folder:

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8081
```

Set `BACKEND_BASE_URL` to point to the FastAPI backend (default `http://localhost:8000`).

## Run with Docker Compose

From the repository root:

```bash
docker compose build darc-el-ui
docker compose up darc-el-ui
```

To rebuild and recreate only the UI service:

```bash
docker compose up -d --build --force-recreate darc-el-ui
```

## UI Environment Variables

- `BACKEND_BASE_URL`: Base URL for the backend API consumed by the UI.
- `DJANGO_DEBUG`: Enables debug mode when set to `true` (default in compose).
- `DJANGO_ALLOWED_HOSTS`: Comma-separated allowed hosts (defaults to `*` in local settings).

## Service Access

- UI URL: `http://localhost:8081`
- Backend URL expected by default: `http://localhost:8000`

## Pages and Navigation

- Monitor page: `/monitor`
- Upload page: `/upload`
- Model page: `/model`

The UI now includes a top menu with `Monitor`, `Upload`, and `Model` items.
The upload page is separate and forwards selected files to the backend `POST /upload` endpoint using multipart form data with the `files` field.
The model page is separate and sends prompts to backend `POST /llm/default-model` for default model interaction.
