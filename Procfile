web: gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --worker-class gthread --threads 4 --timeout 120 --graceful-timeout 30 --keep-alive 5 --log-file -
