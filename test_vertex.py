import os
from dotenv import load_dotenv
from google.cloud import aiplatform
import google.auth
from google.auth.exceptions import DefaultCredentialsError


def resolve_endpoint_name(project: str, location: str, endpoint_id_or_name: str) -> str:
    """
    Accepts either:
      - numeric endpoint id: "1234567890123456789"
      - full resource name: "projects/.../locations/.../endpoints/123..."
    Returns the full endpoint resource name.
    """
    s = endpoint_id_or_name.strip()
    if s.startswith("projects/") and "/endpoints/" in s:
        return s
    return f"projects/{project}/locations/{location}/endpoints/{s}"


def ensure_adc_available() -> None:
    """
    Ensures Application Default Credentials can be discovered.
    If not, raise an error with actionable next steps.
    """
    try:
        # This is what the Vertex AI SDK relies on under the hood.
        google.auth.default()
    except DefaultCredentialsError as e:
        gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        msg = [
            "Google Application Default Credentials (ADC) were not found.",
            "",
            "Fix options:",
            "  1) Recommended for scripts/CI: set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON key file:",
            "       export GOOGLE_APPLICATION_CREDENTIALS='/path/to/service-account.json'",
            "     (Use a placeholder path; do not hardcode secrets into code.)",
            "",
            "  2) For local development: run:",
            "       gcloud auth application-default login",
            "",
            f"Current GOOGLE_APPLICATION_CREDENTIALS: {gac!r}",
            "",
            f"Original error: {e}",
        ]
        raise RuntimeError("\n".join(msg)) from e


def main() -> None:
    load_dotenv()
    # Prefer environment variables so you don't commit identifiers into code.
    project = "147901050545"
    location = "asia-northeast1"
    endpoint_id_or_name = "mg-endpoint-85fde817-56ed-4bc4-bb4c-e541fc9ebb7a"

    # 1) Fail early with a helpful message if auth isn't configured.
    ensure_adc_available()

    # 2) Initialize Vertex AI client defaults.
    aiplatform.init(project=project, location=location)

    # 3) Build endpoint resource name robustly.
    endpoint_name = resolve_endpoint_name(project, location, endpoint_id_or_name)
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_name)

    instances = [{"prompt": "What is a cloud?"}]

    # Let unexpected exceptions show their stack traces (better for debugging).
    response = endpoint.predict(instances=instances)
    print(response.predictions[0])


if __name__ == "__main__":
    main()