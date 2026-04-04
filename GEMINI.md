# Gemini Project Context: sd-turbo-local

This workspace contains two distinct Python projects. The primary root project is a local image generator, and a secondary project (a news platform) is located in the `LazyVim/` subdirectory.

## Project 1: Local SD-Turbo Generator (Root)

### Overview
A high-performance, local image generation application powered by [stabilityai/sd-turbo](https://huggingface.co/stabilityai/sd-turbo). It is optimized for consumer GPUs with limited VRAM (e.g., 4GB NVIDIA RTX 3050).

- **Main Technologies:** Python, `diffusers`, `torch` (CUDA 12.1), `gradio`, `accelerate`.
- **Key Feature:** Generates 512x512 images in 1-4 inference steps.
- **Optimizations:** Uses `fp16` precision and `enable_model_cpu_offload()` to manage memory effectively on 4GB VRAM.

### Building and Running
This project uses `uv` for dependency management.

1. **Sync Environment:**
   ```bash
   uv sync
   ```
2. **Activate Environment:**
   ```bash
   source .venv/bin/activate
   ```
3. **Run Application:**
   ```bash
   python app.py
   ```
   This launches a **FastAPI server** and a **Gradio UI** on `http://127.0.0.1:7860`.
   - **API Endpoint:** `POST /generate` (expects `{"prompt": "...", "steps": 2}`)
   - **UI:** Interactive image generation playground.

### Key Files
- `app.py`: Main entry point with FastAPI + Gradio integration.
- `pyproject.toml`: Project metadata with `fastapi` and `uvicorn` added.

---

## Project 2: ET AI-Native News Experience (`LazyVim/`)

### Overview
An AI-powered news platform built for the ET AI Hackathon 2026.

**New Feature: AI-Generated Video Visuals**
The video generation pipeline now integrates with the root SD-Turbo project to generate high-quality, relevant visuals for news scenes, replacing generic text cards or low-quality web images.

### Building and Running
1. **Navigate and Setup:**
   ```bash
   cd LazyVim
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure Environment:**
   Update `.env` with `SD_TURBO_URL=http://127.0.0.1:7860/generate`.
3. **Run Streamlit UI:**
   ```bash
   streamlit run frontend/app.py
   ```

### Integration Details
- `LazyVim/app/services/video_studio.py`: Modified to call the SD-Turbo API during the `_render_scene_frame` process.
- **Priority Logic:** The system prefers AI-generated images, then falls back to source-matched images, and finally to designed gradient cards.

---

## Global Development Conventions

- **Python Version:** Primarily 3.11+ (Root) and 3.12 (LazyVim).
- **Tooling:** Prefer `uv` for the root project.
- **Environment Variables:** Secrets and API keys should be managed via `.env` files (never committed).
- **Video Processing:** `ffmpeg` is a required system dependency for the news video feature.
