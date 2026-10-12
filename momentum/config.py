"""Ortak ayarlar: .env yükleme, klasör yolları ve video parametreleri."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MUSIC_DIR = ROOT / "music"
OUTPUT_DIR = ROOT / "output"
STATIC_DIR = Path(__file__).resolve().parent / "static"

CLAUDE_MODEL = os.getenv("MOMENTUM_CLAUDE_MODEL", "claude-opus-5-5")
IMAGE_MODEL = os.getenv("MOMENTUM_IMAGE_MODEL", "gemini-3.1-flash-image")

# API anahtarı olmadan arayüzü ve video birleştirmeyi denemek için sahte mod.
MOCK = os.getenv("MOMENTUM_MOCK", "").lower() in ("1", "true", "yes")

SCENE_COUNT = int(os.getenv("MOMENTUM_SCENES", "5"))
VIDEO_SECONDS = 20
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
TRANSITION_SECONDS = 0.5

# Arayüzdeki stil seçenekleri -> görsel prompt'larına eklenecek İngilizce stil tarifi.
STYLE_PRESETS = {
    "sinematik": "cinematic photography, dramatic golden-hour lighting, shallow depth of field, rich film color grading",
    "anime": "high-quality anime illustration, Makoto Shinkai style skies, vibrant colors, detailed backgrounds",
    "3d": "stylized 3D render, Pixar-like characters, soft global illumination, warm color palette",
    "illustrasyon": "modern flat digital illustration, bold shapes, limited harmonious color palette, clean lines",
    "suluboya": "soft watercolor painting, textured paper, gentle pastel tones, loose brush strokes",
}
