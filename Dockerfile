# Dockerfile for ICT Smart Money Trading Alert System (FastAPI + async SQLAlchemy)
# Supports SQLite and PostgreSQL out of the box

FROM python:3.11.9-slim

# Set workdir
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port
EXPOSE 8000

# Entrypoint
CMD ["uvicorn", "ict_trading_system.main:app", "--host", "0.0.0.0", "--port", "8000"]
