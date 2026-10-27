FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app_server.py .
CMD ["uvicorn", "app_server:app", "--host", "0.0.0.0", "--port", "8000"]