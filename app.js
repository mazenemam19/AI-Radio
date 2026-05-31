(function () {
    'use strict';

    /* ── Utilities ─────────────────────────────────────────────── */

    function fmtDuration(secs) {
        if (!secs && secs !== 0) return '—';
        const s = Math.round(Number(secs));
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return `${m}:${String(rem).padStart(2, '0')}`;
    }

    function fmtDate(iso) {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleString(undefined, {
                month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        } catch { return iso; }
    }

    function parseTags(raw) {
        if (!raw) return [];
        if (Array.isArray(raw)) return raw;
        try { const v = JSON.parse(raw); return Array.isArray(v) ? v : []; }
        catch { return String(raw).split(',').map(t => t.trim()).filter(Boolean); }
    }

    function parseAudioScript(raw) {
        if (!raw) return [];
        let parsed = raw;
        if (typeof parsed === 'string') {
            try { parsed = JSON.parse(raw); } catch { return [{ speaker: 'SEGMENT 01', text: raw }]; }
        }
        if (!Array.isArray(parsed)) return [];
        return parsed.map((item, i) => {
            if (typeof item === 'string') return { speaker: `SEGMENT ${String(i + 1).padStart(2, '0')}`, text: item };
            if (item && typeof item === 'object') return {
                speaker: (item.speaker || `SEGMENT ${String(i + 1).padStart(2, '0')}`).toUpperCase(),
                text: item.text || ''
            };
            return null;
        }).filter(Boolean);
    }

    function esc(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /**
     * Resolves a URL, mapping local:// URIs to the local output directory.
     * @param {string} url The URL to resolve.
     * @return {string|null} The resolved URL or null.
     */
    function resolveUrl(url) {
        if (!url) return null;
        if (typeof url !== 'string') return url;
        if (url.startsWith('local://')) {
            return 'output/' + url.substring(8);
        }
        return url;
    }

    function getYoutubeId(url) {
        if (!url) return null;
        const match = url.match(/(?:v=|\/)([0-9A-Za-z_-]{11}).*/);
        return match ? match[1] : null;
    }

    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            s.onload = resolve;
            s.onerror = () => reject(new Error('Failed to load: ' + src));
            document.head.appendChild(s);
        });
    }

    function showFullscreenState(type, title, body) {
        document.getElementById('app').style.display = 'none';
        const el = document.createElement('div');
        el.className = 'fs-state';
        el.innerHTML = `
      <div class="fs-logo">ECHO FM</div>
      ${type === 'loading' ? '<div class="spinner"></div>' : ''}
      <div class="fs-title ${type}">${esc(title)}</div>
      <div class="fs-body">${body}</div>
    `;
        document.body.appendChild(el);
        return el;
    }

    /* ── Clock ─────────────────────────────────────────────────── */
    function startClock() {
        const el = document.getElementById('header-clock');
        function tick() {
            const now = new Date();
            el.textContent = now.toLocaleTimeString(undefined, { hour12: false });
        }
        tick();
        setInterval(tick, 1000);
    }

    function startHeartbeat() {
        const el = document.getElementById('header-freq');
        const base = 88.5;
        function pulse() {
            const dev = (Math.random() * 0.4) - 0.2;
            el.textContent = `SIGNAL: ${(base + dev).toFixed(1)} MHZ`;
        }
        pulse();
        setInterval(pulse, 3000);
    }

    /* ── Mode pill ─────────────────────────────────────────────── */
    function setModePill(mode, label) {
        const pill = document.getElementById('mode-pill');
        const lbl = document.getElementById('mode-label');
        pill.className = 'mode-pill ' + mode;
        lbl.textContent = label;
    }

    /* ── Stats ─────────────────────────────────────────────────── */
    function updateStats(episodes) {
        document.getElementById('stat-count').textContent = episodes.length;
        document.getElementById('stat-plays').textContent =
            episodes.reduce((a, e) => a + (Number(e.plays) || 0), 0).toLocaleString();
        document.getElementById('stat-likes').textContent =
            episodes.reduce((a, e) => a + (Number(e.likes) || 0), 0).toLocaleString();
        document.getElementById('header-freq').textContent =
            `${episodes.length} EPISODE${episodes.length !== 1 ? 'S' : ''} ON RECORD`;
        document.getElementById('feed-count').textContent =
            `${episodes.length} / 20`;
    }

    /* ── Feed rendering ────────────────────────────────────────── */
    let _episodes = [];
    let _selectedIdx = null;

    function confClass(c) {
        if (!c) return 'null';
        return ['high', 'medium', 'low'].includes(c) ? c : 'null';
    }
    function confLabel(c) {
        if (!c) return '—';
        return { high: 'HIGH', medium: 'MED', low: 'LOW' }[c] || c.toUpperCase();
    }

    function renderFeed(episodes) {
        const list = document.getElementById('feed-list');
        if (!episodes.length) {
            list.innerHTML = '<div class="feed-no-ep">No broadcasts generated yet.<br>Run the pipeline to see episodes here.</div>';
            return;
        }
        list.innerHTML = episodes.map((ep, i) => {
            // Target is 10 minutes (600s). Bar fills up to 100% at 10m.
            const targetSecs = 600;
            const progress = Math.min(100, Math.round((Number(ep.broadcast_duration) || 0) / targetSecs * 100));
            
            return `
      <div class="ep-card" data-idx="${i}" tabindex="0" role="button" aria-label="Episode: ${esc(ep.headline)}">
        <div class="ep-card-row1">
          <div class="ep-headline">${esc(ep.headline || 'Untitled Broadcast')}</div>
          <span class="conf-badge ${confClass(ep.confidence)}">${confLabel(ep.confidence)}</span>
        </div>
        <div class="signal-wrap">
          <div class="signal-bar" style="width: ${progress}%"></div>
        </div>
        <div class="ep-card-row2">
          <span class="ep-source">${esc(ep.source || '—')}</span>
          <span>${esc(fmtDate(ep.created_at))}</span>
          <span class="ep-duration">${fmtDuration(ep.broadcast_duration)}</span>
        </div>
      </div>
    `}).join('');

        // Card click handlers
        list.querySelectorAll('.ep-card').forEach(card => {
            function select() {
                const idx = parseInt(card.dataset.idx, 10);
                selectEpisode(idx);
            }
            card.addEventListener('click', select);
            card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') select(); });
        });
    }

    /* ── Detail rendering ──────────────────────────────────────── */
    function selectEpisode(idx) {
        _selectedIdx = idx;
        const ep = _episodes[idx];

        // Mark active card
        document.querySelectorAll('.ep-card').forEach((c, i) => {
            c.classList.toggle('active', i === idx);
        });

        document.getElementById('detail-empty').style.display = 'none';
        const inner = document.getElementById('detail-inner');
        inner.style.display = 'block';

        // Mobile: show detail panel
        document.getElementById('detail-panel').classList.add('mobile-open');

        inner.innerHTML = buildDetail(ep);

        // Accordion toggle
        inner.querySelectorAll('.accordion-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const acc = btn.closest('.accordion');
                acc.classList.toggle('open');
            });
        });
    }

    function buildDetail(ep) {
        const tags = parseTags(ep.topic_tags);
        const segments = parseAudioScript(ep.audio_script);
        const origDiff = ep.original_headline && ep.original_headline !== ep.headline;

        /* Media section */
        let mediaHtml = '';
        const audioUrl = resolveUrl(ep.audio_url);
        const videoUrl = resolveUrl(ep.video_url);

        const hasAudio = audioUrl && 
                         !audioUrl.includes('placeholder') && 
                         (audioUrl.startsWith('http') || audioUrl.startsWith('output/'));
        const hasVideo = videoUrl && 
                         (videoUrl.startsWith('http') || videoUrl.startsWith('output/'));

        if (hasAudio) {
            console.log('[Echo FM] Rendering audio player with URL:', audioUrl);
            mediaHtml = `
        <div class="media-wrap">
          <audio controls preload="metadata" onplay="console.log('[Echo FM] Audio play started')" onerror="console.error('[Echo FM] Audio error:', this.error)">
            <source src="${audioUrl}" type="audio/mpeg">
            Your browser does not support the audio element.
          </audio>
        </div>`;
        } else if (hasVideo) {
            const ytId = getYoutubeId(videoUrl);
            if (ytId) {
                console.log('[Echo FM] Rendering YouTube iframe for ID:', ytId);
                mediaHtml = `
            <div class="video-container">
              <iframe 
                src="https://www.youtube.com/embed/${ytId}" 
                title="YouTube video player" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                allowfullscreen>
              </iframe>
            </div>`;
            } else if (videoUrl.startsWith('output/')) {
                console.log('[Echo FM] Rendering local video player:', videoUrl);
                mediaHtml = `
            <div class="media-wrap">
              <video controls width="100%" preload="metadata" style="display:block; border-radius:var(--radius); border: 1px solid var(--border-active);">
                <source src="${videoUrl}" type="video/mp4">
                Your browser does not support the video element.
              </video>
            </div>`;
            } else {
                console.log('[Echo FM] Rendering external video link:', videoUrl);
                mediaHtml = `<div class="media-wrap">
            <a href="${esc(videoUrl)}" target="_blank" rel="noopener" class="media-yt-btn">
              ${'▶ Watch on YouTube'}
            </a>
          </div>`;
            }
        } else {
            mediaHtml = `<div class="media-wrap"><div class="media-offline">Media Archive Offline (Dry Run / Local Mode)</div></div>`;
        }

        /* Tags */
        const tagsHtml = tags.length
            ? `<div class="tags">${tags.map(t => `<span class="tag">#${esc(t)}</span>`).join('')}</div>`
            : '<div style="font-size:10px;color:var(--text-lo);margin-top:8px;">No tags</div>';

        /* Telemetry */
        const healed = ep.healer_used === true || ep.healer_used === 1 || ep.healer_used === 'true';
        const healedHtml = healed
            ? `<span class="healer-chip healed">⚠ HEALED</span>`
            : `<span class="healer-chip not-healed">CLEAN</span>`;

        /* Audio script segments */
        const scriptHtml = segments.length
            ? segments.map(seg => `
          <div class="script-seg">
            <div class="script-speaker">${esc(seg.speaker)}</div>
            <div class="script-text">${esc(seg.text)}</div>
          </div>`).join('')
            : `<div class="script-no-data">// No audio script recorded for this episode</div>`;

        return `
      <div class="detail-headline">${esc(ep.headline || 'Untitled Broadcast')}</div>
      ${origDiff ? `<div class="detail-orig">↳ orig: ${esc(ep.original_headline)}</div>` : ''}

      <div class="detail-meta">
        <span class="meta-chip"><span class="lbl">SRC</span> ${esc(ep.source || '—')}</span>
        <span class="meta-chip"><span class="lbl">DATE</span> ${esc(fmtDate(ep.created_at))}</span>
        <span class="meta-chip"><span class="lbl">DURATION</span> ${fmtDuration(ep.broadcast_duration)}</span>
        <span class="meta-chip"><span class="lbl">PLAYS</span> ${ep.plays ?? 0}</span>
        <span class="meta-chip"><span class="lbl">LIKES</span> ${ep.likes ?? 0}</span>
        <span class="conf-badge ${confClass(ep.confidence)}" style="font-size:9px">${confLabel(ep.confidence)}</span>
      </div>

      <!-- MEDIA -->
      <div class="d-section">
        <div class="d-section-lbl">// Transmission Archive</div>
        ${mediaHtml}
      </div>

      <!-- AI INSIGHTS -->
      <div class="d-section">
        <div class="d-section-lbl">// AI Insights</div>
        ${ep.my_take ? `<div class="my-take">${esc(ep.my_take)}</div>` : ''}
        ${ep.post_text ? `<div class="post-text">${esc(ep.post_text)}</div>` : ''}
        ${tagsHtml}
      </div>

      <!-- MODEL TELEMETRY -->
      <div class="d-section">
        <div class="d-section-lbl">// Model Telemetry</div>
        <div class="telem-grid">
          <div class="telem-cell">
            <div class="telem-k">Writer Model</div>
            <div class="telem-v">${esc(ep.writer_model || '—')}</div>
          </div>
          <div class="telem-cell">
            <div class="telem-k">Narrator Model</div>
            <div class="telem-v">${esc(ep.narrator_model || '—')}</div>
          </div>
          <div class="telem-cell">
            <div class="telem-k">JSON Healer</div>
            <div class="telem-v">${healedHtml}</div>
          </div>
        </div>
      </div>

      <!-- AUDIO SCRIPT ACCORDION -->
      <div class="d-section">
        <div class="d-section-lbl">// Raw Broadcast Script</div>
        <div class="accordion" id="script-accordion">
          <button class="accordion-btn" aria-expanded="false">
            <span>SHOW DIALOGUE — ${segments.length} SEGMENT${segments.length !== 1 ? 'S' : ''}</span>
            <svg class="accordion-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
          <div class="accordion-body">${scriptHtml}</div>
        </div>
      </div>
    `;
    }

    /* ── Main init ─────────────────────────────────────────────── */
    async function init() {
        console.log('[Echo FM] Initialising dashboard...');
        startClock();
        startHeartbeat();

        // Mobile back button
        const detailPanel = document.getElementById('detail-panel');
        const backBtn = document.createElement('div');
        backBtn.className = 'mobile-back-btn';
        backBtn.innerHTML = '← Back to feed';
        backBtn.addEventListener('click', () => {
            detailPanel.classList.remove('mobile-open');
            _selectedIdx = null;
        });
        detailPanel.insertBefore(backBtn, detailPanel.firstChild);

        // Fetch config.json (Cache-safe)
        let cfg = null;
        try {
            console.log('[Echo FM] Fetching configuration...');
            const response = await fetch('config.json', { cache: 'no-store' });
            if (!response.ok) throw new Error('Config fetch failed');
            cfg = await response.json();
        } catch (err) {
            console.warn('[Echo FM] Configuration missing or failed to load:', err);
            setModePill('error', 'NO CONFIG');
            showFullscreenState('warn', 'SIGNAL OFFLINE',
                `config.json not found or corrupted.<br><br>` +
                `Run the pipeline to generate it:<br>` +
                `<code>python main.py --env local --dry-run</code><br><br>` +
                `Then serve this directory with:<br>` +
                `<code>python -m http.server 8080</code>`
            );
            return;
        }

        console.log('[Echo FM] Config loaded:', { mode: cfg.mode, env: cfg.env });

        const mode = (cfg.mode || 'local').toLowerCase();
        const isProduction = mode === 'production' || mode === 'supabase';

        if (isProduction) {
            console.log('[Echo FM] Entering production mode...');
            setModePill('production', 'PRODUCTION — SUPABASE');
            await loadProduction(cfg);
        } else {
            console.log('[Echo FM] Entering local mode...');
            setModePill('local', 'LOCAL — SQLITE');
            loadLocal(cfg);
        }
    }

    function loadLocal(cfg) {
        const episodes = Array.isArray(cfg.episodes) ? cfg.episodes : [];
        console.log(`[Echo FM] Loaded ${episodes.length} local episodes.`);
        _episodes = episodes;
        updateStats(episodes);
        renderFeed(episodes);
        document.getElementById('header-freq').textContent =
            `SERVING LOCAL SQLITE — ${episodes.length} EP${episodes.length !== 1 ? 'S' : ''}`;
    }

    async function loadProduction(cfg) {
        console.log('[Echo FM] Loading production data from Supabase...');
        // Support both camelCase (spec) and snake_case (older sync_config.py)
        const supabaseUrl = cfg.supabaseUrl || cfg.supabase_url || '';
        const supabaseKey = cfg.supabaseKey || cfg.supabase_key || '';

        if (!supabaseUrl || !supabaseKey) {
            console.error('[Echo FM] Supabase credentials missing from config.');
            setModePill('error', 'CONFIG ERROR');
            const loadEl = showFullscreenState('error', 'CREDENTIALS MISSING',
                'config.js is in production mode but supabaseUrl or supabaseKey is absent.<br><br>' +
                'Re-run the pipeline with a valid --env prod-db or --env production profile.'
            );
            return;
        }

        const loadEl = showFullscreenState('loading', 'CONNECTING TO SUPABASE', 'Establishing secure channel...');

        try {
            console.log('[Echo FM] Fetching Supabase library...');
            // Inject Supabase CDN dynamically
            await loadScript('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js');

            console.log('[Echo FM] Supabase library loaded. Initialising client...');
            const client = window.supabase.createClient(supabaseUrl, supabaseKey);
            const { data, error } = await client
                .from('memory_log')
                .select('*')
                .order('created_at', { ascending: false })
                .limit(20);

            if (error) throw error;

            console.log(`[Echo FM] Successfully fetched ${data ? data.length : 0} episodes from Supabase.`);

            // Restore app, populate UI
            loadEl.remove();
            document.getElementById('app').style.display = '';
            document.getElementById('header-freq').textContent = `SUPABASE — LIVE DATA`;

            _episodes = data || [];
            updateStats(_episodes);
            renderFeed(_episodes);

        } catch (err) {
            console.error('[Echo FM] Supabase connection error:', err);
            loadEl.innerHTML = `
        <div class="fs-logo">ECHO FM</div>
        <div class="fs-title error">SUPABASE ERROR</div>
        <div class="fs-body">${esc(String(err.message || err))}<br><br>
          Check your Supabase credentials and that the memory_log table exists.
        </div>
      `;
            setModePill('error', 'DB ERROR');
        }
    }

    /* ── Boot ──────────────────────────────────────────────────── */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
