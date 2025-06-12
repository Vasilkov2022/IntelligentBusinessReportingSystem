FROM python:3.10-slim

WORKDIR /app
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    python3-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY certs/mincifry-chain.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY app ./app