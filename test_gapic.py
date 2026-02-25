import os
from typing import Dict, List, Union
from dotenv import load_dotenv
from google.cloud import aiplatform
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

def predict_custom_trained_model_sample(
    project: str,
    endpoint_id: str,
    instances: Union[Dict, List[Dict]],
    location: str = "asia-northeast1",
    api_endpoint: str = "asia-northeast1-aiplatform.googleapis.com",
):
    client_options = {"api_endpoint": api_endpoint}
    client = aiplatform.gapic.PredictionServiceClient(client_options=client_options)
    instances = instances if isinstance(instances, list) else [instances]
    instances = [json_format.ParseDict(instance_dict, Value()) for instance_dict in instances]
    parameters_dict = {}
    parameters = json_format.ParseDict(parameters_dict, Value())
    endpoint = client.endpoint_path(project=project, location=location, endpoint=endpoint_id)
    response = client.predict(endpoint=endpoint, instances=instances, parameters=parameters)
    predictions = response.predictions
    for prediction in predictions:
        print(" prediction:", prediction)

if __name__ == "__main__":
    load_dotenv()
    project = os.getenv("VERTEX_PROJECT")
    location = os.getenv("VERTEX_LOCATION")
    endpoint_id = os.getenv("VERTEX_ENDPOINT")
    api_endpoint = os.getenv("VERTEX_API_ENDPOINT")
    
    # Just a small tweak for endpoints that might look like URLs
    if api_endpoint and api_endpoint.startswith("https://"):
        api_endpoint = api_endpoint[8:]
    
    predict_custom_trained_model_sample(
        project, endpoint_id, [{"prompt": "What is a cloud?"}], location, api_endpoint
    )
