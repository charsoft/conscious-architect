FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . ./

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV GCP_PROJECT_ID=gen-lang-client-0182092372

EXPOSE 8080

CMD ["python", "server.py"]
