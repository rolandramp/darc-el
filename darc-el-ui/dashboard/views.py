from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings
from django.shortcuts import render


def _fetch_json(client: httpx.Client, endpoint: str) -> tuple[dict[str, Any] | None, str | None]:
    url = f"{settings.BACKEND_BASE_URL}{endpoint}"
    try:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None, f"Unexpected response format from {endpoint}"
        return data, None
    except Exception as exc:
        return None, str(exc)


def dashboard(request):
    with httpx.Client(timeout=8.0) as client:
        health_payload, health_error = _fetch_json(client, "/health")
        llm_payload, llm_error = _fetch_json(client, "/llm/status")

    context = {
        "backend_base_url": settings.BACKEND_BASE_URL,
        "health_payload": health_payload,
        "health_error": health_error,
        "llm_payload": llm_payload,
        "llm_error": llm_error,
    }
    return render(request, "dashboard/index.html", context)
