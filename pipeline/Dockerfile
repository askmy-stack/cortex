FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY pipeline ./pipeline
COPY connectors ./connectors
COPY extraction ./extraction
COPY graph ./graph
COPY scoring ./scoring
COPY shared ./shared
COPY memory ./memory
COPY intelligence ./intelligence

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

CMD ["python", "-m", "pipeline.extraction_worker"]
