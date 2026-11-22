"""Shared, bounded and content-verified PNG, JPEG and WebP uploads."""
from __future__ import annotations

import io
import logging
import secrets
import tempfile
from pathlib import Path

from PIL import Image, ImageFile, UnidentifiedImageError

MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 80_000_000
CHUNK_BYTES = 1024 * 1024
FORMAT_EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
Image.MAX_IMAGE_PIXELS = min(Image.MAX_IMAGE_PIXELS or MAX_IMAGE_PIXELS, MAX_IMAGE_PIXELS)
ImageFile.LOAD_TRUNCATED_IMAGES = False


class ImageUploadError(ValueError):
    def __init__(self, code: str):
        self.code = code
        self.status_code = 413 if code == "too_large" else (500 if code == "write_failed" else 400)
        super().__init__(self.message)

    @property
    def message(self) -> str:
        return {
            "too_large": "Image exceeds the 25 MB upload limit.",
            "unsupported": "Unsupported image format. Upload PNG, JPEG or WebP.",
            "invalid": "The image is damaged or could not be decoded.",
            "write_failed": "The server could not save the image. Please try again.",
        }[self.code]


def _validate_bytes(data: bytes) -> str:
    if not data:
        raise ImageUploadError("invalid")
    signature = (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8\xff")
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )
    if not signature:
        raise ImageUploadError("unsupported")
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            if fmt not in FORMAT_EXTENSIONS:
                raise ImageUploadError("unsupported")
            if img.width * img.height > MAX_IMAGE_PIXELS:
                raise ImageUploadError("invalid")
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
    except ImageUploadError:
        raise
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageUploadError("invalid") from exc
    return FORMAT_EXTENSIONS[fmt]


async def store_image_upload(upload, directory: Path, prefix: str = "image-") -> str:
    """Read at most 25 MB + one byte, verify all bytes, then atomically publish."""
    if not upload or not getattr(upload, "filename", ""):
        return ""
    data = bytearray()
    while True:
        chunk = await upload.read(min(CHUNK_BYTES, MAX_IMAGE_BYTES + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageUploadError("too_large")
    extension = _validate_bytes(bytes(data))
    filename = f"{prefix}{secrets.token_hex(16)}{extension}"
    temporary = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="wb", dir=directory, prefix=".image-", delete=False) as out:
            temporary = Path(out.name)
            out.write(data)
        temporary.replace(directory / filename)
    except OSError as exc:
        logging.getLogger(__name__).exception("Image upload failed")
        raise ImageUploadError("write_failed") from exc
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return f"/static/uploads/{filename}"
