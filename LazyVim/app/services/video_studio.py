import base64
import json
import re
import subprocess
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.config import SD_TURBO_URL, VIDEO_OUTPUT_DIR
from app.models.schemas import (
    Article,
    ImageCandidate,
    SceneVisualAssignment,
    VideoGenerationResult,
    VideoRequest,
    VideoScene,
    VideoScript,
)
from app.services.llm import call_llm_structured
from app.services.news_fetcher import search_news


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "their", "this", "to",
    "was", "will", "with", "what", "why", "how", "after", "over",
}
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"
VIDEO_SIZE = (1280, 720)


def generate_news_video(request: VideoRequest | dict) -> VideoGenerationResult:
    if isinstance(request, dict):
        request = VideoRequest.model_validate(request)
    working_dir = _create_working_dir(request.query or request.title or "video")
    try:
        articles = _get_source_articles(request)
        if not articles:
            return VideoGenerationResult(
                title=request.title or request.query or "AI News Video",
                topic=request.query or request.title,
                working_dir=str(working_dir),
                status="error",
                error="No source articles found for video generation.",
            )

        script = _build_video_script(articles, request)
        candidates = collect_article_media(articles, working_dir)
        assignments = assign_scene_visuals(script.scenes, candidates, articles)

        scene_videos: list[Path] = []
        subtitles = []
        scene_durations: list[float] = []
        audio_path = working_dir / "narration.wav"
        concat_audio_list = working_dir / "audio_concat.txt"
        with concat_audio_list.open("w", encoding="utf-8") as audio_list_file:
            for scene in script.scenes:
                assignment = next((item for item in assignments if item.scene_id == scene.scene_id), None)
                image_path = _render_scene_frame(scene, assignment, articles, working_dir)
                scene_voice = _synthesize_scene_audio(scene, working_dir)
                audio_duration = _probe_duration(scene_voice)
                if audio_duration <= 0:
                    audio_duration = max(scene.duration_seconds - 0.5, 3.0)
                scene.duration_seconds = round(max(scene.duration_seconds, audio_duration + 0.5), 2)
                scene_bgm = _generate_bgm_clip(scene.scene_id, scene.duration_seconds, working_dir)
                scene_audio = _mix_voice_and_bgm(scene.scene_id, scene_voice, scene_bgm, working_dir)
                scene_durations.append(scene.duration_seconds)
                audio_list_file.write(f"file '{scene_audio.as_posix()}'\n")
                subtitles.append((scene.narration, scene.duration_seconds))
                scene_video = _create_scene_video(scene.scene_id, image_path, scene_audio, scene.duration_seconds, working_dir)
                scene_videos.append(scene_video)

        _concat_audio(concat_audio_list, audio_path)
        subtitle_path = working_dir / "captions.srt"
        _write_srt(subtitles, subtitle_path)

        stitched = _concat_scene_videos(scene_videos, working_dir / "stitched.mp4")
        final_video = working_dir / "final.mp4"
        if request.include_captions:
            _burn_subtitles(stitched, subtitle_path, final_video)
        else:
            final_video = stitched

        manifest = {
            "title": script.title,
            "topic": request.query or request.title,
            "duration_seconds": round(sum(scene_durations), 2),
            "source_count": len(articles),
            "sources": [article.model_dump() for article in articles],
            "scenes": [scene.model_dump() for scene in script.scenes],
            "visual_assignments": [assignment.model_dump() for assignment in assignments],
            "video_path": str(final_video),
            "audio_path": str(audio_path),
            "subtitle_path": str(subtitle_path),
        }
        (working_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return VideoGenerationResult(
            title=script.title,
            topic=request.query or request.title or script.title,
            duration_seconds=round(sum(scene_durations), 2),
            video_path=str(final_video),
            audio_path=str(audio_path),
            subtitle_path=str(subtitle_path),
            working_dir=str(working_dir),
            scenes=script.scenes,
            visual_assignments=assignments,
            sources=articles,
            source_count=len(articles),
            status="ok",
        )
    except Exception as exc:
        return VideoGenerationResult(
            title=request.title or request.query or "AI News Video",
            topic=request.query or request.title,
            working_dir=str(working_dir),
            status="error",
            error=str(exc),
        )


def collect_article_media(articles: list[Article], working_dir: Path) -> list[ImageCandidate]:
    image_dir = working_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[ImageCandidate] = []
    seen_urls: set[str] = set()

    for idx, article in enumerate(articles, start=1):
        urls = []
        if article.image_url:
            urls.append((article.image_url, "thumbnail", ""))

        if article.url.startswith("http"):
            urls.extend(_extract_page_images(article.url))

        for image_url, origin_type, alt_text in urls:
            if not image_url or image_url in seen_urls:
                continue
            local_path, width, height = _download_image(image_url, image_dir, idx, len(candidates) + 1)
            if not local_path:
                continue
            seen_urls.add(image_url)
            candidates.append(
                ImageCandidate(
                    article_index=idx,
                    source_url=article.url,
                    image_url=image_url,
                    local_path=str(local_path),
                    origin_type=origin_type,
                    alt_text=alt_text[:240],
                    width=width,
                    height=height,
                )
            )
            if len([c for c in candidates if c.article_index == idx]) >= 3:
                break
    return candidates


def assign_scene_visuals(
    scenes: list[VideoScene],
    candidates: list[ImageCandidate],
    articles: list[Article],
) -> list[SceneVisualAssignment]:
    assignments: list[SceneVisualAssignment] = []
    used_paths: set[str] = set()

    for scene in scenes:
        if scene.preferred_visual_type in {"data_card", "timeline_card", "closing_card"}:
            assignments.append(
                SceneVisualAssignment(
                    scene_id=scene.scene_id,
                    visual_type=scene.preferred_visual_type,
                    reason=f"Scene type {scene.preferred_visual_type} renders better as a designed card.",
                )
            )
            continue

        scene_text = " ".join([scene.title, scene.narration, *scene.on_screen_text])
        best_candidate = None
        best_score = 0.0

        for candidate in candidates:
            article = articles[candidate.article_index - 1]
            score = _score_candidate(scene, scene_text, article, candidate, used_paths)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_candidate and best_score >= 0.42:
            used_paths.add(best_candidate.local_path)
            assignments.append(
                SceneVisualAssignment(
                    scene_id=scene.scene_id,
                    visual_type="source_image",
                    image_path=best_candidate.local_path,
                    article_index=best_candidate.article_index,
                    score=round(best_score, 3),
                    reason=f"Matched scene sources and keywords with {best_candidate.origin_type} image.",
                )
            )
        else:
            assignments.append(
                SceneVisualAssignment(
                    scene_id=scene.scene_id,
                    visual_type="text_card",
                    score=round(best_score, 3),
                    reason="No source image crossed the relevance threshold.",
                )
            )

    return assignments


def _get_source_articles(request: VideoRequest) -> list[Article]:
    if request.title and request.content:
        return [
            Article(
                title=request.title,
                description=request.content[:260],
                content=request.content,
                source="Custom Article",
                url="",
                published_at="",
                image_url="",
            )
        ]

    if request.query:
        return _enrich_articles(search_news(request.query, page_size=5, sort_by="relevancy"))

    return []


def _build_video_script(articles: list[Article], request: VideoRequest) -> VideoScript:
    compiled = []
    for idx, article in enumerate(articles, start=1):
        compiled.append(
            f"S{idx} | [{article.source}] {article.title}\n"
            f"Published: {article.published_at}\n"
            f"Summary: {_truncate_text(article.description or article.content, 420)}\n"
            f"Extended context: {_truncate_text(article.content or article.description, 820)}\n"
        )

    target_scenes = _target_scene_count(request.duration_seconds)
    fallback = _fallback_script(articles, request, target_scenes)
    prompt = f"""You are producing a sharp, TV-style business news bulletin for an Indian audience.

Topic: {request.query or request.title}
Tone: {request.tone}
Target duration: {request.duration_seconds} seconds
Language: {request.language}
Available source articles:
{chr(10).join(compiled)}

Return JSON with this shape:
{{
  "title": "short broadcast title",
  "intro_hook": "1 sentence",
  "scenes": [
    {{
      "scene_id": 1,
      "title": "scene title",
      "narration": "continuous conversational anchor script",
      "on_screen_text": ["short overlay", "short overlay"],
      "source_ids": [1, 2],
      "preferred_visual_type": "source_image|data_card|timeline_card|closing_card",
      "duration_seconds": 8
    }}
  ],
  "closing_note": "1 sentence",
  "source_summary": "short note about source coverage"
}}

Rules:
- Create between 3 and {target_scenes} scenes.
- Use fewer scenes when the story is tight and more scenes only when the coverage genuinely adds a new angle.
- Keep total duration close to {request.duration_seconds} seconds.
- Write narration like a live business news anchor. It should feel sharp, confident, and continuous.
- Lead with the most important fact, then move into consequence, reaction, and what to watch.
- Use energetic connectors such as "Now", "Meanwhile", "The bigger point here", "What stands out is", when natural.
- If a source contains enough detail, carry 3-4 complete sentences of actual substance through the relevant scenes instead of repeating just the headline.
- Do not split scenes into equal time chunks. Each scene should exist because the narrative focus changes.
- Use source_image only when a scene clearly maps to a cited article.
- Use data_card for market impact or numeric implications.
- Use timeline_card for chronology or sequence scenes.
- Use closing_card for the final what-to-watch scene.
- Every factual scene must cite source_ids from the list above.
- Keep on_screen_text short and presentation-ready.
- Avoid abrupt one-line fragments. Every scene narration should sound natural when read aloud.
- Prioritize what is being said over visual pacing.
"""

    try:
        script = call_llm_structured(prompt, VideoScript, fallback=fallback)
    except Exception:
        script = VideoScript.model_validate(fallback)
    if not script.scenes:
        script = VideoScript.model_validate(fallback)

    _normalize_script(script, request.duration_seconds, len(articles))
    return script


def _fallback_script(articles: list[Article], request: VideoRequest, target_scenes: int) -> dict:
    topic = request.query or request.title or "Business News Update"
    scenes = []
    lead = articles[0]
    lead_sentences = _split_sentences(lead.content or lead.description or lead.title)
    if not lead_sentences:
        lead_sentences = [lead.title]

    opening_block = " ".join(lead_sentences[:2])
    if opening_block:
        scenes.append({
            "scene_id": 1,
            "title": lead.title[:70],
            "narration": (
                f"Here is the top business update right now. {lead.title}. "
                f"{opening_block}"
            ),
            "on_screen_text": [topic, lead.source or "Lead source"],
            "source_ids": [1],
            "preferred_visual_type": "source_image",
            "duration_seconds": 9,
        })

    detail_block = " ".join(lead_sentences[2:5])
    if detail_block:
        scenes.append({
            "scene_id": len(scenes) + 1,
            "title": "What the report is saying",
            "narration": (
                "Now, here is the part of the story that really matters. "
                f"{detail_block}"
            ),
            "on_screen_text": ["Key detail", request.tone],
            "source_ids": [1],
            "preferred_visual_type": "source_image",
            "duration_seconds": 9,
        })

    for idx, article in enumerate(articles[1:4], start=2):
        if len(scenes) >= max(target_scenes - 2, 2):
            break
        article_sentences = _split_sentences(article.content or article.description or article.title)
        excerpt = " ".join(article_sentences[:2]) or article.title
        scenes.append({
            "scene_id": len(scenes) + 1,
            "title": article.title[:70],
            "narration": (
                f"Meanwhile, another important angle is coming through in the coverage. {article.title}. "
                f"{excerpt}"
            ),
            "on_screen_text": [article.source or "Source", article.title[:60]],
            "source_ids": [idx],
            "preferred_visual_type": "source_image",
            "duration_seconds": 9,
        })

    scenes.append({
        "scene_id": len(scenes) + 1,
        "title": "Why it matters",
        "narration": (
            "The bigger point here is what this changes for investors, operators, and decision makers. "
            "The market will now read this through the lens of risk, timing, execution, and the next signal that confirms the trend."
        ),
        "on_screen_text": ["Why it matters", request.tone],
        "source_ids": list(range(1, min(len(articles), 3) + 1)),
        "preferred_visual_type": "data_card",
        "duration_seconds": 10,
    })
    scenes.append({
        "scene_id": len(scenes) + 1,
        "title": "What to watch",
        "narration": (
            "What to watch next is the next official update, fresh commentary from the key players involved, "
            "and whether the market reaction actually follows the direction this coverage is pointing to."
        ),
        "on_screen_text": ["What to watch", "Next trigger"],
        "source_ids": list(range(1, min(len(articles), 3) + 1)),
        "preferred_visual_type": "closing_card",
        "duration_seconds": 8,
    })

    scenes = scenes[:target_scenes]
    return {
        "title": topic,
        "intro_hook": f"The business story moving fastest today: {topic}.",
        "scenes": scenes,
        "closing_note": "Sources synthesized for a short-form intelligence video.",
        "source_summary": f"Built from {len(articles)} source articles.",
    }


def _normalize_script(script: VideoScript, target_duration: int, max_source_id: int) -> None:
    if not script.scenes:
        return

    valid_visuals = {"source_image", "data_card", "timeline_card", "closing_card"}
    for idx, scene in enumerate(script.scenes, start=1):
        scene.scene_id = idx
        scene.duration_seconds = min(max(scene.duration_seconds or 8.0, 6.0), 16.0)
        scene.source_ids = [sid for sid in scene.source_ids if 1 <= sid <= max_source_id][:3] or [1]
        if scene.preferred_visual_type not in valid_visuals:
            scene.preferred_visual_type = "source_image"
        scene.on_screen_text = [item[:70] for item in scene.on_screen_text[:3]]
        scene.title = scene.title[:90]
        scene.narration = re.sub(r"\s+", " ", scene.narration).strip()

    word_weights = [max(len(scene.narration.split()) / 18.0, 1.0) for scene in script.scenes]
    total = sum(word_weights)
    if total <= 0:
        return
    scale = target_duration / total
    adjusted_total = 0.0
    for scene, weight in zip(script.scenes[:-1], word_weights[:-1]):
        scene.duration_seconds = round(min(max(weight * scale, 6.0), 18.0), 2)
        adjusted_total += scene.duration_seconds
    script.scenes[-1].duration_seconds = round(min(max(target_duration - adjusted_total, 6.0), 18.0), 2)


def _extract_page_images(article_url: str) -> list[tuple[str, str, str]]:
    try:
        response = requests.get(article_url, timeout=10, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    candidates: list[tuple[str, str, str]] = []
    for attr in ("property", "name"):
        for tag_name in ("og:image", "twitter:image"):
            tag = soup.find("meta", attrs={attr: tag_name})
            if tag and tag.get("content"):
                candidates.append((urljoin(article_url, tag["content"]), tag_name, ""))

    for img in soup.find_all("img", src=True):
        src = urljoin(article_url, img["src"])
        alt = (img.get("alt") or "").strip()
        candidates.append((src, "inline", alt))
        if len(candidates) >= 6:
            break
    return candidates


def _enrich_articles(articles: list[Article]) -> list[Article]:
    enriched: list[Article] = []
    for article in articles:
        if article.url.startswith("http"):
            detailed = _extract_article_text(article.url)
            if detailed:
                article.description = detailed["summary"] or article.description
                article.content = detailed["content"] or article.content or article.description
        enriched.append(article)
    return enriched


def _extract_article_text(article_url: str) -> dict[str, str]:
    try:
        response = requests.get(article_url, timeout=10, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except requests.RequestException:
        return {"summary": "", "content": ""}

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    meta_desc = ""
    for attr in ("property", "name"):
        tag = soup.find("meta", attrs={attr: "og:description"}) or soup.find("meta", attrs={attr: "description"})
        if tag and tag.get("content"):
            meta_desc = tag["content"].strip()
            break

    paragraphs: list[str] = []
    for node in soup.find_all(["article", "main", "section", "p", "div"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if len(text) < 70:
            continue
        if any(bad in text.lower() for bad in ["subscribe", "sign in", "advertisement", "all rights reserved"]):
            continue
        paragraphs.append(text)
        if len(paragraphs) >= 12:
            break

    combined = " ".join(_dedupe_lines(paragraphs))
    summary = meta_desc or _first_sentences(combined, 2)
    if _is_long_text(combined):
        content = _first_sentences(combined, 4)
    else:
        content = _first_sentences(combined or meta_desc, 2)
    return {"summary": summary[:420], "content": content[:1200]}


def _download_image(url: str, image_dir: Path, article_index: int, candidate_index: int) -> tuple[Path | None, int, int]:
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        width, height = img.size
        if width < 240 or height < 180:
            return None, 0, 0
        out_path = image_dir / f"article_{article_index}_{candidate_index}.jpg"
        img.save(out_path, quality=90)
        return out_path, width, height
    except Exception:
        return None, 0, 0


def _score_candidate(
    scene: VideoScene,
    scene_text: str,
    article: Article,
    candidate: ImageCandidate,
    used_paths: set[str],
) -> float:
    source_match = 1.0 if candidate.article_index in scene.source_ids else 0.0
    article_text = " ".join([article.title, article.description, candidate.alt_text])
    text_match = _token_overlap(scene_text, article_text)
    quality = min((candidate.width * candidate.height) / 1_200_000, 1.0)
    novelty = 0.2 if candidate.local_path in used_paths else 1.0
    origin_bonus = 1.0 if candidate.origin_type in {"og:image", "twitter:image"} else 0.85 if candidate.origin_type == "thumbnail" else 0.7
    return (0.45 * source_match) + (0.30 * text_match) + (0.15 * quality) + (0.10 * novelty * origin_bonus)


def _token_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in re.findall(r"[a-zA-Z0-9]+", left.lower()) if token not in STOPWORDS and len(token) > 2}
    right_tokens = {token for token in re.findall(r"[a-zA-Z0-9]+", right.lower()) if token not in STOPWORDS and len(token) > 2}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _generate_ai_image(prompt: str, working_dir: Path, scene_id: int) -> Path | None:
    try:
        # We use the scene title and narration to form a good prompt for SD-Turbo
        clean_prompt = f"Professional news broadcast visual for: {prompt}. Cinematic lighting, high quality, 4k."
        response = requests.post(
            SD_TURBO_URL,
            json={"prompt": clean_prompt, "steps": 2, "guidance_scale": 0.0},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        img_data = base64.b64decode(data["image_base64"])
        
        image_dir = working_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"ai_scene_{scene_id}.png"
        image_path.write_bytes(img_data)
        return image_path
    except Exception as e:
        print(f"AI Image generation failed: {e}")
        return None


def _render_scene_frame(
    scene: VideoScene,
    assignment: SceneVisualAssignment | None,
    articles: list[Article],
    working_dir: Path,
) -> Path:
    image = Image.new("RGB", VIDEO_SIZE, "#0d1321")
    draw = ImageDraw.Draw(image)

    # Priority:
    # 1. AI Generated Image (New)
    # 2. Source Image (Assignment)
    # 3. Text/Gradient Card (Fallback)
    
    ai_image_path = _generate_ai_image(f"{scene.title}. {scene.narration[:100]}", working_dir, scene.scene_id)
    
    if ai_image_path and ai_image_path.exists():
        image = _compose_source_background(ai_image_path)
        draw = ImageDraw.Draw(image)
    elif assignment and assignment.image_path and Path(assignment.image_path).exists():
        image = _compose_source_background(Path(assignment.image_path))
        draw = ImageDraw.Draw(image)
    else:
        image = _gradient_card(scene.scene_id)
        draw = ImageDraw.Draw(image)

    title_font = _load_font(46, bold=True)
    body_font = _load_font(28)
    meta_font = _load_font(22)

    article_label = ""
    if assignment and assignment.article_index:
        article = articles[assignment.article_index - 1]
        article_label = article.source or urlparse(article.url).netloc or f"Source {assignment.article_index}"

    draw.rounded_rectangle((60, 48, 360, 96), radius=18, fill=(23, 37, 84, 210))
    draw.text((82, 64), f"Scene {scene.scene_id}", font=meta_font, fill=(232, 241, 255))

    if article_label:
        draw.rounded_rectangle((980, 48, 1210, 96), radius=18, fill=(7, 16, 35, 215))
        draw.text((1000, 64), article_label[:18], font=meta_font, fill=(211, 224, 255))

    current_y = 138
    for line in _wrap_text(scene.title, title_font, 1020):
        draw.text((80, current_y), line, font=title_font, fill=(248, 250, 255))
        current_y += 56

    current_y += 12
    for bullet in scene.on_screen_text[:3]:
        bullet_text = f"- {bullet}"
        for line in _wrap_text(bullet_text, body_font, 980):
            draw.text((100, current_y), line, font=body_font, fill=(223, 229, 241))
            current_y += 36
        current_y += 8

    footer_text = "Sources: " + ", ".join(f"S{sid}" for sid in scene.source_ids)
    draw.text((80, 660), footer_text, font=meta_font, fill=(205, 214, 232))

    frame_path = working_dir / f"scene_{scene.scene_id:02d}.png"
    image.save(frame_path)
    return frame_path


def _compose_source_background(image_path: Path) -> Image.Image:
    img = Image.open(image_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = ImageEnhance.Color(img).enhance(1.05)

    scale = max(VIDEO_SIZE[0] / img.width, VIDEO_SIZE[1] / img.height)
    resized = img.resize((int(img.width * scale), int(img.height * scale)))
    left = max((resized.width - VIDEO_SIZE[0]) // 2, 0)
    top = max((resized.height - VIDEO_SIZE[1]) // 2, 0)
    cropped = resized.crop((left, top, left + VIDEO_SIZE[0], top + VIDEO_SIZE[1]))

    blurred = cropped.filter(ImageFilter.GaussianBlur(radius=2))
    overlay = Image.new("RGBA", VIDEO_SIZE, (6, 12, 26, 150))
    gradient = Image.new("L", VIDEO_SIZE)
    gradient_data = []
    for y in range(VIDEO_SIZE[1]):
        gradient_data.extend([min(255, int(255 * (y / VIDEO_SIZE[1]) ** 1.3))] * VIDEO_SIZE[0])
    gradient.putdata(gradient_data)
    shaded = Image.composite(Image.new("RGBA", VIDEO_SIZE, (3, 6, 14, 240)), overlay, gradient)
    return Image.alpha_composite(blurred.convert("RGBA"), shaded).convert("RGB")


def _gradient_card(seed: int) -> Image.Image:
    image = Image.new("RGB", VIDEO_SIZE, "#101820")
    draw = ImageDraw.Draw(image)
    colors = [
        ((14, 24, 47), (38, 77, 122)),
        ((34, 27, 54), (112, 54, 95)),
        ((13, 48, 72), (24, 123, 127)),
    ]
    start, end = colors[(seed - 1) % len(colors)]
    for y in range(VIDEO_SIZE[1]):
        blend = y / max(VIDEO_SIZE[1] - 1, 1)
        color = tuple(int(start[i] * (1 - blend) + end[i] * blend) for i in range(3))
        draw.line((0, y, VIDEO_SIZE[0], y), fill=color)
    draw.ellipse((860, -120, 1360, 380), fill=(255, 255, 255, 18))
    draw.ellipse((-180, 460, 320, 980), fill=(255, 255, 255, 10))
    return image


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy_img = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy_img)
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:5]


def _generate_bgm_clip(scene_id: int, duration_seconds: float, working_dir: Path) -> Path:
    bgm_path = working_dir / f"scene_{scene_id:02d}_bgm.wav"
    fade_start = max(duration_seconds - 1.0, 0.1)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"sine=frequency=110:sample_rate=44100:duration={duration_seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=44100:duration={duration_seconds}",
        "-f", "lavfi", "-i", f"anoisesrc=color=pink:sample_rate=44100:duration={duration_seconds}",
        "-filter_complex",
        (
            "[0:a]volume=0.018[a0];"
            "[1:a]volume=0.010[a1];"
            "[2:a]volume=0.003[a2];"
            "[a0][a1][a2]amix=inputs=3:normalize=0,"
            f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_start}:d=0.8"
        ),
        "-c:a", "pcm_s16le",
        str(bgm_path),
    ]
    subprocess.run(cmd, check=True)
    return bgm_path


def _mix_voice_and_bgm(scene_id: int, voice_path: Path, bgm_path: Path, working_dir: Path) -> Path:
    mixed_path = working_dir / f"scene_{scene_id:02d}_mixed.wav"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(voice_path),
        "-i", str(bgm_path),
        "-filter_complex",
        "[1:a]volume=0.34[bg];[0:a][bg]amix=inputs=2:weights='1 0.42':normalize=0",
        "-c:a", "pcm_s16le",
        str(mixed_path),
    ]
    subprocess.run(cmd, check=True)
    return mixed_path


def _synthesize_scene_audio(scene: VideoScene, working_dir: Path) -> Path:
    text_file = working_dir / f"scene_{scene.scene_id:02d}.txt"
    text_file.write_text(scene.narration, encoding="utf-8")
    raw_audio_path = working_dir / f"scene_{scene.scene_id:02d}_raw.wav"
    audio_path = working_dir / f"scene_{scene.scene_id:02d}.wav"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi",
        "-i", f"flite=textfile='{text_file.as_posix()}':voice=kal16",
        str(raw_audio_path),
    ]
    subprocess.run(cmd, check=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(raw_audio_path),
        "-filter:a", "atempo=1.18,volume=1.18,highpass=f=110,lowpass=f=7200",
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)
    return audio_path


def _create_scene_video(scene_id: int, image_path: Path, audio_path: Path, duration_seconds: float, working_dir: Path) -> Path:
    output = working_dir / f"scene_{scene_id:02d}.mp4"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", "scale=1280:720,format=yuv420p",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "stillimage",
        "-af", "apad",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(duration_seconds),
        str(output),
    ]
    subprocess.run(cmd, check=True)
    return output


def _concat_audio(list_file: Path, output: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output)],
        check=True,
    )


def _concat_scene_videos(scene_videos: list[Path], output: Path) -> Path:
    list_file = output.with_name("video_concat.txt")
    list_file.write_text("".join(f"file '{path.as_posix()}'\n" for path in scene_videos), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output)],
        check=True,
    )
    return output


def _write_srt(subtitles: list[tuple[str, float]], output: Path) -> None:
    cursor = 0.0
    lines = []
    for idx, (text, duration) in enumerate(subtitles, start=1):
        start = _format_srt_time(cursor)
        cursor += duration
        end = _format_srt_time(cursor)
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    output.write_text("\n".join(lines), encoding="utf-8")


def _burn_subtitles(video_path: Path, subtitle_path: Path, output: Path) -> None:
    escaped = subtitle_path.as_posix().replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video_path), "-vf", f"subtitles='{escaped}'", "-c:a", "copy", str(output)],
        check=True,
    )


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _create_working_dir(topic: str) -> Path:
    slug = _slugify(topic) or "video"
    base = Path(VIDEO_OUTPUT_DIR)
    base.mkdir(parents=True, exist_ok=True)
    candidate = base / slug
    candidate.mkdir(parents=True, exist_ok=True)
    run_id = max([int(path.name) for path in candidate.iterdir() if path.is_dir() and path.name.isdigit()] + [0]) + 1
    working_dir = candidate / f"{run_id:03d}"
    working_dir.mkdir(parents=True, exist_ok=True)
    return working_dir.resolve()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:60]


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line[:140].lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(line)
    return output


def _truncate_text(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    return clean[:limit]


def _first_sentences(text: str, count: int) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    sentences = [sentence.strip() for sentence in sentences if len(sentence.strip()) > 20]
    return " ".join(sentences[:count])


def _is_long_text(text: str) -> bool:
    return len((text or "").splitlines()) >= 15 or len((text or "").split()) >= 180


def _is_long_article(article: Article) -> bool:
    return _is_long_text(article.content or "")


def _article_excerpt(article: Article, sentence_count: int) -> str:
    source_text = article.content or article.description or article.title
    excerpt = _first_sentences(source_text, sentence_count)
    return excerpt or article.description or article.title


def _split_sentences(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return []
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", clean) if len(sentence.strip()) > 20]


def _target_scene_count(duration_seconds: int) -> int:
    if duration_seconds <= 60:
        return 4
    if duration_seconds <= 90:
        return 5
    return 6
