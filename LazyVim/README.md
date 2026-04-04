# ET AI-Native News Experience

> ET AI Hackathon 2026 - Problem Statement 8

An AI-powered business news experience built around personalization, synthesis, explainability, multilingual adaptation, and short-form video generation. The app is primarily delivered through Streamlit, with an optional FastAPI layer for API access.

## What the project does

This codebase turns business/news inputs into six AI-assisted experiences:

1. **My Newsroom**
   Personalized feed based on user role and interests, with why-this-matters hooks.

2. **Intelligence Briefing**
   Multi-source synthesis for a topic, with key developments, market implications, and follow-up Q&A.

3. **Story Arc Tracker**
   Timeline-style narrative view of an ongoing story, including key players, sentiment shifts, contrarian views, and predictions.

4. **AI News Video Studio**
   Generates a narrated MP4 from a topic or pasted article using:
   - source-grounded script generation
   - article thumbnail / page image extraction
   - scene-to-image matching
   - local frame rendering
   - local narration via `ffmpeg` + `flite`
   - captions
   - downloadable video output

5. **Vernacular Business News**
   Context-aware translation into multiple Indian languages.

6. **Smart Summarizer**
   Rewrites the same article in different styles such as brief, explainer, investor, and founder.

## Current runtime model

You do **not** need to run FastAPI separately to use the Streamlit app.

The Streamlit app imports and calls the Python services directly. FastAPI exists as an optional wrapper around the same logic for API use cases.

- Run **Streamlit** if you want to use the product UI.
- Run **FastAPI** only if you want HTTP endpoints.

## Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| API | FastAPI |
| LLM primary | Groq |
| LLM fallback | Google Gemini |
| News source | SerpApi Google News |
| Video rendering | FFmpeg |
| Image extraction / parsing | Requests + BeautifulSoup |
| Frame rendering | Pillow |
| Language | Python 3.12 tested locally |

## Project structure

```text
app/
  agents/              # Personalizer, briefing, story tracker, translator, summarizer
  models/              # Pydantic schemas
  services/            # LLM, news fetcher, video studio
  main.py              # FastAPI app

frontend/
  app.py               # Streamlit app

generated_videos/      # Runtime output for MP4 renders (gitignored)
requirements.txt
README.md
```

## Setup

### 1. Clone and enter the repo

```bash
git clone https://github.com/OutstandingWork/LazyVim.git
cd LazyVim
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install system dependency for video generation

`ffmpeg` must be available on your `PATH`.

Check:

```bash
ffmpeg -version
```

### 5. Configure environment variables

Copy the example file:

```bash
cp .env.example .env
```

Set the keys you have:

```env
GROQ_API_KEY=...
SERPAPI_API_KEY=...
GEMINI_API_KEY=...
VIDEO_OUTPUT_DIR=generated_videos
```

Notes:
- `GROQ_API_KEY` is used as the primary LLM.
- `GEMINI_API_KEY` is used as fallback.
- `SERPAPI_API_KEY` is required for live news search / headlines.
- `VIDEO_OUTPUT_DIR` is optional. Default is `generated_videos`.

## Running the app

### Streamlit UI

```bash
source .venv/bin/activate
streamlit run frontend/app.py
```

Default local URL:

```text
http://127.0.0.1:8501
```

### FastAPI backend

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Default local URL:

```text
http://127.0.0.1:8000
```

## Streamlit pages

### My Newsroom
- pulls business headlines
- enriches the feed using role + user interests
- generates personalized hooks

### Intelligence Briefing
- searches a topic
- synthesizes multiple source snippets
- shows executive summary, developments, impacts, and follow-up Q&A

### Story Arc Tracker
- tracks how a story evolves over time
- builds a timeline, key-player map, sentiment shifts, and predictions

### Vernacular News
- translates article text into supported Indian languages
- includes cultural context and key term guidance

### Smart Summarizer
- lets the same article be reframed for different audiences

### AI Video Studio
- supports two source modes:
  - **Search Topic**
  - **Paste Article**
- lets the user choose:
  - `60s`, `90s`, or `120s`
  - tone preset
  - captions on/off
- outputs:
  - previewable MP4
  - downloadable file
  - source list
  - storyboard and visual match details

## AI Video Studio pipeline

The video feature in `app/services/video_studio.py` currently works like this:

1. Collect source articles
   - from SerpApi topic search, or
   - from pasted article text

2. Enrich source text
   - crawls article pages when URLs are available
   - pulls meta description and article-like paragraph text

3. Build a script
   - prefers content-led narration over equal scene slicing
   - uses fewer, denser scenes for shorter videos
   - tries to sound more like a business news bulletin

4. Collect visuals
   - uses SerpApi thumbnail first
   - then tries page-level images such as `og:image` / `twitter:image`
   - then inline images

5. Match visuals to scenes
   - scene-to-source grounding
   - keyword overlap
   - image quality
   - duplicate avoidance

6. Render frames
   - uses source images where they fit
   - otherwise falls back to branded data/text cards

7. Generate narration
   - local `ffmpeg` `flite` voice
   - post-processed for a sharper delivery

8. Add background bed
   - synthetic low-volume BGM mixed locally

9. Build final video
   - scene MP4 segments
   - concatenation
   - captions
   - final downloadable MP4

### Runtime output location

Generated video artifacts are written under:

```text
generated_videos/<slug>/<run-id>/
```

Typical contents:

```text
scene_01.png
scene_01.wav
scene_01_mixed.wav
captions.srt
stitched.mp4
final.mp4
manifest.json
```

## API endpoints

Current FastAPI endpoints in `app/main.py`:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | health/info |
| `GET` | `/api/headlines` | fetch top headlines |
| `GET` | `/api/search` | search related news |
| `POST` | `/api/personalized-feed` | generate personalized feed |
| `GET` | `/api/briefing` | generate intelligence briefing |
| `POST` | `/api/briefing/followup` | answer briefing follow-up |
| `GET` | `/api/story-arc` | generate story arc |
| `POST` | `/api/translate` | translate article |
| `POST` | `/api/summarize` | summarize article |
| `POST` | `/api/video/generate` | generate video result metadata |

## Important implementation notes

### Streamlit and backend

The Streamlit UI does not require the FastAPI server to be running. It imports the app logic directly.

### External dependency behavior

- If `SerpApi` is unavailable or network resolution fails, headline/search calls return empty results instead of crashing the app.
- If article crawling fails, the video flow falls back to whatever summary text was already available.
- If live LLM calls fail, the video system falls back to a local structured fallback script.

### Video tone and pacing

The current video generator is tuned toward:
- sharper bulletin-style narration
- content-first scene segmentation
- stronger but still low-volume background bed

It is still heuristic. For dense source text, the actual runtime may exceed the requested target a bit because the system prioritizes carrying meaningful narration over aggressively chopping content.

## Troubleshooting

### Streamlit says a port is already in use

Either stop the previous process or choose another port:

```bash
streamlit run frontend/app.py --server.port 8502
```

### Streamlit loads but headline/news sections are empty

Usually one of:
- `SERPAPI_API_KEY` missing
- no internet/DNS access
- SerpApi request failed

The app should stay up even if the news fetch fails.

### Video generation fails immediately

Check:
- `ffmpeg` is installed
- output folder is writable
- article input is non-empty

### Video generation works but sounds too long

The narration is intentionally more content-heavy now. If you want stricter target durations, the next tuning step is to trim narration density more aggressively or compress speech further.

## Development notes

Useful checks:

```bash
python3 -m compileall app frontend/app.py
```

Example local video generation smoke test:

```bash
.venv/bin/python - <<'PY'
from app.services.video_studio import generate_news_video
result = generate_news_video({
    "title": "RBI keeps rates steady as inflation cools",
    "content": "The Reserve Bank of India kept benchmark rates unchanged while signaling a data-dependent stance...",
    "duration_seconds": 60,
    "tone": "Investor Update",
    "include_captions": True,
})
print(result.status)
print(result.video_path)
PY
```

## What is currently strong vs incomplete

### Stronger today
- direct Streamlit experience
- source-backed topic synthesis
- functional local video generation pipeline
- captions and downloadable output
- multilingual and summarization flows

### Still heuristic / demo-grade
- article text extraction quality varies by publisher markup
- local TTS is serviceable but not premium
- video pacing is improving but not fully broadcast-polished
- source availability depends on external news/article access

## License / usage

This repository was built as a hackathon/demo project for ET AI Hackathon 2026 Problem Statement 8.
