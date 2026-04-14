FROM python:3.11-slim
WORKDIR /app

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Expose port
EXPOSE 10000

# Start
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port 10000"]
