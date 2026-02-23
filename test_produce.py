import json
import base64
import sys
from kafka import KafkaProducer

def send_pdf(pdf_path):
    producer = KafkaProducer(
        bootstrap_servers=['localhost:29092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    with open(pdf_path, "rb") as f:
        content = base64.b64encode(f.read()).decode('utf-8')

    message = {
        "filename": pdf_path.split("/")[-1],
        "content": content
    }

    producer.send('pdf-tasks', value=message)
    producer.flush()
    print(f"Sent {pdf_path} to kafka topic 'pdf-tasks'")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_produce.py <path_to_pdf>")
    else:
        send_pdf(sys.argv[1])
