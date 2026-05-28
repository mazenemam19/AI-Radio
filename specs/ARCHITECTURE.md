# AI Radio — Echo: System Architecture

This diagram uses **Mermaid.js** syntax to visualize the data flow of the Echo broadcast suite.

```mermaid
graph TD
    %% Data Sources
    subgraph Ingestion [1. Ingestion & Filtering]
        RSS[RSS Feeds: BBC, Reuters] --> NF[news_fetcher.py]
        HN[HackerNews API] --> NF
        NF -->|Deduplication: Keyword Overlap| DB[(SQLite / Supabase)]
    end
%% AI Core
subgraph Brain [2. AI Satirical Engine]
    DB -->|Context & Past Jokes| AC[ai_client.py]
    AC --> REAL_SWITCH{is_real_run?}

    REAL_SWITCH -->|Yes / Live| PROD_LOGIC[Full Context: 15 News / 10 Mem]
    PROD_LOGIC --> L70[Llama 3.3 70B: Versatile]

    REAL_SWITCH -->|No / Test| LOCAL_LOGIC[Trimmed Context: 3 News / 1 Mem]
    LOCAL_LOGIC --> G35[Gemini 3.5 Flash: Quota-Saver]

    L70 & G35 -->|Raw Output| HEAL[JSON Healer / String Repair]
end

%% Media Generation
subgraph Mastering [3. Media Mastering]
    HEAL -->|Cleaned Script| TTS[tts_generator.py]
    TTS --> TTS_SWITCH{is_real_run?}

    TTS_SWITCH -->|Yes| GROQ_TTS[Groq Cloud: Orpheus]
    GROQ_TTS -->|429 Rate Limit| EDGE_TTS

    TTS_SWITCH -->|No| EDGE_TTS[Microsoft Edge: Local]

        
        GROQ_TTS & EDGE_TTS --> AUD[Audio Master .mp3]
        
        HEAL -->|Visual Description| ART[Flux Model: Pollinations]
        ART -->|Neural Art| IMG[Background .png]
        
        AUD & IMG --> FF[FFmpeg Orchestrator]
        FF --> VIDEO[Final Broadcast .mp4]
        VIDEO --> DUR{Duration >= 700s?}
        DUR -->|No| ABORT[Discard Episode]
        DUR -->|Yes| GRID_FLOW
    end

    %% Distribution & Dashboard
    subgraph Grid [4. Distribution & Display]
        GRID_FLOW --> DIST_ENV{env == 'production'?}
        DIST_FLOW -->|Yes| YT[YouTube Upload]
        DIST_FLOW -->|Yes| BKY[Bluesky Post]
        
        DIST_ENV -->|No| LOCAL_OUT[./output/ Folder]
        DIST_ENV -->|No| MOCK[Mock Socials]
        
        HEAL -->|Metadata| DB
        
        DB -->|sync_config.py| CFG[config.js]
        CFG --> APP[app.js]
        
        LOCAL_OUT -->|HTML5 Player| APP
        YT -->|IFrame API| APP
        APP --> UI[Neon-Glass Dashboard]
    end

    %% Styling
    style Ingestion fill:#1a1a1a,stroke:#00f2ff,color:#fff
    style Brain fill:#1a1a1a,stroke:#7000ff,color:#fff
    style Mastering fill:#1a1a1a,stroke:#ff00ea,color:#fff
    style Grid fill:#1a1a1a,stroke:#00ff40,color:#fff
    style REAL_SWITCH fill:#333,stroke:#fff
    style TTS_SWITCH fill:#333,stroke:#fff
    style DIST_ENV fill:#333,stroke:#fff
    style DUR fill:#ff0000,stroke:#fff
```

---

## 🌍 Environment Logic Summary

| Feature | Production (Cloud) | Staging (Cloud) | Local (Offline) |
| :--- | :--- | :--- | :--- |
| **Trigger** | GitHub Actions | Manual CLI | Manual CLI |
| **AI Brain** | Llama 3.3 70B | Gemini 3.5 Flash | Gemini 3.5 Flash |
| **Context** | 15 News / 10 Memory | 3 News / 1 Memory | 3 News / 1 Memory |
| **Speech** | Groq Cloud TTS | Edge-TTS (Local) | Edge-TTS (Local) |
| **Database** | Supabase (Prod) | Supabase (Dev) | SQLite (Local) |
| **Video** | YouTube Upload | Mock (Rick Astley) | Local File |
| **Socials** | Bluesky Live | Mocked | Mocked |
| Quality | >700s Duration | >700s Duration | >700s Duration |

---

## 🛠️ Core Behavioral Mandates

The Echo system adheres to several "unwritten" rules that ensure the broadcast remains high-quality and the pipeline stays resilient:

1.  **JSON Resilience (The Healer):** The `ai_client.py` implements a state-aware machine to close open strings and brackets. If an LLM is cut off, the system "heals" the JSON to ensure the broadcast can still play.
2.  **Persona Integrity:** Echo (Host) and Glitch (Correspondent) are banned from using professional titles. Their dynamic is purely argumentative and rhythmic.
3.  **Forward Momentum:** Each segment must introduce new information. Restating previous segments is a hard logic failure that the AI is commanded to avoid.
4.  **Deduplication Anchor:** The system never "forgets." It tracks original news headlines to ensure that even if the AI changes the show title, the underlying story is never repeated.

