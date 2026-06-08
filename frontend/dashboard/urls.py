"""URL routes for the dashboard app."""

from __future__ import annotations

from django.urls import path

from .views import (
    debate_live_view,
    debate_result_view,
    debate_start_view,
    debate_stream_view,
    home,
    leaderboard_view,
    run_debate_view,
    run_scan_view,
)


urlpatterns = [
    path("", home, name="home"),
    # Async / streaming debate flow (the UI uses this).
    path("debate/start/", debate_start_view, name="debate-start"),
    path("debate/live/<str:job_id>/", debate_live_view, name="debate-live"),
    path("debate/stream/<str:job_id>/", debate_stream_view, name="debate-stream"),
    path("debate/result/<str:job_id>/", debate_result_view, name="debate-result"),
    # Legacy synchronous endpoint (kept for direct callers; UI does not hit this).
    path("debate/", run_debate_view, name="run-debate"),
    path("leaderboard/", leaderboard_view, name="leaderboard"),
    path("leaderboard/run-scan/", run_scan_view, name="run-scan"),
]
