"""URL routes for the dashboard app."""

from __future__ import annotations

from django.urls import path

from .views import home, run_debate_view


urlpatterns = [
    path("", home, name="home"),
    path("debate/", run_debate_view, name="run-debate"),
]
