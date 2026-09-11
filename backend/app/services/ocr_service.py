"""
OCR Service — extracts text from receipt/invoice images.
Priority: PaddleOCR → text sidecar file → filename-based fallback.
This graceful fallback means the demo works even without paddlepaddle installed.
"""
import asyncio
import base64
import os
import tempfile
from pathlib import Path
from loguru import logger


async def extract_text_from_image(
    image_data: bytes | None,
    filename: str | None,
    attachments_dir: str | None = None,
) -> tuple[str, str]:
    """
    Returns (raw_text, confidence) where confidence is 'high' | 'low'.
    Tries PaddleOCR, then sidecar .txt, then graceful empty string.
    """
    # ── Try PaddleOCR ────────────────────────────────────────────────────────
    if image_data:
        try:
            text = await _paddle_ocr(image_data)
            if text.strip():
                logger.info("OCR: PaddleOCR succeeded")
                return text, "high"
        except Exception as e:
            logger.warning(f"OCR: PaddleOCR unavailable ({e}), trying fallback")

    # ── Try loading from demo attachments dir ────────────────────────────────
    if filename and attachments_dir:
        # Look for PNG in attachments dir
        img_path = Path(attachments_dir) / filename
        txt_path = img_path.with_suffix(".txt")

        # Try text sidecar first
        if txt_path.exists():
            text = txt_path.read_text(encoding="utf-8")
            logger.info(f"OCR: Using text sidecar {txt_path.name}")
            return text, "high"

        # Try PaddleOCR on the actual file if it exists
        if img_path.exists():
            try:
                image_data = img_path.read_bytes()
                text = await _paddle_ocr(image_data)
                if text.strip():
                    logger.info(f"OCR: PaddleOCR on file {img_path.name}")
                    return text, "high"
            except Exception:
                pass

    logger.warning("OCR: No text extracted — will rely on email body alone")
    return "", "low"


async def _paddle_ocr(image_data: bytes) -> str:
    """Runs PaddleOCR in a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(_paddle_ocr_sync, image_data)


def _paddle_ocr_sync(image_data: bytes) -> str:
    """Synchronous PaddleOCR call."""
    from paddleocr import PaddleOCR  # May raise ImportError if not installed
    import numpy as np
    import cv2

    # Decode image bytes → numpy array
    arr = np.frombuffer(image_data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    result = ocr.ocr(img, cls=True)

    lines = []
    if result and result[0]:
        for line in result[0]:
            if line and len(line) >= 2:
                text_info = line[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                    lines.append(str(text_info[0]))
    return "\n".join(lines)
