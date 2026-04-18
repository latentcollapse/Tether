FROM python:3.11-slim

WORKDIR /app

COPY relay/ /app/relay/
COPY tether/ /app/tether/
COPY tether_lite/ /app/tether_lite/
COPY tether-dashboard/dist/ /app/tether-dashboard/dist/
COPY pyproject.toml /app/

RUN pip install --no-cache-dir -e .

ENV TETHER_RELAY_HOST=0.0.0.0
ENV TETHER_RELAY_PORT=8000
ENV TETHER_RELAY_DB=/data/relay.db

RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "relay.main:app", "--host", "0.0.0.0", "--port", "8000"]
