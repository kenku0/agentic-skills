#!/usr/bin/env python3
"""
Gemini Slides Generator

Generate professional visual content using Gemini's native image generation.
Default: Direct API (reliable) at 1K resolution (draft mode).
Use --batch for 50% cost savings (but unreliable), --final for 4K production quality.

Consistency features:
    --no-chain    Disable reference chaining (ON by default for multi-slide decks)
    --eval        Enable automated brand evaluation loop after each slide
    --eval-cycles Max correction cycles per slide (default: 3, requires --eval)

Usage:
    # Generate slides (direct API, 1K draft, default — with auto-chaining)
    python3 gemini_slides.py --prompts '[{"filename": "slide-01.png", "prompt": "..."}]' --output slides/260124-topic/

    # Final mode (4K production quality)
    python3 gemini_slides.py --prompts '...' --output ... --final

    # With brand evaluation loop (auto-corrects typography/color drift)
    python3 gemini_slides.py --prompts '...' --output ... --eval

    # Disable chaining (each slide generated independently)
    python3 gemini_slides.py --prompts '...' --output ... --no-chain

    # Image-to-image with reference
    python3 gemini_slides.py --prompts '[{
        "filename": "variation.png",
        "prompt": "Create a variation with blue colors",
        "reference_image": "path/to/existing/image.png"
    }]' --output slides/output/

    # With style_spec for evaluation (included in prompt JSON)
    python3 gemini_slides.py --eval --prompts '[{
        "filename": "slide-01.png",
        "prompt": "...",
        "style_spec": "Canvas: 1920x1080, bg #F8F8F6..."
    }]' --output slides/output/

    # Smoke test
    python3 gemini_slides.py --test

Environment:
    GEMINI_API_KEY or GOOGLE_API_KEY - Gemini API key (required)

Note: Batch API is 50% cheaper but has known reliability issues (jobs stuck in
      PENDING for 24+ hours). Use --batch only for non-urgent, cost-sensitive work.
      Use --final for 4K production quality (default is 1K draft).
"""

import argparse
import base64
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# Model for image generation
IMAGE_MODEL = "gemini-3-pro-image-preview"

# Fallback for direct mode only
FALLBACK_MODELS = [
    "gemini-2.0-flash-exp",
]

# Model for slide evaluation (cheaper, faster — text analysis only)
EVAL_MODEL = "gemini-2.0-flash"

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Batch API polling config
BATCH_POLL_INTERVAL = 5  # seconds
BATCH_MAX_WAIT = 300  # 5 minutes max wait


# =============================================================================
# PDF GENERATION
# =============================================================================

def create_pdf(output_dir: Path) -> Optional[str]:
    """
    Combine all slide images into a single PDF.

    Only creates PDF for multi-slide outputs (2+ images).
    Uses img2pdf for lossless conversion (no re-compression).

    Args:
        output_dir: Directory containing slide-*.png files

    Returns:
        Path to created PDF, or None if skipped/failed
    """
    try:
        import img2pdf
    except ImportError:
        print("Warning: img2pdf not installed, skipping PDF generation", file=sys.stderr)
        print("  Install with: pip install img2pdf", file=sys.stderr)
        return None

    # Find all slide images, sorted by name
    images = sorted(output_dir.glob("slide-*.png"))

    if len(images) < 2:
        # Only create PDF for multi-slide outputs
        return None

    pdf_path = output_dir / "slides.pdf"

    try:
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert([str(img) for img in images]))
        return str(pdf_path)
    except Exception as e:
        print(f"Warning: PDF generation failed: {e}", file=sys.stderr)
        return None


def get_api_key() -> Optional[str]:
    """Get Gemini API key (env first, then repo .env as fallback)."""

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key

    # Fallback: read repo `.env` (matches other skills tooling in this workspace).
    try:
        repo_root = Path(__file__).resolve().parents[3]
        dotenv_path = repo_root / ".env"
        if not dotenv_path.exists():
            return None
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key not in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                continue
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if value:
                return value
    except Exception:
        return None

    return None


def check_environment() -> tuple[bool, str]:
    """Check if environment is properly configured."""
    api_key = get_api_key()
    if not api_key:
        return False, "GEMINI_API_KEY or GOOGLE_API_KEY not set in environment"
    return True, "Environment OK"


def redact_secrets(text: str) -> str:
    """Best-effort redaction for API keys in exception strings/logs."""
    if not text:
        return text
    # Gemini API key is passed as a `key=` query param; ensure it never hits logs.
    return re.sub(r"(key=)[^&\\s]+", r"\\1REDACTED", text)


def load_reference_image(image_path: str) -> tuple[str, str]:
    """
    Load an image file and return base64-encoded data with MIME type.

    Args:
        image_path: Path to the image file (absolute or relative to cwd)

    Returns:
        Tuple of (base64_data, mime_type)

    Raises:
        FileNotFoundError: If image doesn't exist
        ValueError: If file extension is unsupported
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Reference image not found: {image_path}")

    image_bytes = path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    mime_map = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
    }
    mime_type = mime_map.get(path.suffix.lower())
    if not mime_type:
        raise ValueError(f"Unsupported image format: {path.suffix}")

    return image_base64, mime_type


# =============================================================================
# ARCHIVE
# =============================================================================

def archive_if_exists(output_path: Path, output_dir: Path) -> Optional[str]:
    """
    If output_path exists, move it to slides/_archive/ with timestamp.

    This preserves previous versions when regenerating slides, allowing
    users to compare before/after or recover if regeneration is worse.

    Args:
        output_path: Path to the file that will be overwritten
        output_dir: The slide project directory (e.g., slides/260126-topic/)

    Returns:
        Path to archived file, or None if nothing archived
    """
    if not output_path.exists():
        return None

    # Get project name from output_dir (e.g., "260124-sample-project")
    project_name = output_dir.name

    # Create archive dir at slides/_archive/ (sibling to project folders)
    slides_root = output_dir.parent
    archive_dir = slides_root / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Generate archive filename: project_filename_timestamp.ext
    # e.g., 260124-sample-project_slide-01_20260124-143522.png
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_name = f"{project_name}_{output_path.stem}_{timestamp}{output_path.suffix}"
    archive_path = archive_dir / archive_name

    # Move file to archive
    shutil.move(str(output_path), str(archive_path))
    print(f"  Archived: {output_path.name} → _archive/{archive_name}", file=sys.stderr)

    return str(archive_path)


# =============================================================================
# BATCH API (50% cheaper, default for 2+ images)
# =============================================================================

def create_batch_job(prompts: list[dict], resolution: str = "1K") -> tuple[Optional[str], Optional[str]]:
    """
    Create a batch job with inline requests.

    Args:
        prompts: List of {"filename": str, "prompt": str}
        resolution: "1K" (draft), "2K" (standard), or "4K" (final)

    Returns:
        Tuple of (job_name, error_message)
    """
    api_key = get_api_key()
    if not api_key:
        return None, "GEMINI_API_KEY not set"

    url = f"{API_BASE}/{IMAGE_MODEL}:batchGenerateContent?key={api_key}"

    # Build inline requests
    inline_requests = []
    for i, item in enumerate(prompts):
        inline_requests.append({
            "request": {
                "contents": [{
                    "parts": [{"text": item["prompt"]}]
                }],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "imageConfig": {
                        "aspectRatio": "16:9",
                        "imageSize": resolution
                    }
                }
            },
            "metadata": {
                "key": item["filename"]
            }
        })

    payload = {
        "batch": {
            "display_name": f"slides-batch-{int(time.time())}",
            "input_config": {
                "requests": {
                    "requests": inline_requests
                }
            }
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=60)

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "Unknown error"
            return None, f"Batch create failed ({response.status_code}): {error_detail}"

        data = response.json()
        job_name = data.get("name")

        if not job_name:
            return None, f"No job name in response: {data}"

        return job_name, None

    except Exception as e:
        return None, f"Error creating batch: {redact_secrets(str(e))}"


def poll_batch_status(job_name: str) -> tuple[Optional[dict], Optional[str]]:
    """
    Poll batch job status until completion.

    Returns:
        Tuple of (job_data, error_message)
    """
    api_key = get_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/{job_name}?key={api_key}"

    completed_states = {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED"
    }

    start_time = time.time()

    while True:
        try:
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                return None, f"Status check failed: {response.status_code}"

            data = response.json()

            # Check metadata for state
            state = data.get("metadata", {}).get("state", "UNKNOWN")

            if state in completed_states:
                return data, None

            elapsed = time.time() - start_time
            if elapsed > BATCH_MAX_WAIT:
                return None, f"Batch timeout after {BATCH_MAX_WAIT}s (state: {state})"

            print(f"  Batch status: {state} (elapsed: {int(elapsed)}s)...", file=sys.stderr)
            time.sleep(BATCH_POLL_INTERVAL)

        except Exception as e:
            return None, f"Error polling status: {redact_secrets(str(e))}"


def extract_batch_results(job_data: dict, output_dir: Path) -> list[dict]:
    """
    Extract images from completed batch job and save to disk.

    Returns:
        List of {"filename": str, "status": str, ...}
    """
    results = []

    # Results are in response.inlinedResponses
    inlined_responses = job_data.get("response", {}).get("inlinedResponses", [])

    for resp in inlined_responses:
        # Get the key (filename) from metadata
        key = resp.get("metadata", {}).get("key", f"image-{len(results)+1}.png")

        if "response" in resp and resp["response"]:
            # Extract image from response
            candidates = resp["response"].get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        try:
                            image_bytes = base64.b64decode(part["inlineData"]["data"])
                            output_path = output_dir / key
                            # Archive existing file before overwriting
                            archive_if_exists(output_path, output_dir)
                            output_path.write_bytes(image_bytes)
                            results.append({
                                "filename": key,
                                "status": "success",
                                "path": str(output_path),
                                "model": IMAGE_MODEL,
                                "mode": "batch"
                            })
                            print(f"  Saved: {output_path}", file=sys.stderr)
                        except Exception as e:
                            results.append({
                                "filename": key,
                                "status": "error",
                                "error": f"Failed to decode image: {e}"
                            })
                        break
                else:
                    results.append({
                        "filename": key,
                        "status": "error",
                        "error": "No image in response"
                    })
            else:
                results.append({
                    "filename": key,
                    "status": "error",
                    "error": "No candidates in response"
                })
        elif "error" in resp:
            results.append({
                "filename": key,
                "status": "error",
                "error": str(resp["error"])
            })
        else:
            results.append({
                "filename": key,
                "status": "error",
                "error": "Unknown response format"
            })

    return results


def generate_images_batch_api(prompts: list[dict], output_dir: Path, resolution: str = "1K") -> list[dict]:
    """
    Generate images using Batch API (50% cheaper).

    Args:
        prompts: List of {"filename": str, "prompt": str}
        output_dir: Directory to save images
        resolution: "1K" (draft), "2K" (standard), or "4K" (final)

    Returns:
        List of {"filename": str, "status": str, ...}
    """
    print(f"Creating batch job for {len(prompts)} images at {resolution} resolution (50% cheaper)...", file=sys.stderr)

    # Create batch job
    job_name, error = create_batch_job(prompts, resolution)
    if error:
        return [{"filename": p["filename"], "status": "error", "error": error} for p in prompts]

    print(f"  Batch job created: {job_name}", file=sys.stderr)

    # Poll for completion
    job_data, error = poll_batch_status(job_name)
    if error:
        return [{"filename": p["filename"], "status": "error", "error": error} for p in prompts]

    # Check final state
    state = job_data.get("metadata", {}).get("state", "UNKNOWN")
    if state != "JOB_STATE_SUCCEEDED":
        error_msg = job_data.get("error", {}).get("message", f"Job failed with state: {state}")
        return [{"filename": p["filename"], "status": "error", "error": error_msg} for p in prompts]

    print(f"  Batch completed successfully!", file=sys.stderr)

    # Extract and save results
    return extract_batch_results(job_data, output_dir)


# =============================================================================
# DIRECT API (faster, full price)
# =============================================================================

def generate_image_direct(
    prompt: str,
    model_name: str,
    resolution: str = "1K",
    reference_images: Optional[list[str]] = None,
    raw_reference_images: Optional[list[tuple[bytes, str]]] = None,
) -> tuple[Optional[bytes], Optional[str]]:
    """
    Generate a single image using direct REST API.

    Args:
        prompt: The image generation prompt
        model_name: Gemini model to use
        resolution: "1K" (draft), "2K" (standard), or "4K" (final)
        reference_images: Optional list of image paths for image-to-image generation
        raw_reference_images: Optional list of (bytes, mime_type) for in-memory images
                              (e.g., previous slide for chaining — no temp files)

    Returns:
        Tuple of (image_bytes, error_message)
    """
    api_key = get_api_key()
    if not api_key:
        return None, "GEMINI_API_KEY not set"

    url = f"{API_BASE}/{model_name}:generateContent?key={api_key}"

    # Build parts array: file refs → raw refs → text prompt
    parts = []

    for ref_path in (reference_images or []):
        try:
            img_b64, mime = load_reference_image(ref_path)
            parts.append({"inline_data": {"mime_type": mime, "data": img_b64}})
        except (FileNotFoundError, ValueError) as e:
            return None, str(e)

    # Raw in-memory references (e.g., previous slide for chaining)
    for img_bytes, mime in (raw_reference_images or []):
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        parts.append({"inline_data": {"mime_type": mime, "data": img_b64}})

    parts.append({"text": prompt})

    # Different config for Gemini 3 vs Gemini 2
    if "gemini-3" in model_name:
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "imageConfig": {
                    "aspectRatio": "16:9",
                    "imageSize": resolution
                }
            }
        }
    else:
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }

    try:
        response = requests.post(url, json=payload, timeout=120)

        if response.status_code == 404:
            return None, f"Model {model_name} not found"

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "Unknown error"
            return None, f"API error {response.status_code}: {error_detail}"

        data = response.json()

        if "candidates" in data and data["candidates"]:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "inlineData" in part:
                        image_bytes = base64.b64decode(part["inlineData"]["data"])
                        return image_bytes, None

        return None, "No image in response"

    except requests.Timeout:
        return None, "Request timed out (120s)"
    except requests.RequestException as e:
        return None, f"Request error: {redact_secrets(str(e))}"
    except Exception as e:
        return None, f"Error: {redact_secrets(str(e))}"


def generate_with_fallback(
    prompt: str,
    resolution: str = "1K",
    reference_images: Optional[list[str]] = None,
    raw_reference_images: Optional[list[tuple[bytes, str]]] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Try primary model, then fallbacks.

    Args:
        prompt: The image generation prompt
        resolution: "1K" (draft), "2K" (standard), or "4K" (final)
        reference_images: Optional list of image paths for image-to-image generation
        raw_reference_images: Optional list of (bytes, mime_type) for in-memory images

    Returns:
        Tuple of (image_bytes, error_message, model_used)
    """
    models = [IMAGE_MODEL] + FALLBACK_MODELS
    for model in models:
        image_bytes, error = generate_image_direct(
            prompt, model, resolution, reference_images, raw_reference_images
        )
        if image_bytes:
            return image_bytes, None, model
        print(f"  Model {model}: {error}", file=sys.stderr)
    return None, "All models failed", None


# =============================================================================
# EVALUATION LOOP (Phase 2: automated brand consistency checking)
# =============================================================================


def evaluate_slide(image_bytes: bytes, style_spec: str) -> list[dict]:
    """
    Send generated slide to Gemini Flash for brand evaluation.

    Args:
        image_bytes: The generated slide image
        style_spec: The style specification to evaluate against

    Returns:
        List of violations: [{"element", "expected", "actual", "severity"}]
        Fails open — returns empty list on any error.
    """
    api_key = get_api_key()
    if not api_key or not style_spec:
        return []

    url = f"{API_BASE}/{EVAL_MODEL}:generateContent?key={api_key}"

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

    eval_prompt = (
        "Analyze this slide image against the following style specification.\n"
        "Return ONLY a JSON array of violations found. Each violation object:\n"
        '- "element": what element has the issue (e.g., "title", "background", "underline")\n'
        '- "expected": what the spec requires\n'
        '- "actual": what you observe in the image\n'
        '- "severity": "high" (wrong color/font/layout) or "low" (minor spacing)\n\n'
        "If the slide matches the spec perfectly, return an empty array: []\n\n"
        f"STYLE SPECIFICATION:\n{style_spec}\n\n"
        "Return ONLY valid JSON, no markdown formatting."
    )

    parts = [
        {"inline_data": {"mime_type": "image/png", "data": img_b64}},
        {"text": eval_prompt},
    ]

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code != 200:
            return []

        data = response.json()
        text = ""
        if "candidates" in data and data["candidates"]:
            resp_parts = data["candidates"][0].get("content", {}).get("parts", [])
            for part in resp_parts:
                if "text" in part:
                    text = part["text"]
                    break

        if not text:
            return []

        violations = json.loads(text)
        if isinstance(violations, list):
            return violations
        return []
    except Exception:
        return []


def auto_correct_prompt(original_prompt: str, violations: list[dict]) -> str:
    """Prepend corrective instructions based on evaluation violations."""
    if not violations:
        return original_prompt

    corrections = []
    for v in violations:
        element = v.get("element", "unknown")
        expected = v.get("expected", "")
        actual = v.get("actual", "")
        corrections.append(f"- {element}: MUST be {expected} (was incorrectly {actual})")

    correction_block = "\n".join(corrections)
    return (
        f"CRITICAL CORRECTIONS (previous attempt had these errors — fix them):\n"
        f"{correction_block}\n\n"
        f"{original_prompt}"
    )


def generate_with_evaluation(
    prompt: str,
    resolution: str = "1K",
    reference_images: Optional[list[str]] = None,
    raw_reference_images: Optional[list[tuple[bytes, str]]] = None,
    style_spec: Optional[str] = None,
    max_cycles: int = 3,
) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Generate image with evaluation loop: generate → evaluate → correct → regenerate.

    Args:
        prompt: The image generation prompt
        resolution: Image resolution
        reference_images: File-based reference image paths
        raw_reference_images: In-memory reference images (bytes, mime_type)
        style_spec: Style specification for evaluation
        max_cycles: Maximum generate-evaluate-correct cycles

    Returns:
        Tuple of (image_bytes, error_message, model_used)
    """
    current_prompt = prompt

    for cycle in range(max_cycles):
        image_bytes, error, model_used = generate_with_fallback(
            current_prompt, resolution, reference_images, raw_reference_images
        )

        if not image_bytes:
            return None, error, None

        # No spec to evaluate, or last cycle — return as-is
        if not style_spec or cycle == max_cycles - 1:
            return image_bytes, None, model_used

        # Evaluate against style spec
        violations = evaluate_slide(image_bytes, style_spec)
        high_severity = [v for v in violations if v.get("severity") == "high"]

        if not high_severity:
            if cycle > 0:
                print(f"    Eval cycle {cycle + 1}: PASS (no high-severity violations)", file=sys.stderr)
            return image_bytes, None, model_used

        print(f"    Eval cycle {cycle + 1}: {len(high_severity)} violation(s) found, correcting...", file=sys.stderr)
        for v in high_severity:
            print(f"      - {v.get('element', '?')}: expected {v.get('expected', '?')}, got {v.get('actual', '?')}", file=sys.stderr)

        # Auto-correct prompt for next cycle
        current_prompt = auto_correct_prompt(prompt, high_severity)

    # Should not reach here, but return last attempt
    return image_bytes, None, model_used


# =============================================================================
# DIRECT API ORCHESTRATION
# =============================================================================


def generate_images_direct(
    prompts: list[dict],
    output_dir: Path,
    resolution: str = "1K",
    chain: bool = True,
    eval_mode: bool = False,
    eval_cycles: int = 3,
) -> list[dict]:
    """
    Generate images using direct API (sequential, full price).

    Args:
        prompts: List of {"filename": str, "prompt": str,
                 "reference_image"?: str, "reference_images"?: list[str],
                 "style_spec"?: str}
        output_dir: Directory to save images
        resolution: "1K" (draft), "2K" (standard), or "4K" (final)
        chain: If True, pass previous slide as reference for consistency
        eval_mode: If True, evaluate each slide against style_spec and auto-correct
        eval_cycles: Max evaluation-correction cycles per slide

    Returns:
        List of {"filename": str, "status": str, ...}
    """
    results = []
    prev_image_bytes: Optional[bytes] = None

    for i, item in enumerate(prompts):
        filename = item["filename"]
        prompt = item["prompt"]
        style_spec = item.get("style_spec")

        # Normalize: support both "reference_image" (string) and "reference_images" (array)
        ref_images = item.get("reference_images")  # New: array
        if not ref_images:
            single_ref = item.get("reference_image")  # Legacy: single string
            ref_images = [single_ref] if single_ref else None

        # Build raw references for chaining
        raw_refs: Optional[list[tuple[bytes, str]]] = None
        chain_label = ""
        if chain and prev_image_bytes is not None and i > 0:
            raw_refs = [(prev_image_bytes, "image/png")]
            chain_label = " [chained]"
            # Append chaining instruction to prompt
            prompt = (
                prompt
                + "\n\nREFERENCE IMAGE NOTE: One of the reference images is the "
                "PREVIOUS SLIDE in this deck. Match its exact typography, font sizes, "
                "spacing, colors, underline style, and layout positioning. Only change "
                "the text content as specified above."
            )

        ref_label = f" (with {len(ref_images)} reference(s))" if ref_images else ""
        print(f"[{i+1}/{len(prompts)}] Generating: {filename} at {resolution}{ref_label}{chain_label}...", file=sys.stderr)

        if eval_mode and style_spec:
            image_bytes, error, model_used = generate_with_evaluation(
                prompt, resolution, ref_images, raw_refs, style_spec, eval_cycles
            )
        else:
            image_bytes, error, model_used = generate_with_fallback(
                prompt, resolution, ref_images, raw_refs
            )

        if image_bytes:
            output_path = output_dir / filename
            # Archive existing file before overwriting
            archive_if_exists(output_path, output_dir)
            output_path.write_bytes(image_bytes)
            results.append({
                "filename": filename,
                "status": "success",
                "path": str(output_path),
                "model": model_used,
                "mode": "direct"
            })
            print(f"  Saved: {output_path} (using {model_used})", file=sys.stderr)
            # Track for chaining
            prev_image_bytes = image_bytes
        else:
            results.append({
                "filename": filename,
                "status": "error",
                "error": error or "Unknown error"
            })
            print(f"  Error: {error}", file=sys.stderr)

        if i < len(prompts) - 1:
            time.sleep(1)

    return results


# =============================================================================
# SMOKE TEST
# =============================================================================

def run_smoke_test() -> bool:
    """Run a smoke test to verify API connectivity."""
    print("Running smoke test...", file=sys.stderr)

    ok, msg = check_environment()
    if not ok:
        print(f"Environment check failed: {msg}", file=sys.stderr)
        return False
    print(f"Environment: {msg}", file=sys.stderr)

    test_prompt = """
    Create a simple test image:
    - A solid teal (#0D9488) square on an off-white (#F8F8F6) background
    - The word "TEST" in dark slate (#1E293B) centered in the square
    - Minimal, clean design
    """

    print("Testing direct API...", file=sys.stderr)
    image_bytes, error, model_used = generate_with_fallback(test_prompt)

    if image_bytes:
        print(f"Success! Generated {len(image_bytes)} bytes using {model_used}", file=sys.stderr)
        print("Smoke test PASSED", file=sys.stderr)
        return True
    else:
        print(f"Failed: {error}", file=sys.stderr)
        print("Smoke test FAILED", file=sys.stderr)
        return False


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate images using Gemini API")
    parser.add_argument("--prompts", help="JSON array of {filename, prompt} objects")
    parser.add_argument("--output", help="Output directory path")
    parser.add_argument("--test", action="store_true", help="Run smoke test")
    parser.add_argument("--direct", action="store_true",
                        help="[Default] Use direct API (reliable, immediate results).")
    parser.add_argument("--batch", action="store_true",
                        help="Use batch API (50%% cheaper but unreliable - jobs often stuck in PENDING).")
    parser.add_argument("--final", action="store_true",
                        help="Generate at 4K resolution (production quality). Default is 1K (draft).")
    parser.add_argument("--no-chain", action="store_true",
                        help="Disable reference chaining between slides (chaining is ON by default).")
    parser.add_argument("--eval", action="store_true",
                        help="Enable automated brand evaluation loop after each slide.")
    parser.add_argument("--eval-cycles", type=int, default=3,
                        help="Max evaluation-correction cycles per slide (default: 3, requires --eval).")

    args = parser.parse_args()

    if args.test:
        success = run_smoke_test()
        sys.exit(0 if success else 1)

    if not args.prompts or not args.output:
        parser.error("--prompts and --output are required (unless using --test)")

    ok, msg = check_environment()
    if not ok:
        print(json.dumps({"error": msg}))
        sys.exit(1)

    try:
        prompts = json.loads(args.prompts)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Decide which API to use
    # Default: direct (reliable). Use --batch for 50% cost savings (but unreliable).
    use_batch = args.batch

    # Decide resolution: 1K (draft, default) or 4K (final)
    resolution = "4K" if args.final else "1K"
    resolution_label = "production" if args.final else "draft"

    if use_batch:
        print(f"Using batch API (50% cheaper, but unreliable) at {resolution} resolution ({resolution_label}).", file=sys.stderr)
        print("Warning: Batch API often gets stuck in PENDING state for 24+ hours.", file=sys.stderr)
        if not args.final:
            print("Use --final for 4K production quality.", file=sys.stderr)
    else:
        chain_status = "OFF (--no-chain)" if args.no_chain else "ON"
        eval_status = f"ON ({args.eval_cycles} cycles)" if args.eval else "OFF"
        print(f"Using direct API (default, reliable) at {resolution} resolution ({resolution_label}).", file=sys.stderr)
        print(f"  Chaining: {chain_status} | Eval: {eval_status}", file=sys.stderr)
        if not args.final:
            print("Use --final for 4K production quality. Use --batch for 50% cost savings.", file=sys.stderr)

    if use_batch:
        results = generate_images_batch_api(prompts, output_dir, resolution)
    else:
        results = generate_images_direct(
            prompts, output_dir, resolution,
            chain=not args.no_chain,
            eval_mode=args.eval,
            eval_cycles=args.eval_cycles,
        )

    # Auto-generate PDF for multi-slide outputs
    successful_images = sum(1 for r in results if r.get("status") == "success")
    pdf_path = None
    if successful_images >= 2:
        pdf_path = create_pdf(output_dir)
        if pdf_path:
            print(f"PDF created: {pdf_path}", file=sys.stderr)

    output = {"results": results}
    if pdf_path:
        output["pdf"] = pdf_path

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
