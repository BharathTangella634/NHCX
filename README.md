# NHCX_HACKATHON
National Health Claims Exchange Hackathon

## Dockerized PDF to ABDM FHIR OCR Service

This project provides a microservice architecture for processing PDF files into ABDM-compliant FHIR formats using OCR (Docling/Tesseract) and Kafka.

### Architecture
- **Zookeeper**: Manages Kafka brokers.
- **Kafka**: Messaging backbone. Separate microservice.
- **OCR Service**: Multi-threaded Python service that:
  - Consumes PDF tasks from `pdf-tasks` topic.
  - Performs OCR using `docling`.
  - Converts extracted text into FHIR Bundle (ABDM style).
  - Produces results to `fhir-results` topic.

### Getting Started

1. **Prerequisites**: Docker & Docker Compose.

2. **Run the services**:
   ```bash
   docker-compose up --build
   ```

3. **Produce a PDF for processing**:
   You can use the `test_produce.py` script (requires `kafka-python` locally):
   ```bash
   python test_produce.py your_document.pdf
   ```

4. **Consume results**:
   You can monitor the `fhir-results` topic using any Kafka consumer.

### Requirements
- Python 3.11+
- Tesseract OCR (in Docker)
- Docling
- Kafka-python
- fhir.resources
