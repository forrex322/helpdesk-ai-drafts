FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements/ requirements/
RUN pip install -r requirements/dev.txt

COPY . .
RUN SECRET_KEY=build python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["./bin/web"]
