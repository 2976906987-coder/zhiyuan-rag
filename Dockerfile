FROM python:3.12-slim
WORKDIR /app
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY app ./app
RUN mkdir -p /app/data
HEALTHCHECK --interval=20s --timeout=5s --start-period=60s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=4)"
EXPOSE 8000
CMD ["python", "-m", "app.container_start"]
