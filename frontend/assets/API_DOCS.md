# FHIR Converter — API Reference

> **Base URL (Production)**
> ```
> https://nhcxhackathon.tanuh.ai/pdf2abdm   ← Clinical Documents (ABDM FHIR)
> https://nhcxhackathon.tanuh.ai/pdf2nhcx   ← Insurance Policies (NHCX)
> ```

---

## Quick-Start Summary

| Goal | Endpoint | Method |
|------|----------|--------|
| Convert clinical PDF (sync) | `/pdf2abdm` | `POST` |
| Convert insurance PDF (sync) | `/pdf2nhcx` | `POST` |
| Submit clinical PDF async | `/pdf2abdm/submit` | `POST` |
| Submit insurance PDF async | `/pdf2nhcx/submit` | `POST` |
| Submit local-path PDF (ABDM) | `/pdf2abdmurl` | `POST` |
| Submit local-path PDF (NHCX) | `/pdf2nhcxurl` | `POST` |
| Poll task status | `/pdf2abdm/task-status/{task_id}` | `GET` |
| Fetch task result | `/pdf2abdm/task-result/{task_id}` | `GET` |
| Health check | `/pdf2abdm/health` | `GET` |
| Model health | `/pdf2abdm/model-health?model=gemma4` | `GET` |

---

## Authentication

All services use **Google Application Default Credentials (ADC)** on the server side. Clients do **not** need to pass any API key — simply call the HTTP endpoints from your allowed network/domain.

---

## Status Codes

| Code | Meaning |
|------|---------|
| `200 OK` | Request succeeded; body contains the result |
| `202 Accepted` | Task queued for async processing; body contains `task_id` |
| `400 Bad Request` | Invalid input (e.g. non-PDF file, missing field) |
| `404 Not Found` | File not found (URL-path endpoints) or unknown model |
| `413 Request Entity Too Large` | PDF exceeds 25 MB or 100 pages |
| `422 Unprocessable Entity` | Missing required form fields |
| `500 Internal Server Error` | Processing failed (OCR or LLM error) |
| `503 Service Unavailable` | Backend model or auth unavailable |

---

## Clinical Document (ABDM FHIR) Endpoints

### 1. `POST /pdf2abdm` — Synchronous conversion

Converts a clinical PDF to one or more ABDM-compliant FHIR R4 DocumentBundles. Waits until processing is complete (3–8 min typical).

**Request** — `multipart/form-data`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | PDF file | ✅ | — | Clinical document (max 25 MB / 100 pages) |
| `model` | string | ❌ | `gemma4` | LLM model identifier |
| `ocr_engine` | string | ❌ | `auto` | OCR engine: `auto`, `docling`, `rapidocr` |

**Response** — `200 OK`

```json
{
  "message": "File processed successfully",
  "gcs_uri": "gs://tanuh-bcd-bucket/pdf_uploads/abdm/report.pdf",
  "processing_time": "214.3 seconds",
  "document_type": "DiagnosticReportRecord",
  "bundles": [ { ...FHIR Bundle... }, { ...FHIR Bundle... } ],
  "bundle_names": ["Bundle 1 - DiagnosticReportRecord"],
  "model_used": "gemma4",
  "ocr_engine_used": "docling"
}
```

**Response fields**

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Human-readable status |
| `gcs_uri` | string | GCS path where the input PDF is stored |
| `processing_time` | string | Wall-clock time for the full pipeline |
| `document_type` | string | Detected ABDM document type (e.g. `DischargeSummaryRecord`) |
| `bundles` | array | Array of FHIR R4 DocumentBundle objects |
| `bundle_names` | array | Display labels for each bundle |
| `model_used` | string | LLM model used |
| `ocr_engine_used` | string | OCR engine that was selected |

---

### 2. `POST /pdf2abdm/submit` — Async submission

Submit a PDF and immediately receive a `task_id`. Poll for results separately.

**Request** — `multipart/form-data`

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `file` | PDF file | ✅ | — |
| `model` | string | ❌ | `gemma4` |

**Response** — `202 Accepted`

```json
{
  "task_id": "a3f8c2d1-...",
  "status": "queued",
  "message": "Task queued. Poll /pdf2abdm/task-status/a3f8c2d1-... for progress.",
  "gcs_uri": "gs://tanuh-bcd-bucket/pdf_uploads/abdm/report.pdf"
}
```

---

### 3. `GET /pdf2abdm/task-status/{task_id}` — Poll status

**Response**

```json
{
  "task_id": "a3f8c2d1-...",
  "status": "processing",   // "queued" | "processing" | "completed" | "failed"
  "progress": "Section 3/8 processed"
}
```

| Status value | Meaning |
|---|---|
| `queued` | Task received, worker not started yet |
| `processing` | Worker is actively running |
| `completed` | Done — fetch result via `/task-result` |
| `failed` | Error occurred — see `error` field in response |

---

### 4. `GET /pdf2abdm/task-result/{task_id}` — Fetch result

**Response** — `200 OK` (same structure as sync `/pdf2abdm`)

```json
{
  "task_id": "a3f8c2d1-...",
  "status": "completed",
  "result": {
    "bundles": [ { ...FHIR Bundle... } ],
    "bundle_names": ["Bundle 1 - DischargeSummaryRecord"],
    "document_type": "DischargeSummaryRecord",
    "processing_time": "198.7 seconds",
    "gcs_uri": "gs://tanuh-bcd-bucket/json_output/abdm/report.json"
  }
}
```

---

### 5. `POST /pdf2abdmurl` — Convert by local file path

For server-side or Docker volume usage. Accepts a JSON body instead of a file upload.

**Request** — `application/json`

```json
{
  "file_path": "/app/data/report.pdf",
  "model": "gemma4",
  "ocr_engine": "auto"
}
```

**Response** — same as `POST /pdf2abdm`

---

## Insurance Policy (NHCX) Endpoints

Mirrors the ABDM endpoints but targets insurance/claim documents.

### 1. `POST /pdf2nhcx` — Synchronous conversion

**Request** — `multipart/form-data` (same fields as `/pdf2abdm`)

**Response** — `200 OK`

```json
{
  "message": "File processed successfully",
  "gcs_uri": "gs://tanuh-bcd-bucket/pdf_uploads/nhcx/claim.pdf",
  "processing_time": "183.5 seconds",
  "document_type": "InsurancePlan",
  "bundle": { ...NHCX FHIR Bundle... },
  "bundle_names": ["NHCX Bundle"],
  "model_used": "gemma4",
  "ocr_engine_used": "docling"
}
```

> **Note:** NHCX returns a single `bundle` object (not an array), reflecting the single-claim structure.

### 2. `POST /pdf2nhcx/submit` — Async submission

Same interface as `/pdf2abdm/submit`. Returns `task_id`.

### 3. `GET /pdf2nhcx/task-status/{task_id}` — Poll status

Same interface as ABDM task-status.

### 4. `GET /pdf2nhcx/task-result/{task_id}` — Fetch result

```json
{
  "task_id": "b9e1a7f2-...",
  "status": "completed",
  "result": {
    "bundle": { ...NHCX FHIR Bundle... },
    "processing_time": "183.5 seconds",
    "gcs_uri": "gs://tanuh-bcd-bucket/json_output/nhcx/claim.json"
  }
}
```

### 5. `POST /pdf2nhcxurl` — Convert by local file path

```json
{
  "file_path": "/app/data/claim.pdf",
  "model": "gemma4",
  "ocr_engine": "auto"
}
```

---

## Health & Monitoring Endpoints

| Endpoint | Response when healthy |
|----------|----------------------|
| `GET /pdf2abdm/health` | `{"status":"ok","service":"pdf2abdm"}` |
| `GET /pdf2nhcx/health` | `{"status":"ok","service":"pdf2nhcx"}` |
| `GET /pdf2abdm/model-health?model=gemma4` | `{"status":"ok","model":"gemma4","vertex_model":"publishers/google/models/gemma-4-26b-a4b-it-maas"}` |
| `GET /pdf2abdm/ocr-health?engine=docling` | `{"status":"ok","engine":"docling"}` |

---

## GCS Storage Paths

| Purpose | GCS Path |
|---------|----------|
| Input PDFs (ABDM) | `gs://tanuh-bcd-bucket/pdf_uploads/abdm/<filename>.pdf` |
| Input PDFs (NHCX) | `gs://tanuh-bcd-bucket/pdf_uploads/nhcx/<filename>.pdf` |
| Output JSON (ABDM) | `gs://tanuh-bcd-bucket/json_output/abdm/<filename>.json` |
| Output JSON (NHCX) | `gs://tanuh-bcd-bucket/json_output/nhcx/<filename>.json` |

---

## Python Implementation

### Synchronous (simple — blocks until done)

```python
import requests

BASE_URL = "https://nhcxhackathon.tanuh.ai/pdf2abdm"  # or /pdf2nhcx

def convert_clinical_pdf(pdf_path: str) -> dict:
    """Convert a clinical PDF to ABDM FHIR bundles (synchronous)."""
    with open(pdf_path, "rb") as f:
        response = requests.post(
            f"{BASE_URL}",
            files={"file": (pdf_path.split("/")[-1], f, "application/pdf")},
            data={"model": "gemma4", "ocr_engine": "auto"},
            timeout=600,  # 10 min — processing can take 3–8 min
        )
    response.raise_for_status()
    data = response.json()
    print(f"Document type : {data['document_type']}")
    print(f"Processing time: {data['processing_time']}")
    print(f"Bundles found : {len(data['bundles'])}")
    return data["bundles"]

if __name__ == "__main__":
    bundles = convert_clinical_pdf("/path/to/discharge_summary.pdf")
    import json
    print(json.dumps(bundles[0], indent=2))
```

---

### Asynchronous with polling (recommended for production)

```python
import time
import requests

ABDM_BASE = "https://nhcxhackathon.tanuh.ai/pdf2abdm"
NHCX_BASE = "https://nhcxhackathon.tanuh.ai/pdf2nhcx"

# ── Step 1: Submit ─────────────────────────────────────────────────────────
def submit_pdf(pdf_path: str, service: str = "abdm") -> str:
    """Submit a PDF for async processing. Returns task_id."""
    base = ABDM_BASE if service == "abdm" else NHCX_BASE
    with open(pdf_path, "rb") as f:
        resp = requests.post(
            f"{base}/submit",
            files={"file": (pdf_path.split("/")[-1], f, "application/pdf")},
            data={"model": "gemma4"},
            timeout=30,
        )
    resp.raise_for_status()
    task_id = resp.json()["task_id"]
    print(f"✅ Task submitted: {task_id}")
    return task_id

# ── Step 2: Poll ───────────────────────────────────────────────────────────
def poll_until_done(task_id: str, service: str = "abdm",
                    poll_interval: int = 15, max_wait: int = 900) -> dict:
    """Poll task-status until completed or failed."""
    base = ABDM_BASE if service == "abdm" else NHCX_BASE
    status_url = f"{base}/task-status/{task_id}"
    result_url = f"{base}/task-result/{task_id}"
    elapsed = 0

    while elapsed < max_wait:
        resp = requests.get(status_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        print(f"  [{elapsed:>4}s] status={status}  {data.get('progress', '')}")

        if status == "completed":
            result = requests.get(result_url, timeout=10).json()
            return result["result"]

        if status == "failed":
            raise RuntimeError(f"Task failed: {data.get('error', 'unknown error')}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Task {task_id} did not complete within {max_wait}s")

# ── Step 3: Fetch & save ───────────────────────────────────────────────────
def process_pdf_async(pdf_path: str, service: str = "abdm",
                       output_path: str = "result.json") -> None:
    import json
    task_id = submit_pdf(pdf_path, service)
    result  = poll_until_done(task_id, service)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"✅ Result saved to {output_path}")

if __name__ == "__main__":
    # Clinical document (ABDM)
    process_pdf_async(
        "/path/to/discharge_summary.pdf",
        service="abdm",
        output_path="abdm_result.json"
    )

    # Insurance policy (NHCX)
    process_pdf_async(
        "/path/to/claim_form.pdf",
        service="nhcx",
        output_path="nhcx_result.json"
    )
```

---

### Concurrent batch processing

```python
import asyncio
import aiohttp

ABDM_BASE = "https://nhcxhackathon.tanuh.ai/pdf2abdm"

async def submit_async(session: aiohttp.ClientSession, pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        data = aiohttp.FormData()
        data.add_field("file", f,
                       filename=pdf_path.split("/")[-1],
                       content_type="application/pdf")
        data.add_field("model", "gemma4")
        async with session.post(f"{ABDM_BASE}/submit", data=data) as resp:
            body = await resp.json()
            return body["task_id"]

async def poll_async(session: aiohttp.ClientSession, task_id: str,
                     interval: int = 15, max_wait: int = 900) -> dict:
    elapsed = 0
    while elapsed < max_wait:
        async with session.get(f"{ABDM_BASE}/task-status/{task_id}") as resp:
            body = await resp.json()
        if body["status"] == "completed":
            async with session.get(f"{ABDM_BASE}/task-result/{task_id}") as resp:
                result = await resp.json()
            return result["result"]
        if body["status"] == "failed":
            raise RuntimeError(body.get("error", "unknown"))
        await asyncio.sleep(interval)
        elapsed += interval
    raise TimeoutError(task_id)

async def batch_convert(pdf_paths: list[str]) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        # Submit all concurrently
        task_ids = await asyncio.gather(*[submit_async(session, p) for p in pdf_paths])
        # Poll all concurrently
        results  = await asyncio.gather(*[poll_async(session, tid) for tid in task_ids])
    return list(results)

if __name__ == "__main__":
    import json, asyncio
    paths = [
        "/data/patient_001.pdf",
        "/data/patient_002.pdf",
        "/data/patient_003.pdf",
    ]
    all_results = asyncio.run(batch_convert(paths))
    for i, r in enumerate(all_results):
        with open(f"result_{i+1}.json", "w") as f:
            json.dump(r, f, indent=2)
        print(f"✅ result_{i+1}.json written")
```

---

## FHIR Bundle Structure (ABDM)

```json
{
  "resourceType": "Bundle",
  "id": "uuid-...",
  "meta": {
    "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle"]
  },
  "type": "document",
  "entry": [
    { "resource": { "resourceType": "Composition", "...": "..." } },
    { "resource": { "resourceType": "Patient",     "...": "..." } },
    { "resource": { "resourceType": "Practitioner","...": "..." } },
    { "resource": { "resourceType": "Organization","...": "..." } },
    { "resource": { "resourceType": "Observation", "...": "..." } },
    { "resource": { "resourceType": "DocumentReference", "...": "..." } }
  ]
}
```

## NHCX Bundle Structure

```json
{
  "resourceType": "Bundle",
  "id": "uuid-...",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Coverage",    "...": "..." } },
    { "resource": { "resourceType": "Patient",     "...": "..." } },
    { "resource": { "resourceType": "Organization","...": "..." } },
    { "resource": { "resourceType": "Claim",       "...": "..." } }
  ]
}
```

---

## Limits & SLAs

| Constraint | Value |
|------------|-------|
| Max PDF size | 25 MB |
| Max PDF pages | 100 |
| Typical processing time | 3–8 minutes |
| Async task result TTL | 24 hours (Redis cache) |
| GCS object retention | Configurable (default: indefinite) |
| Rate limit | No hard limit; concurrency governed by Celery worker count |

---

*© 2026 TANUH AI — Indian Institute of Science. For support: nhcx@tanuh.ai*
