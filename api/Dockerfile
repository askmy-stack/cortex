FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY api ./api
COPY connectors ./connectors
COPY extraction ./extraction
COPY graph ./graph
COPY scoring ./scoring
COPY shared ./shared
COPY pipeline ./pipeline
COPY memory ./memory
COPY intelligence ./intelligence
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

RUN chmod +x scripts/start_api_production.sh

CMD ["sh", "scripts/start_api_production.sh"]
