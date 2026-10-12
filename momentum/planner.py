"""Konuyu Claude ile görsel olarak tutarlı sahnelere ayırır."""

import json

import anthropic

from . import config

MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"]

SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "video_title": {"type": "string"},
        "visual_style": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "image_prompt": {"type": "string"},
                    "motion": {"type": "string", "enum": MOTIONS},
                },
                "required": ["title", "description", "image_prompt", "motion"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["video_title", "visual_style", "scenes"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Sen kısa, dikey (9:16) motivasyon videoları için sahne yönetmenisin.
Kullanıcının verdiği konuyu, 20 saniyelik bir videoda arka arkaya gösterilecek {n} sahneye böl.

Kurallar:
- Sahneler bir hikâye yayı izlesin: başlangıç/zorluk -> çaba -> dönüm noktası -> başarı/ilham.
- Tüm sahneler görsel olarak tutarlı olsun: aynı ana karakter (görünüşünü her prompt'ta aynı kelimelerle tarif et), aynı renk paleti ve ışık.
- "visual_style": tüm sahnelerde ortak kullanılacak İngilizce stil tarifi. Kullanıcının seçtiği stil: {style}
- "image_prompt": İngilizce, tek paragraf, somut ve sinematik; kompozisyon dikey (portrait) kadraja uygun, ana obje merkezde ve kenarlardan uzak olsun (görsel kaydırılıp yakınlaştırılacak).
  Görselde yazı, harf, logo veya filigran olmasın. Gerçek ünlü kişi veya marka kullanma.
- "title": Türkçe, en fazla 6 kelimelik sahne başlığı. "description": Türkçe, 1-2 cümlelik sahne açıklaması.
- "motion": sahnenin duygusuna uygun kamera hareketi; ardışık sahnelerde aynı hareketi tekrarlama.
- "video_title": Türkçe, kısa ve çarpıcı video başlığı."""


class PlannerError(RuntimeError):
    pass


def plan_scenes(topic: str, style_key: str, n_scenes: int = config.SCENE_COUNT) -> dict:
    """Konuyu sahne listesine çevirir. Dönen her sahnenin image_prompt'u ortak stili içerir."""
    style = config.STYLE_PRESETS.get(style_key, config.STYLE_PRESETS["sinematik"])
    if config.MOCK:
        plan = _mock_plan(topic, style, n_scenes)
    else:
        plan = _claude_plan(topic, style, n_scenes)

    scenes = plan["scenes"][:n_scenes]
    if len(scenes) < 2:
        raise PlannerError("Claude yeterli sahne üretmedi, lütfen tekrar deneyin.")
    for scene in scenes:
        scene["full_prompt"] = f"{scene['image_prompt'].rstrip('. ')}. Style: {plan['visual_style']}"
    plan["scenes"] = scenes
    return plan


def _claude_plan(topic: str, style: str, n_scenes: int) -> dict:
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT.format(n=n_scenes, style=style),
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": SCENE_SCHEMA},
            },
            messages=[{"role": "user", "content": f"Konu: {topic}"}],
        )
    except anthropic.AuthenticationError as exc:
        raise PlannerError("ANTHROPIC_API_KEY geçersiz veya eksik (.env dosyasını kontrol edin).") from exc
    except anthropic.RateLimitError as exc:
        raise PlannerError("Claude API hız sınırına ulaşıldı, biraz sonra tekrar deneyin.") from exc
    except anthropic.APIStatusError as exc:
        raise PlannerError(f"Claude API hatası ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise PlannerError("Claude API'ye bağlanılamadı, internet bağlantınızı kontrol edin.") from exc

    if response.stop_reason == "refusal":
        raise PlannerError("Claude bu konuyu işlemeyi reddetti, konuyu farklı ifade etmeyi deneyin.")
    if response.stop_reason == "max_tokens":
        raise PlannerError("Claude yanıtı yarıda kesildi, tekrar deneyin.")
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)


def _mock_plan(topic: str, style: str, n_scenes: int) -> dict:
    beats = [
        ("Karanlık bir başlangıç", "Kahraman zorluklarla dolu bir yolun başında."),
        ("İlk adım", "Korkusuna rağmen harekete geçiyor."),
        ("Düşüp kalkmak", "Her düşüşte yeniden ayağa kalkıyor."),
        ("Dönüm noktası", "Emeğin karşılığı görünmeye başlıyor."),
        ("Zirve", "Hedefine ulaşıp ufka bakıyor."),
    ]
    scenes = []
    for i in range(n_scenes):
        title, description = beats[i % len(beats)]
        scenes.append({
            "title": title,
            "description": description,
            "image_prompt": f"{topic} - {title}",
            "motion": MOTIONS[i % len(MOTIONS)],
        })
    return {"video_title": topic, "visual_style": style, "scenes": scenes}
