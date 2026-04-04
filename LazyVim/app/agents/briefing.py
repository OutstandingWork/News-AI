from app.models.schemas import BriefingResponse
from app.services.llm import call_llm, call_llm_structured
from app.services.news_fetcher import search_news


def _clean_source_ids(source_ids: list[int], max_source_id: int) -> list[int]:
    valid_ids: list[int] = []
    for source_id in source_ids:
        if 1 <= source_id <= max_source_id and source_id not in valid_ids:
            valid_ids.append(source_id)
    return valid_ids[:3]


def generate_briefing(topic: str) -> dict:
    """Generate an interactive intelligence briefing by synthesizing multiple articles on a topic."""
    articles = search_news(topic, page_size=10, sort_by="relevancy")

    if not articles:
        return {"error": f"No articles found for topic: {topic}"}

    # Compile all article content
    compiled = ""
    sources = []
    for i, a in enumerate(articles):
        compiled += f"\n--- Source S{i+1} [{a.source}] ---\n"
        compiled += f"Title: {a.title}\n"
        compiled += f"Published: {a.published_at}\n"
        compiled += f"Content: {a.description} {a.content}\n"
        sources.append(a.model_dump())

    prompt = f"""You are an elite business intelligence analyst for an Indian news platform.

Synthesize these {len(articles)} articles about "{topic}" into ONE comprehensive intelligence briefing.

Articles:
{compiled}

Create a briefing with:
1. **Executive Summary** (6-8 sentences covering the full picture)
2. **Key Developments** (5-7 bullet points — facts, not opinions)
3. **Stakeholder Impact** (who wins, who loses, and why)
4. **Market Implications** (for Indian investors/businesses specifically)
5. **What to Watch Next** (3-5 upcoming triggers/events)
6. **Follow-up Questions** (5 questions a reader might want to explore deeper)
7. **Confidence** based on source freshness, agreement, and diversity

Respond in JSON:
{{
    "executive_summary": "...",
    "executive_summary_sources": [1, 2],
    "key_developments": [{{"text": "...", "source_ids": [1, 3]}}],
    "stakeholder_impact": "...",
    "stakeholder_impact_sources": [1, 2],
    "market_implications": "...",
    "market_implications_sources": [2, 4],
    "what_to_watch": [{{"text": "...", "source_ids": [2, 5]}}],
    "follow_up_questions": ["...", "..."],
    "confidence": {{
        "score": 82,
        "label": "high",
        "reason": "Recent reporting across multiple publishers supports the same core narrative"
    }}
}}"""

    result = call_llm_structured(
        prompt,
        BriefingResponse,
        fallback={
            "executive_summary": "",
            "executive_summary_sources": [],
            "key_developments": [],
            "stakeholder_impact": "",
            "stakeholder_impact_sources": [],
            "market_implications": "",
            "market_implications_sources": [],
            "what_to_watch": [],
            "follow_up_questions": [],
            "confidence": {"score": 35, "label": "low", "reason": "LLM output could not be validated."},
        },
    )

    result.executive_summary_sources = _clean_source_ids(result.executive_summary_sources, len(articles))
    result.stakeholder_impact_sources = _clean_source_ids(result.stakeholder_impact_sources, len(articles))
    result.market_implications_sources = _clean_source_ids(result.market_implications_sources, len(articles))
    for item in result.key_developments:
        item.source_ids = _clean_source_ids(item.source_ids, len(articles))
    for item in result.what_to_watch:
        item.source_ids = _clean_source_ids(item.source_ids, len(articles))
    result.confidence.score = max(0, min(result.confidence.score, 100))

    return {
        "topic": topic,
        "briefing": result.model_dump(),
        "source_count": len(articles),
        "sources": sources,
    }


def answer_followup(topic: str, briefing_context: str, question: str) -> str:
    """Answer a follow-up question based on the briefing context."""
    prompt = f"""You are an expert business analyst. A user read an intelligence briefing about "{topic}" and has a follow-up question.

Briefing context:
{briefing_context}

User's question: {question}

Provide a clear, detailed answer. If the answer requires information beyond what's in the briefing, say so and provide your best analysis. Always relate back to Indian market context where relevant."""

    return call_llm(prompt, system="You are an expert Indian business and market analyst.")
