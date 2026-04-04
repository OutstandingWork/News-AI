import json
from typing import TypeVar

import google.generativeai as genai
from groq import Groq
from pydantic import BaseModel, ValidationError

from app.config import GROQ_API_KEY, GEMINI_API_KEY, GROQ_MODEL, GEMINI_MODEL


T = TypeVar("T", bound=BaseModel)


def get_groq_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


def init_gemini():
    genai.configure(api_key=GEMINI_API_KEY)


def call_groq(prompt: str, system: str = "You are a helpful AI assistant.", temperature: float = 0.7) -> str:
    client = get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def call_gemini(prompt: str, temperature: float = 0.7) -> str:
    init_gemini()
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=4096,
        ),
    )
    return response.text


def call_llm(prompt: str, system: str = "You are a helpful AI assistant.", provider: str = "groq", temperature: float = 0.7) -> str:
    """Unified LLM caller — tries groq first, falls back to gemini."""
    if provider == "gemini" and GEMINI_API_KEY:
        return call_gemini(prompt, temperature)
    if GROQ_API_KEY:
        return call_groq(prompt, system, temperature)
    if GEMINI_API_KEY:
        return call_gemini(prompt, temperature)
    return "[Error] No LLM API key configured. Please set GROQ_API_KEY or GEMINI_API_KEY in .env"


def extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]
    return json.loads(cleaned.strip())


def call_llm_json(prompt: str, system: str = "You are a helpful AI assistant. Always respond with valid JSON.", provider: str = "groq") -> dict:
    """Call LLM and parse JSON response."""
    raw = call_llm(prompt, system, provider, temperature=0.3)
    try:
        return extract_json(raw)
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to parse LLM response", "raw": raw}


def call_llm_structured(
    prompt: str,
    response_model: type[T],
    fallback: dict,
    system: str = "You are a helpful AI assistant. Always respond with valid JSON.",
    provider: str = "groq",
) -> T:
    raw = call_llm(prompt, system, provider, temperature=0.3)
    try:
        return response_model.model_validate(extract_json(raw))
    except (json.JSONDecodeError, IndexError, ValidationError):
        return response_model.model_validate(fallback)
