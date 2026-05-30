"""
news_fetcher.py — Fetches and deduplicates news from RSS feeds and HackerNews.

Sources:
  - BBC News RSS       (up to 5 items)
  - Reuters RSS        (up to 5 items)
  - The Guardian RSS   (up to 5 items)
  - HackerNews API     (up to 10 items)

Deduplication rules:
  - Exact headline match → skip
  - 3+ significant keyword overlap → skip  (NOT 2, which is too aggressive)
  - Significant word: length > 4 AND not in STOP_WORDS
"""

import requests
import feedparser  # type: ignore
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# HTMLStripper — defined ONCE at module level, never inside a loop
# ---------------------------------------------------------------------------

class HTMLStripper(HTMLParser):
    """Minimal HTML tag stripper for feed summaries."""

    def __init__(self):
        super().__init__()
        self._data: list[str] = []

    def handle_data(self, data: str):
        self._data.append(data)

    def get_data(self) -> str:
        return " ".join(self._data).strip()


def strip_html(raw: str) -> str:
    s = HTMLStripper()
    s.feed(raw or "")
    return s.get_data()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RSS_SOURCES = {
    "BBC":     "http://feeds.bbci.co.uk/news/rss.xml",
    "Reuters": "https://feeds.reuters.com/reuters/topNews",
    "Guardian":"https://www.theguardian.com/world/rss",
}
RSS_LIMIT = 5
HN_LIMIT  = 10
FETCH_TIMEOUT = 10  # seconds per request

STOP_WORDS = {
    "about", "after", "also", "been", "does", "from", "have",
    "into", "more", "most", "over", "says", "that", "their",
    "there", "they", "this", "were", "will", "with",
}


# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

def _significant_words(headline: str) -> set[str]:
    """Return words that are longer than 4 chars and not in STOP_WORDS."""
    return {
        w.lower().strip(".,!?\"'")
        for w in headline.split()
        if len(w) > 4 and w.lower() not in STOP_WORDS
    }


def _is_duplicate(headline: str, seen_headlines: set[str], seen_word_sets: list[set]) -> bool:
    """
    Return True if this headline should be skipped due to duplication.
    Exact match OR 3+ significant word overlap.
    """
    if headline in seen_headlines:
        return True
    words = _significant_words(headline)
    for existing in seen_word_sets:
        if len(words & existing) >= 3:
            return True
    return False


# ---------------------------------------------------------------------------
# Per-source fetchers
# ---------------------------------------------------------------------------

def _fetch_rss(source_name: str, url: str, limit: int) -> list[dict]:
    """Fetch up to `limit` items from an RSS feed via requests → feedparser."""
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries[:limit]:
            title   = entry.get("title", "").strip()
            summary = strip_html(entry.get("summary", entry.get("description", "")))
            link    = entry.get("link", "")
            if title:
                items.append({
                    "title":   title,
                    "summary": summary,
                    "url":     link,
                    "source":  source_name,
                })
        return items
    except Exception as exc:
        print(f"[NewsFetcher] {source_name} RSS failed: {exc}")
        return []


def _fetch_hackernews(limit: int) -> list[dict]:
    """Fetch top HackerNews stories."""
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        ids = resp.json()[:limit * 2]  # fetch extra in case some items are bad

        items = []
        for story_id in ids:
            if len(items) >= limit:
                break
            try:
                item_resp = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=FETCH_TIMEOUT,
                )
                item_resp.raise_for_status()
                story = item_resp.json()
                title = (story or {}).get("title", "").strip()
                url   = (story or {}).get("url", "")
                if title:
                    items.append({
                        "title":   title,
                        "summary": "",
                        "url":     url,
                        "source":  "HackerNews",
                    })
            except Exception as exc:
                print(f"[NewsFetcher] HackerNews item {story_id} failed: {exc}")
                continue

        return items
    except Exception as exc:
        print(f"[NewsFetcher] HackerNews top-stories fetch failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_news(history_headlines: "list[str] | None" = None) -> list[dict]:
    """
    Fetch news from all sources, deduplicate, and return a flat list.

    Args:
        history_headlines: Optional list of previous headlines to deduplicate against.

    Returns:
        List of dicts with keys: title, summary, url, source.
        Returns empty list (not an error) if all sources fail — caller decides.
    """
    history_headlines = history_headlines or []

    # Pre-load history into dedup state
    seen_headlines: set[str] = set(history_headlines)
    seen_word_sets: list[set] = [_significant_words(h) for h in history_headlines]

    failed_sources: list[str] = []
    all_raw: list[dict]       = []

    # --- RSS sources ---
    for name, url in RSS_SOURCES.items():
        items = _fetch_rss(name, url, RSS_LIMIT)
        if not items:
            failed_sources.append(name)
        all_raw.extend(items)

    # --- HackerNews ---
    hn_items = _fetch_hackernews(HN_LIMIT)
    if not hn_items:
        failed_sources.append("HackerNews")
    all_raw.extend(hn_items)

    # --- Report partial failures ---
    if failed_sources:
        print(f"[NewsFetcher] Warning: the following sources failed or returned no items: {failed_sources}")

    if not all_raw:
        print("[NewsFetcher] Warning: ALL sources failed. Returning empty list.")
        return []

    # --- Deduplicate ---
    deduped: list[dict] = []
    for item in all_raw:
        headline = item["title"]
        if _is_duplicate(headline, seen_headlines, seen_word_sets):
            continue
        seen_headlines.add(headline)
        seen_word_sets.append(_significant_words(headline))
        deduped.append(item)

    print(f"[NewsFetcher] Fetched {len(all_raw)} raw items → {len(deduped)} after deduplication.")
    return deduped
