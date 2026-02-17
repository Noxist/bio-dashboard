FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app/ ./app/

# Create data dir
RUN mkdir -p /data

# Expose ports: 8000 = FastAPI, 8501 = Streamlit
EXPOSE 8000 8501

# Startup script
COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
