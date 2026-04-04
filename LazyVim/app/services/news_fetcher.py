import serpapi
from app.config import SERPAPI_API_KEY
from app.models.schemas import Article


COUNTRY_NAMES = {
    "in": "India",
    "us": "United States",
    "uk": "United Kingdom",
}


def _get_client() -> serpapi.Client | None:
    if not SERPAPI_API_KEY:
        return None
    return serpapi.Client(api_key=SERPAPI_API_KEY)


def _parse_articles(data: dict) -> list[Article]:
    articles = []
    for a in data.get("news_results", []):
        source = a.get("source", {})
        source_name = source.get("name", "") if isinstance(source, dict) else str(source or "")
        highlights = a.get("highlight", {})
        stories = highlights.get("stories", []) if isinstance(highlights, dict) else []
        highlight_snippets = []
        for story in stories[:2]:
            if isinstance(story, dict) and story.get("snippet"):
                highlight_snippets.append(story["snippet"])
        description = a.get("snippet", "") or " ".join(highlight_snippets)
        articles.append(Article(
            title=a.get("title", "") or "",
            description=description,
            content=description,
            source=source_name,
            url=a.get("link", "") or "",
            published_at=a.get("date", "") or "",
            image_url=a.get("thumbnail", "") or "",
        ))
    return articles


def fetch_top_headlines(category: str = "business", country: str = "in", page_size: int = 10) -> list[Article]:
    country_name = COUNTRY_NAMES.get(country.lower(), country)
    query = f"{country_name} {category} news"
    return search_news(query, page_size=page_size, sort_by="date")


def search_news(query: str, page_size: int = 10, sort_by: str = "relevancy") -> list[Article]:
    client = _get_client()
    if not client:
        return []

    search_query = query
    if sort_by in {"publishedAt", "date"}:
        search_query = f"latest {query}"

    params = {
        "engine": "google_news",
        "q": search_query,
        "hl": "en",
        "gl": "IN",
    }

    try:
        results = client.search(params)
    except Exception:
        return []

    articles = _parse_articles(results)
    return articles[:page_size]
