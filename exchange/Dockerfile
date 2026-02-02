FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY exchange/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY exchange/app/ ./app/
COPY exchange/data/ ./data/
COPY exchange/manage.py .
COPY VERSION .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
