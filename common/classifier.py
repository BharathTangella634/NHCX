import logging
from common.llm_inference_service import LlmInferenceService

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """
You are an expert medical document classifier.
Analyze the following text extracted from a PDF and classify it into one of these three categories:

1. "CLINICAL": The document is a medical record, such as a discharge summary, lab report, diagnostic report, or clinical note.
2. "INSURANCE": The document is an insurance policy, a claim form, a pre-authorization request, or an insurance-related benefit summary.
3. "INVALID": The document is neither a medical record nor an insurance document (e.g., it's a random letter, an invoice for non-medical items, or garbage text).

Return ONLY the category name in uppercase: "CLINICAL", "INSURANCE", or "INVALID".

TEXT:
{text}
"""

async def classify_document_text(text: str) -> str:
    """
    Classifies document text into CLINICAL, INSURANCE, or INVALID.
    Uses the native LlmInferenceService (Gemma-4).
    """
    if not text or len(text.strip()) < 50:
        return "INVALID"

    # Use first 2000 chars for classification to keep it fast
    sample_text = text[:2000]
    
    svc = LlmInferenceService()
    try:
        response = await svc.generate(
            prompt=CLASSIFICATION_PROMPT.format(text=sample_text),
            temperature=0.1,
            max_output_tokens=10
        )
        category = response.strip().upper()
        if category in ["CLINICAL", "INSURANCE", "INVALID"]:
            return category
        
        # Fallback heuristic if LLM output is noisy
        if "CLINICAL" in category: return "CLINICAL"
        if "INSURANCE" in category: return "INSURANCE"
        return "INVALID"
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return "INVALID"
