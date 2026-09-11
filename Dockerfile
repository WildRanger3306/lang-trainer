FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY templates ./templates
COPY static ./static
COPY scripts ./scripts
COPY db ./db
COPY docs/words/json ./docs/words/json

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python", "scripts/docker_entrypoint.py"]
