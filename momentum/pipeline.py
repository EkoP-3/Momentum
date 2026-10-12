"""Konu -> sahne planı -> görseller -> video akışını arka planda yürütür ve ilerlemeyi tutar."""

import json
import random
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config, imagegen, planner, video


@dataclass
class Job:
    id: str
    topic: str
    style: str
    music: str | None
    stage: str = "queued"  # queued -> planning -> images -> video -> done | error
    message: str = "Sırada bekliyor"
    video_title: str = ""
    scenes: list[dict] = field(default_factory=list)
    images: list[str | None] = field(default_factory=list)
    video: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        return asdict(self)


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def start_job(topic: str, style: str, music: str | None) -> Job:
    job = Job(id=uuid.uuid4().hex[:10], topic=topic, style=style, music=music)
    with _lock:
        _jobs[job.id] = job
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job


def _url(path: Path) -> str:
    return "/output/" + path.relative_to(config.OUTPUT_DIR).as_posix()


def _run(job: Job) -> None:
    out_dir = config.OUTPUT_DIR / job.id
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        job.stage, job.message = "planning", "Konu sahnelere ayrılıyor…"
        plan = planner.plan_scenes(job.topic, job.style)
        job.video_title = plan["video_title"]
        job.scenes = [
            {k: s[k] for k in ("title", "description", "image_prompt", "motion")} for s in plan["scenes"]
        ]
        job.images = [None] * len(job.scenes)
        (out_dir / "scenes.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        job.stage, job.message = "images", f"Görseller üretiliyor (0/{len(job.scenes)})"

        def on_image(i: int, path: Path) -> None:
            with _lock:
                job.images[i] = _url(path)
                done = sum(1 for img in job.images if img)
            job.message = f"Görseller üretiliyor ({done}/{len(job.scenes)})"

        images = imagegen.generate_images([s["full_prompt"] for s in plan["scenes"]], out_dir, on_image)

        job.stage, job.message = "video", "Video birleştiriliyor…"
        music = _resolve_music(job.music)
        out = video.build_video(images, [s["motion"] for s in plan["scenes"]], out_dir / "video.mp4", music)
        job.video = _url(out)
        job.stage, job.message = "done", "Video hazır!"
    except (planner.PlannerError, imagegen.ImageGenError, video.VideoError) as exc:
        job.stage, job.error, job.message = "error", str(exc), "Hata oluştu"
    except Exception as exc:  # beklenmeyen hatalar da arayüzde görünsün
        job.stage, job.error, job.message = "error", f"Beklenmeyen hata: {exc}", "Hata oluştu"


def list_music() -> list[str]:
    if not config.MUSIC_DIR.exists():
        return []
    exts = {".mp3", ".m4a", ".wav", ".ogg", ".aac"}
    return sorted(p.name for p in config.MUSIC_DIR.iterdir() if p.suffix.lower() in exts)


def _resolve_music(name: str | None) -> Path | None:
    if not name:
        return None
    if name == "random":
        tracks = list_music()
        return config.MUSIC_DIR / random.choice(tracks) if tracks else None
    path = (config.MUSIC_DIR / name).resolve()
    # Yalnızca music/ klasöründeki dosyalara izin ver.
    if path.parent != config.MUSIC_DIR.resolve() or not path.is_file():
        return None
    return path
