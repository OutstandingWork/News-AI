from app.services.llm import call_llm


def summarize_article(title: str, content: str, style: str = "brief") -> str:
    """Summarize an article in the requested style."""
    style_instructions = {
        "brief": "Summarize in 2-3 concise sentences.",
        "explainer": "Explain this like you're teaching a college student. Use simple language, define jargon, and explain why it matters.",
        "investor": "Summarize from an investor's perspective. Focus on market impact, stock implications, and actionable takeaways.",
        "founder": "Summarize from a startup founder's perspective. Focus on market opportunities, competitive landscape, and strategic implications.",
    }

    instruction = style_instructions.get(style, style_instructions["brief"])

    prompt = f"""Article: {title}

{content}

{instruction}"""

    return call_llm(prompt, system="You are a sharp Indian business news analyst.")
