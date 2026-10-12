"""Web arayüzü: konu gir, video üret, izle ve indir.

Çalıştırma:  uvicorn momentum.app:app --reload   ->   http://localhost:8000
"""

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, pipeline

config.OUTPUT_DIR.mkdir(exist_ok=True)
config.MUSIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Momentum")
app.mount("/output", StaticFiles(directory=config.OUTPUT_DIR), name="output")


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    style: str = "sinematik"
    music: str | None = None


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/options")
def options():
    return {
        "styles": list(config.STYLE_PRESETS),
        "music": pipeline.list_music(),
        "mock": config.MOCK,
        "seconds": config.VIDEO_SECONDS,
    }


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if req.style not in config.STYLE_PRESETS:
        raise HTTPException(400, "Bilinmeyen stil")
    job = pipeline.start_job(req.topic.strip(), req.style, req.music or None)
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = pipeline.get_job(job_id)
    if not job:
        raise HTTPException(404, "İş bulunamadı")
    return job.public()


@app.post("/api/music")
async def upload_music(file: UploadFile):
    raw = Path(file.filename or "").name
    name = re.sub(r"[^\w.\- ]", "_", raw).strip().lstrip(".") or "muzik.mp3"
    if not name.lower().endswith((".mp3", ".m4a", ".wav", ".ogg", ".aac")):
        raise HTTPException(400, "Desteklenen formatlar: mp3, m4a, wav, ogg, aac")
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(400, "Dosya 30 MB'tan büyük olamaz")
    (config.MUSIC_DIR / name).write_bytes(data)
    return {"name": name, "music": pipeline.list_music()}
