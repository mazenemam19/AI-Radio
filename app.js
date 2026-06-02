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
        const origDiff = ep.original_headline && ep.original_headline !== ep.headline;

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
                mediaHtml = `<div class="video-container"><iframe src="https://www.youtube.com/embed/${ytId}" allowfullscreen></iframe></div>`;
            } else {
                mediaHtml = `<div class="media-wrap"><a href="${esc(videoUrl)}" target="_blank" class="media-yt-btn">▶ Watch Source</a></div>`;
            }
        } else {
            mediaHtml = `<div class="media-wrap"><div class="media-offline">// Media Archive Offline</div></div>`;
        }

        const tagsHtml = tags.length ? `<div class="tags">${tags.map(t => `<span class="tag">#${esc(t)}</span>`).join('')}</div>` : '';
        const scriptHtml = segments.map(seg => `
            <div class="script-seg">
                <div class="script-speaker">${esc(seg.speaker)}</div>
                <div class="script-text">${esc(seg.text)}</div>
            </div>`).join('');

        const healed = ep.healer_used === true || ep.healer_used === 1 || ep.healer_used === 'true';

        return `
            <div class="detail-headline">${esc(ep.headline || 'Untitled Broadcast')}</div>
            ${origDiff ? `<div class="detail-orig">↳ orig: ${esc(ep.original_headline)}</div>` : ''}
            
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
                ${ep.post_text ? `<div class="post-text" style="margin-top:20px; font-size:13px; color:var(--text-mid); padding:16px; background:var(--void); border-radius:8px;">${esc(ep.post_text)}</div>` : ''}
                ${tagsHtml}
            </div>

            <div class="d-section">
                <div class="d-section-lbl">// Model Telemetry</div>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:12px;">
                    <div style="background:var(--void); padding:12px; border-radius:8px; border:1px solid var(--border);">
                        <div style="font-size:9px; font-weight:800; color:var(--text-lo); margin-bottom:4px; text-transform:uppercase;">Writer</div>
                        <div style="font-size:11px; font-weight:600; color:var(--primary);">${esc(ep.writer_model || '--')}</div>
                    </div>
                    <div style="background:var(--void); padding:12px; border-radius:8px; border:1px solid var(--border);">
                        <div style="font-size:9px; font-weight:800; color:var(--text-lo); margin-bottom:4px; text-transform:uppercase;">Narrator</div>
                        <div style="font-size:11px; font-weight:600; color:var(--primary);">${esc(ep.narrator_model || '--')}</div>
                    </div>
                </div>
            </div>

            <div class="d-section">
                <div class="d-section-lbl">// Raw Broadcast Script</div>
                <div class="accordion" id="script-accordion">
                    <button class="accordion-btn">
                        <span>SHOW DIALOGUE — ${segments.length} SEGMENTS</span>
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style="transition:transform 0.2s;"><path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                    </button>
                    <div class="accordion-body">${scriptHtml}</div>
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

    function updateStats(cfg) {
        const countEl = document.getElementById('stat-count');
        const playsEl = document.getElementById('stat-plays');
        const likesEl = document.getElementById('stat-likes');
        if (countEl) countEl.textContent = cfg.episode_count || 0;
        if (playsEl) playsEl.textContent = (cfg.total_plays || 0).toLocaleString();
        if (likesEl) likesEl.textContent = (cfg.total_likes || 0).toLocaleString();
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
                        <div class="ep-eng-item">▶ ${ep.plays ?? 0}</div>
                        <div class="ep-eng-item">❤ ${ep.likes ?? 0}</div>
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
            updateStats(cfg);
            renderFeed(_episodes);

            // Handle URL parameter ?id=123
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
