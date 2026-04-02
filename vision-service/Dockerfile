FROM python:3.12-slim AS base

WORKDIR /app

# System deps for image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libglib2.0-0 libsm6 libxext6 libxrender-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 20002

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "20002"]
