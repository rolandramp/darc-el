from __future__ import annotations

from django.contrib import admin
from django.urls import path

from dashboard.views import dashboard

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard, name="dashboard"),
]
