from __future__ import annotations
import re

import httpx

NEWS_API_BASE = "https://newsapi.org/v2/everything"

_WIKI_HEADERS = {
    "User-Agent": "Nexus/1.0 (personal knowledge tool; https://github.com/anthropics/nexus)",
}


async def search_news(
    query: str,
    api_key: str,
    page: int = 1,
    page_size: int = 10,
) -> list[dict]:
    """Search NewsAPI for articles. Returns list of article dicts."""
    params = {
        "q": query,
        "apiKey": api_key,
        "page": page,
        "pageSize": page_size,
        "sortBy": "relevancy",
        "language": "en",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(NEWS_API_BASE, params=params)
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "title": a.get("title") or "",
            "description": a.get("description") or "",
            "content": a.get("content") or "",
            "url": a.get("url") or "",
            "source": (a.get("source") or {}).get("name", ""),
            "publishedAt": a.get("publishedAt") or "",
        }
        for a in data.get("articles", [])
        if (a.get("title") or "") not in ("", "[Removed]")
    ]


async def search_wiki(
    query: str,
    language: str = "en",
    limit: int = 10,
) -> list[dict]:
    """Search Wikipedia via MediaWiki API. Returns list of result dicts."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=15.0, headers=_WIKI_HEADERS) as client:
        resp = await client.get(
            f"https://{language}.wikipedia.org/w/api.php", params=params
        )
        resp.raise_for_status()
        data = resp.json()
    results = []
    for item in data.get("query", {}).get("search", []):
        title = item["title"]
        snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
        results.append({
            "title": title,
            "description": snippet,
            "url": f"https://{language}.wikipedia.org/wiki/{title.replace(' ', '_')}",
            "source": "Wikipedia",
            "language": language,
        })
    return results


async def fetch_wiki_full_text(title: str, language: str = "en") -> str:
    """Fetch the full plain-text extract of a Wikipedia article."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "format": "json",
        "formatversion": "2",
    }
    async with httpx.AsyncClient(timeout=20.0, headers=_WIKI_HEADERS) as client:
        resp = await client.get(
            f"https://{language}.wikipedia.org/w/api.php", params=params
        )
        resp.raise_for_status()
        data = resp.json()
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return ""
    return pages[0].get("extract", "")
