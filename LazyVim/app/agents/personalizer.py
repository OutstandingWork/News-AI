from app.models.schemas import PersonalizedFeedResult, UserProfile
from app.services.llm import call_llm_structured
from app.services.news_fetcher import fetch_top_headlines, search_news


def get_personalized_feed(profile: UserProfile) -> dict:
    """Fetch and personalize news based on user profile."""
    # Fetch general headlines
    headlines = fetch_top_headlines(category="business", page_size=15)

    # Fetch interest-specific news
    interest_articles = []
    for interest in profile.interests[:3]:
        results = search_news(interest, page_size=5)
        interest_articles.extend(results)

    all_articles = headlines + interest_articles

    if not all_articles:
        return {"personalized_feed": [], "summary": "No articles found.", "confidence": {"score": 0, "label": "low", "reason": "No articles found."}, "sources": []}

    # Build article summaries for LLM
    article_list = ""
    for i, a in enumerate(all_articles):
        article_list += f"S{i+1}. [{a.source}] {a.title}: {a.description}\n"

    prompt = f"""You are a news personalization AI for an Indian business news platform.

User Profile:
- Role: {profile.role}
- Interests: {', '.join(profile.interests) if profile.interests else 'general business'}
- Name: {profile.name}

Available articles:
{article_list}

Select the top 8 most relevant articles for this user. For each, provide:
- The article number (index)
- A personalized headline twist (why this matters to them specifically)
- Relevance score (1-10)
- source_ids: always include the matching source ID for the selected article, e.g. [3]

Also provide an overall confidence assessment for the feed quality.

Respond in JSON format:
{{
    "selections": [
        {{"index": 1, "personalized_hook": "...", "relevance": 9, "source_ids": [1]}},
        ...
    ],
    "daily_brief": "A 2-3 sentence personalized morning brief for this user",
    "confidence": {{
        "score": 78,
        "label": "high",
        "reason": "Good source diversity and clear match with user interests"
    }}
}}"""

    result = call_llm_structured(
        prompt,
        PersonalizedFeedResult,
        fallback={"selections": [], "daily_brief": "", "confidence": {"score": 35, "label": "low", "reason": "LLM output could not be validated."}},
    )

    # Map back to articles
    personalized = []
    for sel in result.selections:
        idx = sel.index - 1
        if 0 <= idx < len(all_articles):
            article = all_articles[idx]
            personalized.append({
                "article": article.model_dump(),
                "personalized_hook": sel.personalized_hook,
                "relevance": max(1, min(sel.relevance, 10)),
                "source_ids": [idx + 1],
            })

    return {
        "personalized_feed": personalized,
        "daily_brief": result.daily_brief,
        "confidence": result.confidence.model_dump(),
        "sources": [a.model_dump() for a in all_articles],
    }
