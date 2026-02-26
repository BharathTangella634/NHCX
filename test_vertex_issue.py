import os
from dotenv import load_dotenv
from ocr_service.utils.fhir_converter import predict_custom_trained_model_sample

load_dotenv()
project = os.getenv("VERTEX_PROJECT")
endpoint_id = os.getenv("VERTEX_ENDPOINT")

instance = {
    "@requestFormat": "chatCompletions",
    "messages": [
        {
            "role": "user",
            "content": "What is machine learning? Please, answer in pirate-speak."
        }
    ],
    "max_tokens": 1000
}

try:
    preds = predict_custom_trained_model_sample(project, endpoint_id, [instance])
    print("Predictions type:", type(preds))
    print("Predictions len:", len(preds))
    print("Keys:", preds.keys() if isinstance(preds, dict) else None)
    print("Choices:", preds.get('choices', None) if isinstance(preds, dict) else None)
    print("Content:", preds)
except Exception as e:
    import traceback
    traceback.print_exc()