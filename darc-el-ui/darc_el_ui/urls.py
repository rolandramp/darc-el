from __future__ import annotations

from django.contrib import admin
from django.urls import path

from webapp.views import home, model_interaction, monitor, upload_documents

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("monitor/", monitor, name="monitor"),
    path("upload/", upload_documents, name="upload_documents"),
    path("model/", model_interaction, name="model_interaction"),
]
