"""Opt-in local OCR for a user-selected local image; never an image sanitizer."""
import asyncio
import shutil
from pathlib import Path
from helpers.api import ApiHandler
from helpers import files


def read_image(value):
    if not shutil.which("tesseract"):
        raise ValueError("Local OCR is unavailable: install Tesseract in the Agent Zero environment.")
    import pytesseract
    from PIL import Image
    root = Path(files.get_abs_path(files.USER_DIR)).resolve()
    image = Path(str(value)).resolve()
    if not image.is_relative_to(root) or not image.is_file() or image.stat().st_size>32*1024*1024:
        raise ValueError("Choose a local image below Agent Zero's user directory (maximum 32 MB).")
    with Image.open(image) as source:
        if source.width*source.height>40_000_000:
            raise ValueError("Image is too large for the local OCR preview.")
        return pytesseract.image_to_string(source, timeout=30)[:50000]


class Ocr(ApiHandler):
    async def process(self, input, request):
        if input.get("action")=="status":
            try:
                import pytesseract
                available = bool(shutil.which("tesseract"))
            except ImportError:
                available = False
            return {"ok":True,"available":available}
        try:
            text = await asyncio.to_thread(read_image,input.get("path", ""))
            return {"ok":True,"text":text,"notice":"Local OCR extracts text only. It does not remove personal details from the original image."}
        except Exception:
            return {"ok":False,"error":"Local OCR failed. Check image path, format and installed Tesseract. No external request was made."}
