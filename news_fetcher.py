"""
news_fetcher.py — AI Radio Echo
Fetches headlines from BBC, Reuters, Guardian RSS feeds and HackerNews API.
Deduplicates against existing headlines using keyword overlap.
"""

import requests
import feedparser
from html.parser import HTMLParser


# ------------------------------------------------------------------ #
#  HTML stripper — defined once at module level, never inside loops  #
# ------------------------------------------------------------------ #

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts).strip()


def _strip_html(html: str) -> str:
    s = _HTMLStripper()
    s.feed(html or "")
    return s.get_text()


# ------------------------------------------------------------------ #
#  Constants                                                          #
# ------------------------------------------------------------------ #

# 20-word stop list for keyword overlap detection
_STOP_WORDS: frozenset[str] = frozenset({
    "about", "after", "also", "been", "from", "have", "into",
    "more", "over", "says", "that", "their", "there", "these",
    "they", "this", "were", "what", "which", "with",
})

RSS_SOURCES: dict[str, str] = {
    "BBC":      "https://feeds.bbci.co.uk/news/rss.xml",
    "Reuters":  "https://feeds.reuters.com/reuters/topNews",
    "Guardian": "https://www.theguardian.com/world/rss",
}

_HN_TOP_URL  = "https://hacker-news.firebaseio.com/v0/topstories.json"
_HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

_RSS_PER_SOURCE  = 5
_HN_FETCH_LIMIT  = 10


# ------------------------------------------------------------------ #
#  Deduplication helpers                                              #
# ------------------------------------------------------------------ #

def _significant_words(text: str) -> set[str]:
    """Words longer than 4 chars that are not stop words."""
    return {
        w for w in text.lower().split()
        if len(w) > 4 and w not in _STOP_WORDS
    }


def _is_duplicate(headline: str, history: list[str]) -> bool:
    """
    Exact match → duplicate.
    ≥3 significant keyword overlap → duplicate.
    2-word overlap is NOT enough (too aggressive per spec).
    """
    headline_lower = headline.lower()
    sig = _significant_words(headline)

    for prev in history:
        if headline_lower == prev.lower():
            return True
        if len(sig & _significant_words(prev)) >= 3:
            return True
    return False


# ------------------------------------------------------------------ #
#  Source fetchers                                                    #
# ------------------------------------------------------------------ #

def _fetch_rss(source_name: str, url: str, limit: int) -> list[dict] | None:
    """
    Fetch up to `limit` items from an RSS feed.
    Returns None on failure (not empty list) so the caller can distinguish
    'source failed' from 'source returned no items'.
    Always passes content through requests with a 10-second timeout;
    never calls feedparser.parse(url) directly.
    """
    try:
        content = requests.get(url, timeout=10).content
        feed = feedparser.parse(content)
        items: list[dict] = []
        for entry in feed.entries[:limit]:
            title   = (entry.get("title") or "").strip()
            summary = entry.get("summary") or entry.get("description") or ""
            summary = _strip_html(summary)
            if title:
                items.append({
                    "headline": title,
                    "summary":  summary[:400],
                    "source":   source_name,
                })
        return items
    except Exception as e:
        print(f"[News] RSS fetch failed ({source_name}): {e}")
        return None


def _fetch_hackernews(limit: int) -> list[dict] | None:
    """
    Fetch up to `limit` story items from HackerNews.
    Returns None on total failure; returns partial list on item-level failures.
    """
    try:
        resp = requests.get(_HN_TOP_URL, timeout=10)
        resp.raise_for_status()
        story_ids: list[int] = resp.json()
    except Exception as e:
        print(f"[News] HackerNews top-stories fetch failed: {e}")
        return None

    items: list[dict] = []
    # Fetch more IDs than needed to account for non-story items
    for story_id in story_ids[: limit * 3]:
        if len(items) >= limit:
            break
        try:
            item_resp = requests.get(_HN_ITEM_URL.format(story_id), timeout=10)
            item = item_resp.json()
            if item and item.get("type") == "story" and item.get("title"):
                items.append({
                    "headline": item["title"],
                    "summary":  item.get("url") or item.get("text") or "",
                    "source":   "HackerNews",
                })
        except Exception as e:
            print(f"[News] HackerNews item {story_id} failed: {e}")
            continue  # partial failure — keep going

    return items


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def fetch_news(history_headlines: list[str] | None = None) -> list[dict]:
    """
    Fetch and deduplicate news from all sources.

    Args:
        history_headlines: Headlines already seen (used for dedup).
            Pass an empty list or None if no history.

    Returns:
        Deduplicated list of news items. Empty list means no new stories
        (caller should exit cleanly, not treat as an error).
    """
    if history_headlines is None:
        history_headlines = []

    raw_items: list[dict] = []
    failed_sources: list[str] = []

    # RSS sources
    for name, url in RSS_SOURCES.items():
        result = _fetch_rss(name, url, _RSS_PER_SOURCE)
        if result is None:
            failed_sources.append(name)
        else:
            raw_items.extend(result)

    # HackerNews
    hn_result = _fetch_hackernews(_HN_FETCH_LIMIT)
    if hn_result is None:
        failed_sources.append("HackerNews")
    else:
        raw_items.extend(hn_result)

    if failed_sources:
        print(f"[News] Warning: sources that failed: {', '.join(failed_sources)}")

    if not raw_items:
        print("[News] Warning: all news sources failed. No stories available.")
        return []

    # Deduplicate
    seen: list[str] = list(history_headlines)
    unique: list[dict] = []
    for item in raw_items:
        headline = item["headline"]
        if not _is_duplicate(headline, seen):
            unique.append(item)
            seen.append(headline)

    print(f"[News] Fetched {len(raw_items)} items; {len(unique)} unique after dedup.")
    return unique
