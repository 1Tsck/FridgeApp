# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app
COPY app ./app

# Expose port
EXPOSE 8080

# Run the app using Gunicorn + Uvicorn workers (recommended for production)
CMD exec uvicorn app.main:app --host 0.0.0.0 --port 8080
