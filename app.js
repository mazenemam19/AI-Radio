(function () {
    'use strict';

    /* ── Utilities ─────────────────────────────────────────────── */

    function fmtDuration(secs) {
        if (!secs && secs !== 0) return '--:--';
        const s = Math.round(Number(secs));
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return `${m}:${String(rem).padStart(2, '0')}`;
    }

    function fmtDate(iso) {
        if (!iso) return '--';
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

    /* ── UI Handlers ────────────────────────────────────────── */

    function selectEpisode(idx) {
        if (window.isArchivesPage) {
            const ep = _episodes[idx];
            window.location.href = `control.html?id=${ep.id}`;
            return;
        }

        _selectedIdx = idx;
        const ep = _episodes[idx];

        // Mark active card
        document.querySelectorAll('.ep-card').forEach((c, i) => {
            c.classList.toggle('active', i === idx);
        });

        const empty = document.getElementById('detail-empty');
        const inner = document.getElementById('detail-inner');
        if (empty) empty.style.display = 'none';
        if (inner) {
            inner.style.display = 'block';
            inner.innerHTML = buildDetail(ep);

            // Accordion toggle
            inner.querySelectorAll('.accordion-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const acc = btn.closest('.accordion');
                    acc.classList.toggle('open');
                });
            });
        }

        // Mobile: show detail panel
        const detailPanel = document.getElementById('detail-panel');
        if (detailPanel) detailPanel.classList.add('mobile-open');
    }

    function buildDetail(ep) {
        const tags = parseTags(ep.topic_tags);
        const segments = parseAudioScript(ep.audio_script);

        let mediaHtml = '';
        const audioUrl = resolveUrl(ep.audio_url);
        const videoUrl = resolveUrl(ep.video_url);

        const hasAudio = audioUrl && !audioUrl.includes('placeholder') && 
                         (audioUrl.startsWith('http') || audioUrl.startsWith('output/'));
        const hasVideo = videoUrl && (videoUrl.startsWith('http') || videoUrl.startsWith('output/'));

        if (hasAudio) {
            mediaHtml = `<div class="media-wrap"><audio controls preload="metadata"><source src="${audioUrl}" type="audio/mpeg"></audio></div>`;
        } else if (hasVideo) {
            const ytId = getYoutubeId(videoUrl);
            if (ytId) {
                mediaHtml = `<div class="video-container" style="position:relative; padding-bottom:56.25%; height:0; overflow:hidden; border-radius:12px; background:#000;"><iframe src="https://www.youtube.com/embed/${ytId}" style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;" allowfullscreen></iframe></div>`;
            } else {
                mediaHtml = `<div class="media-wrap"><a href="${esc(videoUrl)}" target="_blank" class="btn-primary" style="font-size:14px; padding:12px 24px;">Watch Source</a></div>`;
            }
        } else {
            mediaHtml = `<div class="media-wrap"><div style="font-size:12px; color:var(--text-lo); letter-spacing:1px;">// Media Archive Offline</div></div>`;
        }

        const tagsHtml = tags.length ? `<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:16px;">${tags.map(t => `<span class="conf-badge" style="background:var(--void); color:var(--cyan); border:1px solid var(--border-mid);">#${esc(t)}</span>`).join('')}</div>` : '';
        const scriptHtml = segments.map(seg => `
            <div class="script-seg">
                <div class="script-speaker">${esc(seg.speaker)}</div>
                <div class="script-text">${esc(seg.text)}</div>
            </div>`).join('');

        const healed = ep.healer_used === true || ep.healer_used === 1 || ep.healer_used === 'true';

        return `
            <div class="detail-headline">${esc(ep.headline || 'Untitled Broadcast')}</div>
            
            <div class="detail-meta">
                <span class="meta-chip"><span class="lbl">SRC</span> ${esc(ep.source || '--')}</span>
                <span class="meta-chip"><span class="lbl">DATE</span> ${esc(fmtDate(ep.created_at))}</span>
                <span class="meta-chip"><span class="lbl">DUR</span> ${fmtDuration(ep.broadcast_duration)}</span>
                <span class="meta-chip"><span class="lbl">PLAYS</span> ${ep.plays ?? 0}</span>
                <span class="conf-badge ${confClass(ep.confidence)}">${confLabel(ep.confidence)}</span>
                ${healed ? '<span class="healer-chip healed">⚠ HEALED</span>' : ''}
            </div>

            <div class="d-section">
                <div class="d-section-lbl">// Transmission Archive</div>
                ${mediaHtml}
            </div>

            <div class="d-section">
                <div class="d-section-lbl">// AI Insights</div>
                <div class="my-take">${esc(ep.my_take || '')}</div>
                ${ep.post_text ? `<div style="margin-top:24px; font-size:14px; color:var(--text-mid); padding:20px; background:var(--void); border-radius:12px; line-height:1.6; border-left:4px solid var(--border-mid);">${esc(ep.post_text)}</div>` : ''}
                ${tagsHtml}
            </div>

            <div class="d-section">
                <div class="d-section-lbl">// Model Telemetry</div>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:16px;">
                    <div style="background:var(--void); padding:16px; border-radius:12px; border:1px solid var(--border);">
                        <div style="font-size:10px; font-weight:800; color:var(--text-lo); margin-bottom:6px; text-transform:uppercase; letter-spacing:1px;">Writer Model</div>
                        <div style="font-size:12px; font-weight:700; color:var(--primary);">${esc(ep.writer_model || '--')}</div>
                    </div>
                    <div style="background:var(--void); padding:16px; border-radius:12px; border:1px solid var(--border);">
                        <div style="font-size:10px; font-weight:800; color:var(--text-lo); margin-bottom:6px; text-transform:uppercase; letter-spacing:1px;">Narrator Model</div>
                        <div style="font-size:12px; font-weight:700; color:var(--primary);">${esc(ep.narrator_model || '--')}</div>
                    </div>
                </div>
            </div>

            <div class="d-section">
                <div class="d-section-lbl">// Raw Broadcast Script</div>
                <div class="accordion" id="script-accordion">
                    <button class="accordion-btn" style="width:100%; display:flex; justify-content:space-between; align-items:center; background:var(--void); border:none; padding:16px; border-radius:12px; cursor:pointer;">
                        <span style="font-weight:700; font-size:13px; color:var(--primary);">SHOW DIALOGUE — ${segments.length} SEGMENTS</span>
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style="transition:transform 0.2s;"><path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                    </button>
                    <div class="accordion-body" style="display:none; padding-top:20px;">${scriptHtml}</div>
                </div>
            </div>
        `;
    }

    function confClass(c) { return ['high', 'medium', 'low'].includes(c) ? c : 'null'; }
    function confLabel(c) { return { high: 'HIGH', medium: 'MED', low: 'LOW' }[c] || '--'; }

    /* ── Core components ───────────────────────────────────────── */

    function startClock() {
        const el = document.getElementById('header-clock');
        if (!el) return;
        const tick = () => { el.textContent = new Date().toLocaleTimeString(undefined, { hour12: false }); };
        tick(); setInterval(tick, 1000);
    }

    function startHeartbeat() {
        const el = document.getElementById('header-freq');
        if (!el) return;
        const base = 88.5;
        const pulse = () => { el.textContent = `SIGNAL: ${(base + (Math.random() * 0.4 - 0.2)).toFixed(1)} MHZ`; };
        pulse(); setInterval(pulse, 5000);
    }

    function setModePill(mode, label) {
        const pill = document.getElementById('mode-pill');
        const lbl = document.getElementById('mode-label');
        if (!pill || !lbl) return;
        pill.className = 'mode-pill ' + (mode === 'supabase' ? 'production' : mode);
        lbl.textContent = label;
    }

    function updateStats(cfg) {
        const episodes = cfg.episodes || [];
        const countEl = document.getElementById('stat-count');
        const playsEl = document.getElementById('stat-plays');
        const likesEl = document.getElementById('stat-likes');
        const feedCountEl = document.getElementById('feed-count');

        if (countEl) countEl.textContent = cfg.episode_count || episodes.length;
        if (playsEl) playsEl.textContent = (cfg.total_plays || episodes.reduce((a, e) => a + (Number(e.plays) || 0), 0)).toLocaleString();
        if (likesEl) likesEl.textContent = (cfg.total_likes || episodes.reduce((a, e) => a + (Number(e.likes) || 0), 0)).toLocaleString();
        if (feedCountEl) feedCountEl.textContent = `${episodes.length} / ${cfg.episode_count || episodes.length}`;
    }

    function renderFeed(episodes) {
        const list = document.getElementById('feed-list');
        if (!list) return;
        if (!episodes.length) {
            list.innerHTML = '<div class="feed-no-ep">No broadcasts found.</div>';
            return;
        }
        list.innerHTML = episodes.map((ep, i) => `
            <div class="ep-card" data-idx="${i}" tabindex="0">
                <div class="ep-card-row1">
                    <div class="ep-headline">${esc(ep.headline)}</div>
                    <span class="conf-badge ${confClass(ep.confidence)}">${confLabel(ep.confidence)}</span>
                </div>
                <div class="signal-wrap"><div class="signal-bar" style="width: ${Math.min(100, (ep.broadcast_duration/600)*100)}%"></div></div>
                <div class="ep-card-row2">
                    <span class="ep-source">${esc(ep.source || '--')}</span>
                    <div class="ep-eng">
                        <div class="ep-eng-item">P ${ep.plays ?? 0}</div>
                        <div class="ep-eng-item">L ${ep.likes ?? 0}</div>
                    </div>
                    <span class="ep-card-date">${esc(fmtDate(ep.created_at))}</span>
                </div>
            </div>
        `).join('');

        list.querySelectorAll('.ep-card').forEach(card => {
            card.addEventListener('click', () => selectEpisode(parseInt(card.dataset.idx, 10)));
        });
    }

    let _episodes = [];
    let _selectedIdx = null;

    async function init() {
        startClock();
        startHeartbeat();

        const detailPanel = document.getElementById('detail-panel');
        if (detailPanel) {
            const backBtn = document.createElement('div');
            backBtn.className = 'mobile-back-btn';
            backBtn.innerHTML = '← Back to feed';
            backBtn.addEventListener('click', () => { detailPanel.classList.remove('mobile-open'); });
            detailPanel.insertBefore(backBtn, detailPanel.firstChild);
        }

        try {
            const response = await fetch('config.json');
            const cfg = await response.json();
            _episodes = cfg.episodes || [];
            
            const mode = (cfg.mode || 'local').toLowerCase();
            const isProduction = mode === 'production' || mode === 'supabase';
            if (isProduction) {
                setModePill('production', 'PRODUCTION MODE');
            } else {
                setModePill('local', 'LOCAL — SQLITE');
            }

            updateStats(cfg);
            renderFeed(_episodes);

            const urlParams = new URLSearchParams(window.location.search);
            const id = urlParams.get('id');
            if (id) {
                const idx = _episodes.findIndex(e => String(e.id) === id);
                if (idx !== -1) selectEpisode(idx);
            }
        } catch (err) {
            console.error('[Echo FM] Init failed:', err);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
