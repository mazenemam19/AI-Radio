import os
import requests
import feedparser
from dotenv import load_dotenv

load_dotenv()

class NewsFetcher:
    def __init__(self):
        self.guardian_key = os.environ.get("GUARDIAN_API_KEY")

    def fetch_rss_feeds(self):
        """Fetch items from BBC, Reuters, and The Guardian RSS feeds."""
        feeds = {
            "BBC News": "https://feeds.bbci.co.uk/news/rss.xml",
            "Reuters World": "https://rss.reuters.com/reuters/worldNews",
            "The Guardian World": "https://www.theguardian.com/world/rss"
        }
        items = []

        for source_name, url in feeds.items():
            try:
                print(f"[News Fetcher] Parsing RSS feed: {source_name}...")
                feed = feedparser.parse(url)
                
                # Fetch up to 3 stories from each feed
                for entry in feed.entries[:3]:
                    headline = entry.get("title", "").strip()
                    summary = entry.get("summary", "") or entry.get("description", "")
                    # Strip HTML tags if present in summary
                    if summary:
                        from html.parser import HTMLParser
                        class HTMLStripper(HTMLParser):
                            def __init__(self):
                                super().__init__()
                                self.reset()
                                self.fed = []
                            def handle_data(self, d):
                                self.fed.append(d)
                            def get_data(self):
                                return ''.join(self.fed)
                        stripper = HTMLStripper()
                        stripper.feed(summary)
                        summary = stripper.get_data().strip()[:300]

                    items.append({
                        "headline": headline,
                        "source": source_name,
                        "summary": summary,
                        "url": entry.get("link", "")
                    })
            except Exception as e:
                print(f"[News Fetcher] Error parsing feed {source_name}: {e}")

        return items

    def fetch_hackernews(self):
        """Fetch top 5 HackerNews stories."""
        items = []
        try:
            print("[News Fetcher] Fetching HackerNews top stories...")
            # Fetch top stories list
            r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
            top_ids = r.json()
            
            # Fetch details for top 5 stories
            for story_id in top_ids[:5]:
                try:
                    story_r = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=5)
                    story = story_r.json()
                    if story and story.get("title"):
                        headline = story.get("title", "").strip()
                        summary = story.get("text", "")[:300] if story.get("text") else f"HackerNews story with {story.get('score', 0)} points."
                        url = story.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                        items.append({
                            "headline": headline,
                            "source": "HackerNews",
                            "summary": summary,
                            "url": url
                        })
                except Exception as ex:
                    print(f"[News Fetcher] Error fetching HackerNews story {story_id}: {ex}")
        except Exception as e:
            print(f"[News Fetcher] Error fetching HackerNews: {e}")

        return items

        items = []
        try:
            print("[News Fetcher] Querying Guardian API...")
            # Query tech, science, and world sections
            url = f"https://content.guardianapis.com/search?section=technology|science|world&show-fields=trailText&api-key={self.guardian_key}"
            r = requests.get(url, timeout=10)
            results = r.json().get("response", {}).get("results", [])

            for item in results[:4]:
                headline = item.get("webTitle", "").strip()
                summary = item.get("fields", {}).get("trailText", "")[:300]
                items.append({
                    "headline": headline,
                    "source": f"The Guardian ({item.get('sectionName', 'World')})",
                    "summary": summary,
                    "url": item.get("webUrl", "")
                })
        except Exception as e:
            print(f"[News Fetcher] Error calling Guardian API: {e}")

        return items

    def get_all_news(self, processed_headlines=None):
        """Fetch from all sources, filter duplicates, and return a clean list of news items."""
        if processed_headlines is None:
            processed_headlines = []
        
        # Lowercase for robust checking
        processed_set = {h.lower().strip() for h in processed_headlines}
        
        raw_items = []
        raw_items.extend(self.fetch_rss_feeds())
        raw_items.extend(self.fetch_hackernews())

        unique_items = []
        seen_headlines = set()

        def get_keywords(text):
            """Simple extraction of significant words for similarity checking."""
            words = text.lower().split()
            # Ignore common small words
            stop_words = {'the', 'and', 'for', 'was', 'with', 'that', 'this', 'after', 'from', 'says', 'warns', 'in', 'on', 'at'}
            return {w for w in words if len(w) > 3 and w not in stop_words}

        # Pre-calculate keywords for history
        history_keywords = [get_keywords(h) for h in processed_headlines]

        for item in raw_items:
            headline = item["headline"]
            headline_lower = headline.lower().strip()
            item_keywords = get_keywords(headline_lower)
            
            # 1. Exact match check
            if headline_lower in processed_set:
                print(f"[News Fetcher] [SKIP] Exact headline match in history: {headline}")
                continue
            if headline_lower in seen_headlines:
                continue

            # 2. Topic similarity check (Keyword Overlap)
            # Threshold lowered to 2: If 2 or more significant words match, it's a duplicate.
            is_duplicate_topic = False
            for prev_keywords in history_keywords:
                overlap = item_keywords.intersection(prev_keywords)
                if len(overlap) >= 2:
                    print(f"[News Fetcher] [SKIP] Topic already covered (Overlap: {overlap}): {headline}")
                    is_duplicate_topic = True
                    break
            
            if is_duplicate_topic:
                continue
                
            seen_headlines.add(headline_lower)
            unique_items.append(item)

        print(f"[News Fetcher] Total unique, unprocessed news stories fetched: {len(unique_items)}")
        return unique_items
