"""Regression coverage for all image upload entry points."""
import asyncio
import io

import pytest
from PIL import Image

from image_uploads import ImageUploadError, MAX_IMAGE_BYTES, store_image_upload


class Uploaded:
    def __init__(self, data: bytes, name="test.png"):
        self.filename = name
        self.stream = io.BytesIO(data)

    async def read(self, count):
        return self.stream.read(count)


def generated_image(fmt: str, size=(128, 128)) -> bytes:
    image = Image.new("RGB", size, color=(20, 80, 130))
    out = io.BytesIO()
    image.save(out, format=fmt)
    return out.getvalue()


@pytest.mark.parametrize("fmt,ext", [("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")])
def test_valid_supported_image(tmp_path, fmt, ext):
    upload = Uploaded(generated_image(fmt), "wrong-file-extension.txt")
    path = asyncio.run(store_image_upload(upload, tmp_path))
    assert path.endswith(ext)
    saved = tmp_path / path.rsplit("/", 1)[-1]
    assert saved.exists()
    with Image.open(saved) as image:
        image.verify()


def test_reject_corrupt_and_truncated_images(tmp_path):
    original = generated_image("PNG")
    for data in (original[:40], original[:-25], b"hello"):
        with pytest.raises(ImageUploadError) as result:
            asyncio.run(store_image_upload(Uploaded(data), tmp_path))
        assert result.value.code in {"invalid", "unsupported"}
    assert list(tmp_path.iterdir()) == []


def test_reject_oversized_image_without_writing(tmp_path):
    with pytest.raises(ImageUploadError) as result:
        asyncio.run(store_image_upload(Uploaded(b"x" * (MAX_IMAGE_BYTES + 1)), tmp_path))
    assert result.value.code == "too_large"
    assert result.value.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_no_image_leaves_existing_image_unchanged(tmp_path):
    assert asyncio.run(store_image_upload(None, tmp_path)) == ""


def test_larger_than_64kb_jpeg_is_not_rejected(tmp_path):
    # Previously verify() saw only 64 KB and rejected valid large JPEGs.
    image = Image.effect_noise((1024, 768), 100)
    output = io.BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=92)
    assert len(output.getvalue()) > 65536
    path = asyncio.run(store_image_upload(Uploaded(output.getvalue(), "test.jpg"), tmp_path))
    assert path.endswith(".jpg")
