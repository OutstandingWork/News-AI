# LazyVim: ET AI News Platform

This directory contains the **ET AI-Native News Experience** platform, a feature-rich application built to deliver personalized, synthesized, and highly visual news.

## 🌟 Enhanced Capabilities
As part of the integrated workspace, this application now features:
- **AI-Generated Visuals**: Integrated with the workspace's local `sd-turbo` backend to generate custom visuals for every news scene.
- **Narrated Bulletins**: Full pipeline from news fetching to final MP4 generation.
- **Multi-Agent Intelligence**: Specialized agents for translation, summarization, and story tracking.

## 🛠️ Local Environment Setup
Ensure you are in the `LazyVim/` directory before running these commands:

1. **Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Environment Variables**:
   ```bash
   cp .env.example .env
   # Add your API keys (GROQ, SERPAPI, GEMINI)
   # Ensure SD_TURBO_URL points to the local backend (usually http://127.0.0.1:7860/generate)
   ```
3. **Launch the UI**:
   ```bash
   streamlit run frontend/app.py
   ```

## 🎥 Video Studio Integration
The `app/services/video_studio.py` script has been specifically updated to prioritize AI-generated visuals over generic cards or thumbnails. Every scene script is sent to the local image generator API to create high-context, professional imagery.

## 📁 Subdirectory Structure
- `app/agents/`: Personalized feed, briefing, and story tracking logic.
- `app/services/`: Integration with LLMs, news APIs, and the video rendering pipeline.
- `frontend/`: Streamlit dashboard and user experience.
- `generated_videos/`: (Local only) Output directory for rendered MP4s.

For full system documentation, please refer to the root `README.md`.
