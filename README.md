# AI-Native News Experience with Local SD-Turbo

A state-of-the-art, integrated news platform that combines real-time business news curation with high-speed, local AI image generation. This project uses a dual-service architecture to provide a visually rich, automated news experience optimized for consumer GPUs.

## 🚀 Key Features
- **Real-Time Curation**: Personalized business news feeds based on user roles and interests.
- **Blazing Fast Local Images**: Integrated with a local `sd-turbo` API to generate 512x512 images in just 1-2 steps (~1 second on an RTX 3050).
- **Automated Video Studio**: Generates narrated MP4 news bulletins with AI-generated visuals matched to the script.
- **VRAM Optimized**: Specifically tuned to run both the news engine and the image generator on 4GB VRAM hardware.

## 🏗️ Architecture
The workspace consists of two primary components:
1. **Root Project (Image Generator)**: A FastAPI + Gradio service providing the `sd-turbo` backend.
2. **LazyVim (News Platform)**: A Streamlit-based application that handles news fetching, LLM synthesis, and video production.

---

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.11+
- NVIDIA GPU (4GB+ VRAM recommended)
- `uv` package manager
- `ffmpeg` (for video rendering)

### 1. Root Service (Image API)
```bash
# Sync dependencies
uv sync
source .venv/bin/activate

# Run the API + UI
python app.py
```
*Accessible at: http://127.0.0.1:7860*

### 2. News Platform (LazyVim)
```bash
cd LazyVim
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure API Keys
cp .env.example .env
# Edit .env and add your keys (GROQ, SERPAPI, GEMINI)
# Ensure SD_TURBO_URL=http://127.0.0.1:7860/generate
```

---

## 🏃 Running the Application
1. **Start the Image Backend**: Run `python app.py` in the root.
2. **Start the News UI**: In a new terminal, run:
   ```bash
   cd LazyVim
   streamlit run frontend/app.py
   ```
3. **Experience**: Navigate to the Streamlit UI (port 8501/8502). When you generate a video, it will automatically call the local root API to create custom visuals.

## 📄 Project Structure
- `app.py`: FastAPI backend for SD-Turbo.
- `LazyVim/app/agents/`: AI logic for personalization and synthesis.
- `LazyVim/app/services/video_studio.py`: The video pipeline integrated with the local image API.
- `GEMINI.md`: Detailed technical context for AI agents.

## 🛡️ License
Built for the ET AI Hackathon 2026.
