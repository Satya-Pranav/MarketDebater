release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: PYTHONPATH=frontend gunicorn marketdebater_frontend.wsgi:application --bind=0.0.0.0:$PORT --workers 2 --timeout 1800 --access-logfile -
