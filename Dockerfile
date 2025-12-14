# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend
COPY backend ./backend
COPY frontend ./frontend

# Expose port
EXPOSE 8080

# Run the app using Gunicorn + Uvicorn workers (recommended for production)
CMD ["python", "backend/main.py"]