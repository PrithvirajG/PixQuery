FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# 👇 Add this line
ENV PYTHONPATH="${PYTHONPATH}:/app"

CMD ["python", "src/ingestion/monitor.py"]
