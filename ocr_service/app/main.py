import json
import os
import threading
import base64
from kafka import KafkaConsumer, KafkaProducer
from utils.ocr_engine import extract_text_from_pdf
from utils.fhir_converter import text_to_abdm_fhir

KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
INPUT_TOPIC = os.getenv('INPUT_TOPIC', 'pdf-tasks')
OUTPUT_TOPIC = os.getenv('OUTPUT_TOPIC', 'fhir-results')

def process_message(message, producer):
    try:
        data = json.loads(message.value.decode('utf-8'))
        file_content_b64 = data.get('content')
        filename = data.get('filename', 'input.pdf')

        if not file_content_b64:
            print("No content found in message")
            return

        # Save PDF temporarily
        temp_path = f"/tmp/{filename}"
        with open(temp_path, "wb") as f:
            f.write(base64.b64decode(file_content_b64))

        # Perform OCR
        print(f"Processing {filename}...")
        extracted_text = extract_text_from_pdf(temp_path)

        # Convert to FHIR
        fhir_json = text_to_abdm_fhir(extracted_text, filename)

        # Send to output topic
        producer.send(OUTPUT_TOPIC, value=fhir_json.encode('utf-8'))
        print(f"Successfully processed {filename} and sent to {OUTPUT_TOPIC}")

        # Cleanup
        os.remove(temp_path)
    except Exception as e:
        print(f"Error processing message: {e}")

def main():
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id='ocr-group',
        auto_offset_reset='earliest'
    )
    producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

    print(f"OCR Service started. Listening on {INPUT_TOPIC}...")

    for message in consumer:
        # Multiple threads for processing
        thread = threading.Thread(target=process_message, args=(message, producer))
        thread.start()

if __name__ == "__main__":
    main()
