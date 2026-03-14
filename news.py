"""
news.py — HZL AI News Integration
NewsAPI.org headlines + search with full debug logging.

Setup:
    Set env var: NEWS_API_KEY
    Get it from: newsapi.org (free tier — 100 req/day)
"""

import os
import requests
from hzl_logger import get_logger

log = get_logger("news")

API_KEY  = os.getenv("NEWS_API_KEY")
BASE_URL = "https://newsapi.org/v2"
TIMEOUT  = 10

# Prioritize open/free sources, exclude heavy paywalls
PREFERRED_SOURCES = {
    # Open/Free & Generally Reliable
    "AP News", "Reuters", "NPR", "PBS", "BBC News", "The Guardian",
    "Al Jazeera English", "ABC News", "CBS News", "NBC News", "CNN",
    "Associated Press", "The Hill", "Politico", "Axios", "The Verge",
    "Ars Technica", "TechCrunch", "Wired", "Engadget",
}

PAYWALLED_SOURCES = {
    "The Wall Street Journal", "Financial Times", "The New York Times",
    "Washington Post", "Bloomberg", "The Athletic", "The Information",
}

def filter_and_rank_articles(articles):
    """Filter out paywalled sources, prioritize open ones."""
    open_articles = []
    other_articles = []
    for a in articles:
        source = a.get("source", {}).get("name", "")
        if source in PAYWALLED_SOURCES:
            continue  # Skip paywalled
        if source in PREFERRED_SOURCES:
            open_articles.append(a)
        else:
            other_articles.append(a)
    # Return preferred first, then others
    return open_articles + other_articles

VALID_CATEGORIES = {
    "general", "technology", "business",
    "science", "health", "entertainment", "sports"
}


def _get(endpoint: str, params: dict) -> dict:
    if not API_KEY:
        raise EnvironmentError("Missing NEWS_API_KEY in environment.")
    url = f"{BASE_URL}/{endpoint}"
    params["apiKey"] = API_KEY
    log.debug(f"GET {url} params={{k: v for k, v in params.items() if k != 'apiKey'}}")
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    log.debug(f"Response {resp.status_code} — {len(resp.content)} bytes")
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        raise ValueError(f"NewsAPI error: {data.get('message', 'unknown')}")
    return data


# ── Public API ────────────────────────────────────────────────────────────────

def get_top_headlines(category: str = "general", country: str = "us", count: int = 5) -> str:
    # Normalize and validate category
    category = category.lower().strip()
    if category not in VALID_CATEGORIES:
        log.warning(f"Invalid category '{category}' — falling back to 'general'")
        category = "general"

    log.info(f"get_top_headlines() — category='{category}' count={count}")
    try:
        data     = _get("top-headlines", {"country": country, "category": category, "pageSize": count})
        articles = data.get("articles", [])

        if not articles:
            log.info("No articles returned")
            return f"No headlines found for '{category}'."

        lines = [f"Top {category} headlines:"]
        for i, a in enumerate(articles[:count], 1):
            source = a.get("source", {}).get("name", "Unknown")
            title  = a.get("title", "No title")
            lines.append(f"{i}. {title} ({source})")

        log.info(f"Returning {len(articles)} headline(s) for '{category}'")
        return "\n".join(lines)

    except Exception as e:
        log.error(f"get_top_headlines() failed — {e}", exc_info=True)
        return f"News error: {e}"


def search_news(query: str, count: int = 4) -> str:
    log.info(f"search_news() — query='{query}' count={count}")
    try:
        data     = _get("everything", {"q": query, "pageSize": count, "language": "en", "sortBy": "publishedAt"})
        articles = data.get("articles", [])

        if not articles:
            log.info(f"No articles for query: '{query}'")
            return f"No news found for '{query}'."

        lines = [f"News about '{query}':"]
        for i, a in enumerate(articles[:count], 1):
            source = a.get("source", {}).get("name", "Unknown")
            lines.append(f"{i}. {a['title']} ({source})")

        log.info(f"Returning {len(articles)} result(s) for query '{query}'")
        return "\n".join(lines)

    except Exception as e:
        log.error(f"search_news() failed — {e}", exc_info=True)
        return f"News error: {e}"


def get_morning_news_brief(topics: list = None, count_per_topic: int = 2) -> str:
    """Fetch multi-topic brief for morning_brief.py."""
    if topics is None:
        topics = ["technology", "business", "general"]
    log.info(f"get_morning_news_brief() — topics={topics}")
    sections = []
    for topic in topics:
        result = get_top_headlines(category=topic, count=count_per_topic)
        sections.append(result)
    return "\n\n".join(sections)




def get_headlines_structured(category: str = "general", count: int = 5) -> list:
    """Return structured news data with images for UI, prioritizing open sources."""
    category = category.lower().strip()
    if category not in VALID_CATEGORIES:
        category = "general"
    log.info(f"get_headlines_structured() — category='{category}'")
    try:
        # Fetch more than needed so we can filter
        data = _get("top-headlines", {"country": "us", "category": category, "pageSize": count * 3})
        articles = filter_and_rank_articles(data.get("articles", []))
        return [{
            "title": a.get("title", ""),
            "src": a.get("source", {}).get("name", ""),
            "img": a.get("urlToImage", ""),
            "url": a.get("url", ""),
            "summary": (a.get("description") or "")[:120],
            "time": a.get("publishedAt", "")[:10] if a.get("publishedAt") else "",
            "open": a.get("source", {}).get("name", "") in PREFERRED_SOURCES
        } for a in articles[:count]]
    except Exception as e:
        log.error(f"get_headlines_structured() failed — {e}")
        return []

# ── Test CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else None
    if query:
        print(search_news(query))
    else:
        print(get_top_headlines("technology"))
