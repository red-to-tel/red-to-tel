FROM python:3.13-slim

# --- build args to match host user ---
ARG UID=1001
ARG GID=1001

# --- create non-root user with matching UID/GID ---
RUN groupadd -g ${GID} appgroup \
 && useradd -u ${UID} -g ${GID} -m appuser

WORKDIR /app

# --- install system dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# --- install Python dependencies ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- copy application code ---
COPY . .

# --- ensure app directory ownership ---
RUN mkdir -p /app/posts /tmp && \
    chown -R appuser:appgroup /app /tmp

# --- drop privileges ---
USER appuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "reddit.py"]

