# Feature Spec 004: Deduplication Logic

## 🎯 Purpose
To ensure unique and non-repetitive content by anchoring the news scraper to original source headlines and separating satirical display titles from content-aware tracking.

## 🛠️ Implementation
- **Original Headline Tracking:** Persists the raw news title from RSS/API as `original_headline` in the database.
- **Display Title Separation:** Separates the satirical show title (e.g., "[The Descent into Cacophony]") from the news anchor.
- **Scraper Anchor:** The `NewsFetcher` compares incoming news *only* against the `original_headline` column, preventing "blindness" caused by satirical prefixing.
- **Overlap Sensitivity:** Uses a strict Keyword Overlap (Threshold: 2) to skip similar topics even if headlines are phrased differently.

## ⚙️ Logic
- **Database:** Stores both `headline` (display) and `original_headline` (tracking).
- **History:** Scraper checks the last 20 episodes for semantic keyword overlap.
