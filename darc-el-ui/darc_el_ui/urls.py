from __future__ import annotations

from django.contrib import admin
from django.urls import path

from webapp.views import document_page, home, model_interaction, monitor

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("monitor/", monitor, name="monitor"),
    path("document/", document_page, name="document"),
    path("model/", model_interaction, name="model_interaction"),
]
