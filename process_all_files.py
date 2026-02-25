import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ocr_service.utils.logger import get_logger

logger = get_logger(__name__)


def _stream_process_output(proc: subprocess.Popen, pdf_name: str) -> int:
    """
    Stream combined stdout/stderr from a subprocess to logs to avoid silent hangs.
    Returns the subprocess return code.
    """
    assert proc.stdout is not None  # for type checkers
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line:
            logger.info(f"[{pdf_name}] {line}")
    return proc.wait()


def process_all_files(
    test_files_dir: Path = Path("test_files/Problem_Statement_2_630a8c8cb6"),
    output_dir: Path = Path("fhir_results"),
    md_dir: Path = Path("markdown_results"),
    per_file_timeout_s: int = 15 * 60,
) -> None:
    project_root = Path(__file__).resolve().parent
    test_files_dir = (project_root / test_files_dir).resolve()
    output_dir = (project_root / output_dir).resolve()
    md_dir = (project_root / md_dir).resolve()

    # Ensure output directories exist
    output_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    if not test_files_dir.exists():
        logger.error(f"Test files directory does not exist: {test_files_dir}")
        return

    # Find all pdf files in the test_files directory and its subdirectories
    pdf_files = sorted(test_files_dir.rglob("*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDF files found in {test_files_dir}")
        return

    ocr_entry = (project_root / "ocr_service" / "app" / "main.py").resolve()
    if not ocr_entry.exists():
        logger.error(f"OCR entrypoint not found: {ocr_entry}")
        return

    logger.info(f"Found {len(pdf_files)} PDF files to process.")
    logger.info(f"Using OCR entrypoint: {ocr_entry}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Markdown dir: {md_dir}")
    logger.info(f"Per-file timeout: {per_file_timeout_s}s")

    for i, pdf_path in enumerate(pdf_files, 1):
        pdf_path = pdf_path.resolve()
        logger.info(f"[{i}/{len(pdf_files)}] Processing: {pdf_path}")

        command = [
            sys.executable,
            str(ocr_entry),
            str(pdf_path),
            "--output_dir",
            str(output_dir),
            "--md_dir",
            str(md_dir),
        ]

        # Start the subprocess in its own process group so we can terminate the whole tree reliably.
        # macOS/Linux: start_new_session=True creates a new process group.
        start_time = time.time()
        try:
            proc = subprocess.Popen(
                command,
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # line-buffered
                start_new_session=True,
            )
        except Exception as e:
            logger.exception(f"Failed to start OCR subprocess for {pdf_path.name}: {e}")
            continue

        try:
            # Poll with a timeout so we can enforce per-file timeout while still streaming output.
            while True:
                rc = proc.poll()
                if rc is not None:
                    break

                elapsed = time.time() - start_time
                if elapsed > per_file_timeout_s:
                    raise TimeoutError(f"Timed out after {per_file_timeout_s}s")

                # Stream any available output (non-blocking-ish due to line buffering)
                # If there's no output, readline() will block, so we stream in a separate helper
                # only once the process ends. Here we just sleep briefly.
                time.sleep(0.2)

            # Process already ended; now stream remaining buffered output (if any).
            try:
                _ = _stream_process_output(proc, pdf_path.name)
            except Exception:
                # If stdout is already closed/None, just continue.
                pass

            if proc.returncode == 0:
                logger.info(f"Successfully processed {pdf_path.name}")
            else:
                logger.error(f"Failed to process {pdf_path.name}. Return code: {proc.returncode}")

        except KeyboardInterrupt:
            logger.warning("Interrupted by user (Ctrl+C). Terminating current OCR subprocess...")
            try:
                # Terminate the whole process group created by start_new_session=True
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            try:
                proc.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            raise

        except TimeoutError as e:
            logger.error(f"{e} while processing {pdf_path.name}. Killing OCR subprocess and continuing...")
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            continue

        except Exception as e:
            logger.exception(f"Exception occurred while processing {pdf_path.name}: {e}")
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            continue


if __name__ == "__main__":
    process_all_files()
