# Track Specification: Fresh Brain Update

## Overview
Implement a three-pronged creative and technical overhaul to eliminate content repetition, break formulaic dialogue loops, and refresh the station's satirical vocabulary.

## Functional Requirements

### 1. Tag-Aware Topic Burn (Technical)
- **Aggressive Deduplication:** Update `news_fetcher.py` to treat recent topic tags as absolute blocks.
- **Logic:** If a headline contains a keyword from the `topic_tags` of the last 10 episodes, it is rejected.
- **Goal:** Force the station to find new stories instead of repeating the same top headlines for 48 hours.

### 2. Reactive Clash Protocol (Creative)
- **Perspective Injection:** Update `ai_client.py` to assign adversarial roles based on news content.
- **Conditional Dread:** Alistair's existential crisis is no longer constant. It scales with news confidence and severity (e.g., 'Low' crisis for tech news, 'High' for climate/conflict).
- **Mandatory Friction:** Prompt the AI to include segments where Victoria or Ronald challenge the previous speaker's take as being "too naive" or "missing the human angle."

### 3. Semantic Refresh (Creative)
- **Trope Blacklist:** Explicitly forbid overused AI-isms: "recursive loop," "deck chairs," "sinking ship," "void," "static."
- **Style Diversity:** Demand the use of fresh, non-digital metaphors for social decay.
- **Recency Memory:** Pass the last 5 titles to the prompt as examples of structures to avoid.

## Acceptance Criteria
- [ ] News fetcher rejects stories containing words from recent topic tags.
- [ ] AI scripts show character disagreement in at least 2 segments.
- [ ] Alistair's tone varies according to the news type.
- [ ] No blacklisted tropes appear in the generated scripts.
- [ ] Titles are structurally different from the last 5 episodes.
