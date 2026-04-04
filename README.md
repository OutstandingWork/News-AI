# Local SD-Turbo Generator

A blazing-fast, local image generator powered by [stabilityai/sd-turbo](https://huggingface.co/stabilityai/sd-turbo), specifically optimized to run locally on a 4GB VRAM GPU (like the NVIDIA RTX 3050 Laptop).

## Features
- **Speed**: Generates 512x512 images in just 1 to 4 steps.
- **VRAM Optimizations**: Automatically applies `fp16` precision and dynamic CPU offloading to prevent Out-Of-Memory (OOM) errors.
- **Local Web UI**: Features a sleek UI built with Gradio for typing prompts and visualizing outputs.

## Requirements
- Python 3.11+
- An NVIDIA GPU (4GB VRAM minimum)
- `uv` package manager installed

## Installation & Setup

1. **Clone/Navigate** to the project directory:
   ```bash
   cd sd-turbo-local
   ```

2. **Sync the Environment**: Use `uv` to automatically create a virtual environment and pull down the correct CUDA version of PyTorch and all dependencies.
   ```bash
   uv sync
   ```

## Running the Application

1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Start the generator:
   ```bash
   python app.py
   ```

*(Note: On the very first run, it will automatically download the SD-Turbo model weights from Hugging Face. This is a one-time download of ~2GB.)*

3. Open your web browser and go to `http://127.0.0.1:7860`.