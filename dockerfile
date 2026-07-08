FROM python:3.11-slim

WORKDIR /app

# مكتبات النظام اللي opencv-python-headless و Pillow محتاجينها
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY Backend/requirements.txt ./Backend/requirements.txt
RUN pip install --no-cache-dir -r Backend/requirements.txt

COPY Backend/ ./Backend/
COPY Front-end/ ./Front-end/

WORKDIR /app/Backend

# Azure App Service for Containers بيبعت الـ PORT كـ env var
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]