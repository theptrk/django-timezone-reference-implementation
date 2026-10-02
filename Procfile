release: python manage.py migrate --noinput && python manage.py setup_demo
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --access-logfile - --error-logfile -
