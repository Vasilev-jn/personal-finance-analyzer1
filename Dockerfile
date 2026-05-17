FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=app:app

WORKDIR /app

RUN addgroup --system moneymap && adduser --system --ingroup moneymap moneymap

COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY app.py LICENSE README.md ./
COPY finance_app ./finance_app
COPY instructions ./instructions

RUN mkdir -p data models && chown -R moneymap:moneymap /app

USER moneymap

EXPOSE 5059

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5059/api/auth/status', timeout=3)"

CMD ["python", "-m", "flask", "--app", "app:app", "run", "--host", "0.0.0.0", "--port", "5059"]
