FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN adduser --disabled-password --gecos '' appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files for the admin site. A build-time key is fine here:
# nothing is signed during the build, and the real key comes from the runtime
# environment.
RUN DJANGO_DEBUG=False \
    DJANGO_SECRET_KEY=build-only \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
