FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build-essential for compiling native extensions, iputils-ping, libpq-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Start the polling worker loop
CMD ["python", "main.py"]
