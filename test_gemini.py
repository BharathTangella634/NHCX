import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# IMPORTANT: Ensure you are NOT setting 'vertexai=True'
# and that you are using the genai.Client specifically.
client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents="Hello! Are you working with my API key?"
    )
    print(response.text)
except Exception as e:
    print(f"Still failing? Here is the error: {e}")