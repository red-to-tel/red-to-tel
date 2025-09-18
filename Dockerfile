FROM python:3.13-slim

# create non-root user
RUN useradd --create-home appuser
WORKDIR /app

# install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# copy dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy project code
COPY . .

# create posts directory for persistence
RUN mkdir -p /app/posts && chown -R appuser:appuser /app/posts /app

USER appuser
ENV PYTHONUNBUFFERED=1

CMD ["python", "reddit.py"]
