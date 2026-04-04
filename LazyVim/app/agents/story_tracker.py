from app.models.schemas import StoryArcResponse
from app.services.llm import call_llm_structured
from app.services.news_fetcher import search_news


def _clean_source_ids(source_ids: list[int], max_source_id: int) -> list[int]:
    valid_ids: list[int] = []
    for source_id in source_ids:
        if 1 <= source_id <= max_source_id and source_id not in valid_ids:
            valid_ids.append(source_id)
    return valid_ids[:3]


def track_story(topic: str) -> dict:
    """Build a story arc — timeline, key players, sentiment, predictions."""
    articles = search_news(topic, page_size=15, sort_by="publishedAt")

    if not articles:
        return {"error": f"No articles found for: {topic}"}

    compiled = ""
    for i, a in enumerate(articles):
        compiled += f"\n[S{i+1}] Date: {a.published_at} | Source: {a.source}\n"
        compiled += f"Title: {a.title}\n"
        compiled += f"Content: {a.description} {a.content}\n"

    prompt = f"""You are a narrative intelligence analyst. Analyze these {len(articles)} articles about "{topic}" and build a complete story arc.

Articles (chronological):
{compiled}

Build a story arc with:
1. **Timeline**: Key events in chronological order with dates
2. **Key Players**: People, companies, institutions involved and their roles
3. **Sentiment Shifts**: How the narrative tone has changed over time
4. **Contrarian Views**: Any dissenting or minority perspectives
5. **Predictions**: What's likely to happen next based on the trajectory
6. **Confidence**: How well the source set supports this story arc

Respond in JSON:
{{
    "title": "Story arc title",
    "timeline": [
        {{"date": "...", "event": "...", "significance": "high/medium/low", "source_ids": [1, 2]}}
    ],
    "key_players": [
        {{"name": "...", "role": "...", "stance": "...", "source_ids": [2, 3]}}
    ],
    "sentiment_shifts": [
        {{"period": "...", "sentiment": "positive/negative/neutral", "reason": "...", "source_ids": [1, 4]}}
    ],
    "contrarian_views": [{{"text": "...", "source_ids": [5]}}],
    "predictions": [
        {{"prediction": "...", "confidence": "high/medium/low", "timeframe": "...", "source_ids": [3, 6]}}
    ],
    "narrative_summary": "2-3 sentence summary of the complete story arc",
    "narrative_summary_sources": [1, 2],
    "confidence": {{
        "score": 74,
        "label": "medium",
        "reason": "Core events are consistent, but later predictions rely on fewer sources"
    }}
}}"""

    result = call_llm_structured(
        prompt,
        StoryArcResponse,
        fallback={
            "title": topic,
            "timeline": [],
            "key_players": [],
            "sentiment_shifts": [],
            "contrarian_views": [],
            "predictions": [],
            "narrative_summary": "",
            "narrative_summary_sources": [],
            "confidence": {"score": 35, "label": "low", "reason": "LLM output could not be validated."},
        },
    )

    result.narrative_summary_sources = _clean_source_ids(result.narrative_summary_sources, len(articles))
    for item in result.timeline:
        item.source_ids = _clean_source_ids(item.source_ids, len(articles))
    for item in result.key_players:
        item.source_ids = _clean_source_ids(item.source_ids, len(articles))
    for item in result.sentiment_shifts:
        item.source_ids = _clean_source_ids(item.source_ids, len(articles))
    for item in result.contrarian_views:
        item.source_ids = _clean_source_ids(item.source_ids, len(articles))
    for item in result.predictions:
        item.source_ids = _clean_source_ids(item.source_ids, len(articles))
    result.confidence.score = max(0, min(result.confidence.score, 100))

    return {
        "topic": topic,
        "story_arc": result.model_dump(),
        "article_count": len(articles),
        "sources": [a.model_dump() for a in articles],
    }
