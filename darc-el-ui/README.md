# DARC-EL UI

Django-based UI for the DARC-EL backend.

## Run locally

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8081
```

Set `BACKEND_BASE_URL` to point to the FastAPI backend (default `http://localhost:8000`).
