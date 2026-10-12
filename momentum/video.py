"""Görselleri Ken Burns hareketi ve geçişlerle tam 20 saniyelik dikey videoya dönüştürür."""

import subprocess
from pathlib import Path

from . import config

TRANSITIONS = ["fade", "slideup", "circleopen", "smoothleft", "dissolve", "radial", "wipeup"]

# Görsel çıktı çözünürlüğünün kaç katına büyütülüp hareket ettirilir; zoompan'in
# piksel yuvarlamasından kaynaklanan titremeyi azaltır.
UPSCALE = 2
ZOOM = 0.18  # zoom/pan hareketinin genliği


class VideoError(RuntimeError):
    pass


def scene_frame_counts(n_scenes: int) -> tuple[list[int], int]:
    """Toplamı geçişlerle birlikte tam VIDEO_SECONDS edecek sahne kare sayılarını hesaplar."""
    total = config.VIDEO_SECONDS * config.FPS
    trans = round(config.TRANSITION_SECONDS * config.FPS)
    # n sahne, n-1 geçişte üst üste biner: sum(frames) - (n-1)*trans == total
    needed = total + (n_scenes - 1) * trans
    base, extra = divmod(needed, n_scenes)
    frames = [base + (1 if i >= n_scenes - extra else 0) for i in range(n_scenes)]
    return frames, trans


def _motion_filter(motion: str, frames: int) -> str:
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    p = f"on/{frames - 1}"  # 0 -> 1 ilerleme
    ease = f"(0.5-0.5*cos(PI*{p}))"  # yumuşak başlayıp yumuşak biten hareket
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    span_x = "(iw-iw/zoom)"
    span_y = "(ih-ih/zoom)"
    pan_zoom = f"{1 + ZOOM}"
    z, x, y = {
        "zoom_in": (f"1+{ZOOM}*{ease}", center_x, center_y),
        "zoom_out": (f"{1 + ZOOM}-{ZOOM}*{ease}", center_x, center_y),
        "pan_left": (pan_zoom, f"{span_x}*(1-{ease})", center_y),
        "pan_right": (pan_zoom, f"{span_x}*{ease}", center_y),
        "pan_up": (pan_zoom, center_x, f"{span_y}*(1-{ease})"),
        "pan_down": (pan_zoom, center_x, f"{span_y}*{ease}"),
    }.get(motion, (f"1+{ZOOM}*{ease}", center_x, center_y))
    return (
        f"scale={w * UPSCALE}:{h * UPSCALE}:force_original_aspect_ratio=increase,"
        f"crop={w * UPSCALE}:{h * UPSCALE},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={config.FPS},"
        "setsar=1,format=yuv420p"
    )


def build_video(
    images: list[Path],
    motions: list[str],
    out_path: Path,
    music: Path | None = None,
) -> Path:
    if len(images) < 2:
        raise VideoError("Video için en az 2 görsel gerekli.")
    frames, trans = scene_frame_counts(len(images))
    fps = config.FPS

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for img in images:
        cmd += ["-i", str(img)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]

    parts = [f"[{i}:v]{_motion_filter(motions[i], frames[i])}[v{i}]" for i in range(len(images))]

    # xfade zinciri: her geçiş, o ana kadarki toplam uzunluğun sonundan 'trans' kare önce başlar.
    current, length = "[v0]", frames[0]
    for i in range(1, len(images)):
        label = f"[x{i}]" if i < len(images) - 1 else "[vout]"
        offset = (length - trans) / fps
        transition = TRANSITIONS[(i - 1) % len(TRANSITIONS)]
        parts.append(
            f"{current}[v{i}]xfade=transition={transition}:duration={trans / fps}:offset={offset:.4f}{label}"
        )
        current, length = label, length + frames[i] - trans

    seconds = config.VIDEO_SECONDS
    if music:
        parts.append(
            f"[{len(images)}:a]atrim=0:{seconds},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.5,afade=t=out:st={seconds - 1.5}:d=1.5[aout]"
        )

    cmd += ["-filter_complex", ";".join(parts), "-map", "[vout]"]
    if music:
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(fps), "-t", str(seconds),
        "-movflags", "+faststart", str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise VideoError(f"ffmpeg hatası: {result.stderr.strip()[-800:]}")
    return out_path
