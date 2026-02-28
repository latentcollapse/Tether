FROM python:3.11-slim

WORKDIR /app

COPY tether/ /app/tether/
COPY pyproject.toml /app/

RUN pip install --no-cache-dir -e .

ENV TETHER_DB=/data/tether.db
ENV TETHER_HOST=0.0.0.0
ENV TETHER_PORT=7890

RUN mkdir -p /data

EXPOSE 7890

CMD ["python", "-m", "tether.mcp_server"]
