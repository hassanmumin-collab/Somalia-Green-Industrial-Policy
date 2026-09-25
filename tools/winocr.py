"""OCR through the Windows built-in engine (Windows.Media.Ocr), used when Tesseract is absent."""
from __future__ import annotations

import asyncio


def available() -> bool:
    try:
        from winrt.windows.media.ocr import OcrEngine
        return OcrEngine.try_create_from_user_profile_languages() is not None
    except Exception:  # noqa: BLE001
        return False


async def _ocr(png: bytes) -> str:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png)
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    engine = OcrEngine.try_create_from_user_profile_languages()
    result = await engine.recognize_async(bitmap)
    return "\n".join(line.text for line in result.lines)


def ocr_png(png: bytes) -> str:
    return asyncio.run(_ocr(png))
