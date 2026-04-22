FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if required by pymupdf, docling, and opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY pdf2abdm/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY pdf2abdm/__init__.py ./pdf2abdm/__init__.py
COPY pdf2abdm/app/ ./pdf2abdm/app/
COPY pdf2abdm/utils/ ./pdf2abdm/utils/
COPY pdf2abdm/rulebooks_updated/ ./pdf2abdm/rulebooks_updated/
COPY pdf2abdm/tasks.py ./pdf2abdm/tasks.py

# Set PYTHONPATH so imports work
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "pdf2abdm.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "1500"]
