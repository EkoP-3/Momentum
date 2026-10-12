"""Sahne prompt'larından Gemini görsel modeliyle 9:16 görseller üretir.

İlk sahne önce üretilir; kalan sahnelere referans olarak verilir ki karakter,
stil ve renk paleti tüm videoda tutarlı kalsın.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from . import config


class ImageGenError(RuntimeError):
    pass


SAFE_SUFFIX = " Family-friendly, uplifting, no text, no violence."
REFERENCE_INSTRUCTION = (
    "Use the attached image only as a visual reference: keep the same main character "
    "(face, hair, clothing), the same art style and the same color palette. "
    "Create a NEW vertical 9:16 scene: "
)
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def generate_images(
    prompts: list[str],
    out_dir: Path,
    on_done: Callable[[int, Path], None] = lambda i, p: None,
) -> list[Path]:
    """Prompt'lardan görsel üretir, her biri bitince on_done(index, path) çağrılır."""
    out_dir.mkdir(parents=True, exist_ok=True)
    client = None if config.MOCK else _client()

    def work(i: int, reference: tuple[bytes, str] | None) -> Path:
        if config.MOCK:
            path = out_dir / f"scene_{i + 1}.png"
            _mock_image(prompts[i], i, path)
        else:
            data, mime = _generate_one(client, prompts[i], reference)
            path = out_dir / f"scene_{i + 1}{EXTENSIONS.get(mime, '.png')}"
            path.write_bytes(data)
        on_done(i, path)
        return path

    first = work(0, None)
    reference = None
    if not config.MOCK:
        mime = next((m for m, ext in EXTENSIONS.items() if ext == first.suffix), "image/png")
        reference = (first.read_bytes(), mime)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rest = list(pool.map(lambda i: work(i, reference), range(1, len(prompts))))
    return [first, *rest]


def _client():
    from google import genai

    try:
        # GEMINI_API_KEY (veya GOOGLE_API_KEY) ortam değişkeninden okunur.
        return genai.Client()
    except ValueError as exc:
        raise ImageGenError("GEMINI_API_KEY eksik (.env dosyasını kontrol edin).") from exc


def _generate_one(client, prompt: str, reference: tuple[bytes, str] | None, attempts: int = 3) -> tuple[bytes, str]:
    from google.genai import errors, types

    last_problem = "bilinmeyen hata"
    for attempt in range(attempts):
        # Güvenlik filtresine takılırsa prompt'u yumuşatarak yeniden dener.
        text = prompt + (SAFE_SUFFIX if attempt else "")
        contents: list = [text]
        if reference:
            contents = [types.Part.from_bytes(data=reference[0], mime_type=reference[1]), REFERENCE_INSTRUCTION + text]
        try:
            response = client.models.generate_content(
                model=config.IMAGE_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio="9:16"),
                ),
            )
        except errors.ClientError as exc:
            if exc.code in (401, 403) or "API key not valid" in (exc.message or ""):
                raise ImageGenError("GEMINI_API_KEY geçersiz veya bu modele erişim yok.") from exc
            if exc.code == 404:
                raise ImageGenError(
                    f"'{config.IMAGE_MODEL}' modeli bulunamadı; .env içinde MOMENTUM_IMAGE_MODEL ile değiştirin."
                ) from exc
            if exc.code != 429:
                raise ImageGenError(f"Görsel isteği reddedildi ({exc.code}): {exc.message}") from exc
            last_problem = "hız sınırı"
        except errors.ServerError as exc:
            last_problem = f"sunucu hatası ({exc.code})"
        else:
            for part in response.parts or []:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data, part.inline_data.mime_type or "image/png"
            last_problem = _empty_reason(response)
        time.sleep(2 ** attempt)
    raise ImageGenError(f"Görsel üretilemedi: {last_problem}")


def _empty_reason(response) -> str:
    feedback = response.prompt_feedback
    if feedback and feedback.block_reason:
        return f"güvenlik filtresi ({feedback.block_reason})"
    if response.candidates and response.candidates[0].finish_reason:
        return f"model görsel döndürmedi ({response.candidates[0].finish_reason})"
    return "boş yanıt"


def _mock_image(prompt: str, index: int, path: Path) -> None:
    """API olmadan test için renk geçişli, yazılı bir yer tutucu görsel çizer."""
    from PIL import Image, ImageDraw

    palettes = [
        ((20, 24, 82), (240, 120, 60)),
        ((10, 60, 70), (250, 210, 90)),
        ((60, 20, 70), (90, 200, 220)),
        ((30, 30, 30), (230, 90, 120)),
        ((15, 70, 40), (250, 240, 200)),
    ]
    top, bottom = palettes[index % len(palettes)]
    w, h = 768, 1365
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    draw.ellipse([w * 0.3, h * 0.38, w * 0.7, h * 0.6], fill=(255, 255, 255))
    draw.text((40, 60), f"Sahne {index + 1}", fill=(255, 255, 255))
    draw.text((40, 90), prompt[:80], fill=(255, 255, 255))
    img.save(path)
