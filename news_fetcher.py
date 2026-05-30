"""
news_fetcher.py — AI Radio Echo
Fetches news from RSS feeds and HackerNews API.
  - feedparser is always fed via requests (never feedparser.parse(url) directly)
  - HTMLStripper is defined once at module level
  - Dedup: skip if 3+ significant words overlap
"""

import re
from html.parser import HTMLParser

import feedparser
import requests

# ---------------------------------------------------------------------------
# HTMLStripper — defined once at module level, not inside any loop
# ---------------------------------------------------------------------------

class HTMLStripper(HTMLParser):
    """Strips all HTML tags and returns plain text."""

    def __init__(self):
        super().__init__()
        self._data_parts: list[str] = []

    def handle_data(self, data: str):
        self._data_parts.append(data)

    def get_data(self) -> str:
        return " ".join(self._data_parts).strip()


def strip_html(raw: str) -> str:
    """Return plain text from an HTML string, collapsing whitespace."""
    if not raw:
        return ""
    s = HTMLStripper()
    s.feed(raw)
    text = s.get_data()
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Stop words and deduplication helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "about", "after", "again", "also", "been", "before", "being", "could",
    "doing", "during", "every", "first", "found", "from", "have", "here",
    "into", "more", "much", "only", "other", "over", "since", "some",
    "such", "than", "that", "their", "them", "then", "there", "these",
    "they", "this", "through", "under", "very", "what", "when", "where",
    "which", "while", "will", "with", "would", "your",
}


def _significant_words(text: str) -> set[str]:
    """Words that are longer than 4 chars and not in the stop list."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if len(w) > 4 and w not in _STOP_WORDS}


def _is_duplicate(headline: str, seen_headlines: set[str], seen_keywords: list[set[str]]) -> bool:
    """
    Returns True if the headline is considered a duplicate:
      - Exact match against seen_headlines
      - Keyword overlap: 3 or more significant words shared with any prior item
    """
    if headline in seen_headlines:
        return True
    incoming_kw = _significant_words(headline)
    if not incoming_kw:
        return False
    for prior_kw in seen_keywords:
        overlap = incoming_kw & prior_kw
        if len(overlap) >= 3:
            return True
    return False


# ---------------------------------------------------------------------------
# Feed sources
# ---------------------------------------------------------------------------

_RSS_SOURCES = [
    ("BBC",     "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
    ("Guardian","https://www.theguardian.com/world/rss"),
]

_HACKERNEWS_TOP_STORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
_HACKERNEWS_ITEM        = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

_REQUEST_TIMEOUT = 10  # seconds


def _fetch_rss(name: str, url: str, limit: int = 5) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns list of item dicts."""
    try:
        response = requests.get(url, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as exc:
        print(f"[News] RSS source '{name}' failed: {exc}")
        return []

    items = []
    for entry in feed.entries[:limit]:
        headline = strip_html(getattr(entry, "title", "") or "").strip()
        if not headline:
            continue
        summary = strip_html(
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        ).strip()
        link = getattr(entry, "link", "")
        items.append({
            "headline": headline,
            "original_headline": headline,
            "summary": summary[:500],
            "source": name,
            "url": link,
        })
    return items


def _fetch_hackernews(limit: int = 10) -> list[dict]:
    """Fetch top HackerNews stories. Returns list of item dicts."""
    try:
        resp = requests.get(_HACKERNEWS_TOP_STORIES, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        story_ids = resp.json()[:limit * 2]  # Fetch extra in case some are null
    except Exception as exc:
        print(f"[News] HackerNews top-stories failed: {exc}")
        return []

    items = []
    for story_id in story_ids:
        if len(items) >= limit:
            break
        try:
            resp = requests.get(
                _HACKERNEWS_ITEM.format(id=story_id), timeout=_REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"[News] HackerNews item {story_id} failed: {exc}")
            continue

        if not data or data.get("type") != "story":
            continue
        headline = (data.get("title") or "").strip()
        if not headline:
            continue
        items.append({
            "headline": headline,
            "original_headline": headline,
            "summary": f"HackerNews discussion with {data.get('score', 0)} points and "
                       f"{data.get('descendants', 0)} comments.",
            "source": "HackerNews",
            "url": data.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
        })

    return items


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fetch_news() -> list[dict]:
    """
    Fetch news from all sources.
    Returns a deduplicated list. Empty list means no new stories.
    """
    all_items: list[dict] = []
    failed_sources: list[str] = []

    # RSS feeds
    for name, url in _RSS_SOURCES:
        items = _fetch_rss(name, url, limit=5)
        if not items:
            failed_sources.append(name)
        all_items.extend(items)

    # HackerNews
    hn_items = _fetch_hackernews(limit=10)
    if not hn_items:
        failed_sources.append("HackerNews")
    all_items.extend(hn_items)

    if failed_sources:
        print(f"[News] Failed sources (continuing with others): {', '.join(failed_sources)}")

    if not all_items:
        print("[News] Warning: ALL news sources failed. Returning empty list.")
        return []

    # Deduplication pass
    seen_headlines: set[str] = set()
    seen_keywords:  list[set[str]] = []
    deduped: list[dict] = []

    for item in all_items:
        headline = item["headline"]
        if _is_duplicate(headline, seen_headlines, seen_keywords):
            continue
        seen_headlines.add(headline)
        seen_keywords.append(_significant_words(headline))
        deduped.append(item)

    print(f"[News] Fetched {len(deduped)} unique stories ({len(all_items)} raw, "
          f"{len(all_items) - len(deduped)} duplicates removed).")
    return deduped
