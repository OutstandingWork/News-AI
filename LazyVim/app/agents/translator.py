from app.models.schemas import TranslationResponse
from app.services.llm import call_llm_structured


LANGUAGE_MAP = {
    "hindi": "Hindi (हिन्दी)",
    "tamil": "Tamil (தமிழ்)",
    "telugu": "Telugu (తెలుగు)",
    "bengali": "Bengali (বাংলা)",
    "marathi": "Marathi (मराठी)",
    "gujarati": "Gujarati (ગુજરાતી)",
    "kannada": "Kannada (ಕನ್ನಡ)",
    "malayalam": "Malayalam (മലയാളം)",
}


def translate_article(title: str, content: str, target_language: str) -> dict:
    """Context-aware translation — not literal, culturally adapted."""
    lang_display = LANGUAGE_MAP.get(target_language, target_language)

    prompt = f"""You are an expert Indian business journalist who writes in {lang_display}.

Translate the following English business news article into {lang_display}. This is NOT a literal translation — you must:

1. Adapt financial terms to how they're commonly understood in {lang_display}-speaking regions
2. Add brief cultural context where needed (e.g., explain foreign concepts with local analogies)
3. Keep the business accuracy intact
4. Use the script of {lang_display} for the translation
5. Maintain a professional news tone

Original Title: {title}

Original Content:
{content}

Respond in JSON:
{{
    "translated_title": "...",
    "translated_content": "...",
    "cultural_notes": "Brief note on any cultural adaptations made",
    "key_terms": [
        {{"english": "...", "translated": "...", "explanation": "..."}}
    ]
}}"""

    result = call_llm_structured(
        prompt,
        TranslationResponse,
        fallback={"translated_title": "", "translated_content": "", "cultural_notes": "", "key_terms": []},
    )
    return {
        "language": target_language,
        "language_display": lang_display,
        "translation": result.model_dump(),
    }
