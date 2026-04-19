from __future__ import annotations

import json
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


def _base_context(active_page: str) -> dict[str, Any]:
    return {
        "backend_base_url": settings.BACKEND_BASE_URL,
        "active_page": active_page,
    }


def _parse_response_payload(response: httpx.Response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def home(request):
    context = _base_context(active_page="home")
    return render(request, "webapp/index.html", context)


def monitor(request):
    with httpx.Client(timeout=8.0) as client:
        health_payload, health_error = _fetch_json(client, "/health")
        llm_payload, llm_error = _fetch_json(client, "/llm/status")

    context = _base_context(active_page="monitor")
    context.update(
        {
        "health_payload": health_payload,
        "health_error": health_error,
        "llm_payload": llm_payload,
        "llm_error": llm_error,
        }
    )
    return render(request, "webapp/moitor.html", context)


def upload_documents(request):
    context = _base_context(active_page="upload")

    if request.method != "POST":
        return render(request, "webapp/upload.html", context)

    files = request.FILES.getlist("files")
    if not files:
        context["upload_error"] = "Please select at least one file before uploading."
        return render(request, "webapp/upload.html", context)

    multipart_files: list[tuple[str, tuple[str, bytes, str]]] = []
    for file_obj in files:
        content_type = file_obj.content_type or "application/octet-stream"
        multipart_files.append(("files", (file_obj.name, file_obj.read(), content_type)))

    upload_url = f"{settings.BACKEND_BASE_URL}/upload"
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(upload_url, files=multipart_files)
    except Exception as exc:
        context["upload_error"] = f"Upload request failed: {exc}"
        return render(request, "webapp/upload.html", context)

    payload = _parse_response_payload(response)
    context["selected_file_count"] = len(files)

    if response.is_success:
        context["upload_success"] = payload or {
            "status": "completed",
            "detail": "Upload completed but response payload was not JSON.",
        }
        return render(request, "webapp/upload.html", context)

    if payload and "detail" in payload:
        error_detail = payload["detail"]
    elif payload:
        error_detail = json.dumps(payload)
    else:
        error_detail = response.text or "Unknown upload error"

    context["upload_error"] = f"Backend returned {response.status_code}: {error_detail}"
    return render(request, "webapp/upload.html", context)


def model_interaction(request):
    context = _base_context(active_page="model")

    if request.method != "POST":
        return render(request, "webapp/model.html", context)

    prompt = str(request.POST.get("prompt", "")).strip()
    system_prompt = str(request.POST.get("system_prompt", "")).strip()

    context["prompt_value"] = prompt
    context["system_prompt_value"] = system_prompt

    if not prompt:
        context["model_error"] = "Please enter a prompt before sending the request."
        return render(request, "webapp/model.html", context)

    payload: dict[str, Any] = {"prompt": prompt}
    if system_prompt:
        payload["system_prompt"] = system_prompt

    endpoint_url = f"{settings.BACKEND_BASE_URL}/llm/default-model"
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(endpoint_url, json=payload)
    except Exception as exc:
        context["model_error"] = f"Request failed: {exc}"
        return render(request, "webapp/model.html", context)

    response_payload = _parse_response_payload(response)
    if response.is_success:
        context["model_success"] = response_payload or {
            "status": "completed",
            "detail": "Response completed but payload was not JSON.",
        }
        return render(request, "webapp/model.html", context)

    if response_payload and "detail" in response_payload:
        error_detail = response_payload["detail"]
    elif response_payload:
        error_detail = json.dumps(response_payload)
    else:
        error_detail = response.text or "Unknown model interaction error"

    context["model_error"] = f"Backend returned {response.status_code}: {error_detail}"
    return render(request, "webapp/model.html", context)
