release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
# Single worker with 8 threads so the in-process job dict (frontend.dashboard.jobs)
# is shared between the POST that starts a debate and the SSE handler that streams
# its events. Threads handle concurrency; LLM work is I/O-bound so the GIL is fine.
web: PYTHONPATH=frontend gunicorn marketdebater_frontend.wsgi:application --bind=0.0.0.0:$PORT --workers 1 --threads 8 --timeout 1800 --access-logfile -
