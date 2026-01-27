FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agentplatform/ ./agentplatform/

EXPOSE 8001

CMD ["uvicorn", "agentplatform.main:app", "--host", "0.0.0.0", "--port", "8001"]
