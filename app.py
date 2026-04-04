import base64
from io import BytesIO

import gradio as gr
import torch
import uvicorn
from diffusers import AutoPipelineForText2Image
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI(title="SD-Turbo API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# We use stabilityai/sd-turbo because it can generate high-quality images in 1-4 steps
model_id = "stabilityai/sd-turbo"

print(
    "Loading the SD-Turbo model... (This might take a minute on the first run as it downloads weights)"
)
pipe = AutoPipelineForText2Image.from_pretrained(
    model_id, torch_dtype=torch.float16, variant="fp16"
)

# VRAM Optimizations for 4GB RTX 3050
print("Applying memory optimizations for 4GB VRAM...")
pipe.enable_model_cpu_offload()  # Dynamically moves weights to RAM when not in use


class GenerationRequest(BaseModel):
    prompt: str
    steps: int = 1
    guidance_scale: float = 0.0


def generate_image_internal(prompt, num_inference_steps, guidance_scale):
    print(
        f"Generating image for prompt: '{prompt}' with {num_inference_steps} steps..."
    )
    result = pipe(
        prompt=prompt,
        num_inference_steps=int(num_inference_steps),
        guidance_scale=guidance_scale,
    )
    return result.images[0]


@app.post("/generate")
async def api_generate_image(request: GenerationRequest):
    try:
        image = generate_image_internal(
            request.prompt, request.steps, request.guidance_scale
        )
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return {"image_base64": img_str}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}


# Gradio Web UI
with gr.Blocks(title="Local SD-Turbo Generator", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🚀 Fast Local Image Generator (Optimized for 4GB VRAM)")
    gr.Markdown(
        "Powered by `stabilityai/sd-turbo` for lightning-fast generations on laptop GPUs."
    )

    with gr.Row():
        with gr.Column(scale=1):
            prompt = gr.Textbox(
                label="Prompt",
                placeholder="A cinematic shot of a cute cat wearing sunglasses...",
                lines=3,
            )

            with gr.Accordion("Advanced Settings", open=True):
                steps = gr.Slider(
                    minimum=1,
                    maximum=4,
                    value=2,
                    step=1,
                    label="Inference Steps (1-4 for Turbo)",
                )
                guidance = gr.Slider(
                    minimum=0.0,
                    maximum=2.0,
                    value=0.0,
                    step=0.1,
                    label="Guidance Scale (Keep at 0.0 for Turbo)",
                )

            btn = gr.Button("🎨 Generate Image", variant="primary")

        with gr.Column(scale=1):
            output_image = gr.Image(label="Generated Image", type="pil")

    btn.click(fn=generate_image_internal, inputs=[prompt, steps, guidance], outputs=output_image)

# Mount Gradio into FastAPI
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    print("Launching SD-Turbo API and Gradio interface...")
    uvicorn.run(app, host="127.0.0.1", port=7860)
