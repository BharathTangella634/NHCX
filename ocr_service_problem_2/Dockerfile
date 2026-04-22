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

COPY ocr_service_problem_2/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY ocr_service_problem_2/app/ ./ocr_service_problem_2/app/
COPY ocr_service_problem_2/utils/ ./ocr_service_problem_2/utils/
COPY ocr_service_problem_2/rulebooks_updated/ ./ocr_service_problem_2/rulebooks_updated/

# Set PYTHONPATH so imports work
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "ocr_service_problem_2.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "1500"]
