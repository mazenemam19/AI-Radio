/**
 * AI Radio — Echo Frontend
 * Hybrid Player (YouTube + Local MP4 Support)
 */

// --- 1. GLOBAL STATE ---
let episodes = [];
let activeEpisode = null;
let ytPlayer = null; 
let visualizerAnimationId = null;
let supabaseClient = null;
let ytPlayerReady = false;
let CURRENT_ENV = "production";
let SUB_URL = "";
let SUB_KEY = "";

// --- 2. DOM ELEMENTS ---
const elements = {
  activeTitle: document.getElementById("active-title"),
  activeSource: document.getElementById("active-source"),
  activeTake: document.getElementById("active-take"),
  activeDate: document.getElementById("active-date"),
  activeLikes: document.getElementById("active-likes"),
  btnLike: document.getElementById("btn-like"),
  btnPlayPause: document.getElementById("btn-play-pause"),
  playIcon: document.getElementById("play-icon"),
  pauseIcon: document.getElementById("pause-icon"),
  visualizer: document.getElementById("visualizer"),
  visualizerPlaceholder: document.getElementById("visualizer-placeholder"),
  episodesGrid: document.getElementById("episodes-grid"),
  archiveSearch: document.getElementById("archive-search"),
  commentsList: document.getElementById("comments-list"),
  commentsCount: document.getElementById("comments-count"),
  commentForm: document.getElementById("comment-form"),
  commenterName: document.getElementById("commenter-name"),
  commenterText: document.getElementById("commenter-text"),
  localPlayer: document.getElementById("local-video-player"),
  ytFrame: document.getElementById("yt-player-frame"),
  ytContainer: document.getElementById("yt-container")
};

// --- 3. INITIALIZATION ---

function initApp() {
  CURRENT_ENV = window.CONFIG?.APP_ENV || "production";
  SUB_URL = window.CONFIG?.SUPABASE_URL || "";
  SUB_KEY = window.CONFIG?.SUPABASE_ANON_KEY || "";

  if (localStorage.getItem("AI_RADIO_SUB_URL")) SUB_URL = localStorage.getItem("AI_RADIO_SUB_URL");
  if (localStorage.getItem("AI_RADIO_SUB_KEY")) SUB_KEY = localStorage.getItem("AI_RADIO_SUB_KEY");

  console.log(`[Echo] --- INITIALIZING HYBRID APP ---`);
  console.log(`[Echo] Mode: ${CURRENT_ENV.toUpperCase()}`);
  
  if (CURRENT_ENV === "local") {
    loadTransmissions();
    setupUIEventListeners();
  } else {
    if (connectSupabase()) {
      loadTransmissions();
      setupUIEventListeners();
    } else {
      showConfigModal();
    }
  }
}

function connectSupabase() {
  if (SUB_URL && SUB_KEY) {
    try {
      supabaseClient = window.supabase.createClient(SUB_URL, SUB_KEY);
      return true;
    } catch (e) { return false; }
  }
  return false;
}

function showConfigModal() {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `<div class="modal glass"><h3>⚡ CONNECT SUPABASE</h3><p>Required for ${CURRENT_ENV} mode.</p><input type="text" id="setup-url" placeholder="URL" class="search-input glass" style="width:100%; margin-bottom:10px;"><input type="text" id="setup-key" placeholder="Key" class="search-input glass" style="width:100%; margin-bottom:20px;"><button class="btn btn-primary" id="btn-save-setup" style="width:100%">CONNECT</button></div>`;
  document.body.appendChild(overlay);
  document.getElementById("btn-save-setup").addEventListener("click", () => {
    localStorage.setItem("AI_RADIO_SUB_URL", document.getElementById("setup-url").value.trim());
    localStorage.setItem("AI_RADIO_SUB_KEY", document.getElementById("setup-key").value.trim());
    location.reload();
  });
}

// --- 4. DATA LOADING ---

async function loadTransmissions() {
  console.log(`[Echo] Attempting to load transmissions. Env: ${CURRENT_ENV}`);

  if (CURRENT_ENV === "local") {
    console.log("[Echo] Data sync complete.");
    episodes = window.CONFIG?.LOCAL_DATA || [];
    
    // Path Translation
    episodes = episodes.map(ep => ({
      ...ep,
      audio_url: ep.audio_url?.replace("local://", "output/").replace("https://mock-audio-link.com/", "output/"),
      video_url: ep.video_url?.replace("local://", "output/").replace("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    }));
  } else {
    try {
      const { data, error } = await supabaseClient.from("memory_log").select("*").order("created_at", { ascending: false });
      if (error) throw error;
      episodes = data || [];
    } catch (err) {
      elements.episodesGrid.innerHTML = `<div class="loading-state">⚠️ Sync failed.</div>`;
      return;
    }
  }

  renderEpisodesGrid(episodes);
  if (episodes.length > 0) {
    const urlId = new URLSearchParams(window.location.search).get("id");
    selectEpisode(episodes.find(e => e.id == urlId) || episodes[0]);
  } else {
    elements.activeTitle.innerText = "No Transmissions Found";
  }
}

// --- 5. UI LOGIC ---

function selectEpisode(episode) {
  activeEpisode = episode;
  elements.activeTitle.innerText = episode.headline;
  elements.activeSource.innerText = `Source: ${episode.source || "Unknown"}`;
  elements.activeTake.innerText = `"${episode.my_take || 'Static observed.'}"`;
  elements.activeDate.innerText = new Date(episode.created_at).toLocaleDateString();
  elements.activeLikes.innerText = episode.likes || 0;

  const isLocalFile = episode.video_url?.includes("output/") || episode.audio_url?.includes("output/");

  if (isLocalFile) {
    console.log("[Echo] Switching to Local HTML5 Player.");
    elements.ytFrame.classList.add("hidden");
    elements.localPlayer.classList.remove("hidden");
    
    let playSource = episode.video_url;
    if (playSource.includes("youtube.com") || playSource.includes("dQw4w9WgXcQ")) {
       const filename = episode.audio_url.split("/").pop().replace(".mp3", ".mp4");
       playSource = "output/" + filename;
    }

    elements.localPlayer.src = playSource;
    elements.localPlayer.load();
    
    elements.localPlayer.onplay = () => {
      elements.playIcon.classList.add("hidden");
      elements.pauseIcon.classList.remove("hidden");
      elements.visualizerPlaceholder.classList.add("hidden");
      startNeuralPulse();
    };
    elements.localPlayer.onpause = () => {
      elements.playIcon.classList.remove("hidden");
      elements.pauseIcon.classList.add("hidden");
      stopNeuralPulse();
    };
  } else {
    console.log("[Echo] Switching to YouTube IFrame Player.");
    elements.localPlayer.classList.add("hidden");
    elements.ytFrame.classList.remove("hidden");
    elements.localPlayer.pause();
    
    if (ytPlayer && episode.video_url) {
      if (ytPlayerReady) {
        const videoId = extractVideoId(episode.video_url);
        if (videoId) {
          console.log(`[Echo] Loading YouTube ID: ${videoId}`);
          ytPlayer.cueVideoById(videoId);
        }
      } else {
        console.log("[Echo] YouTube Player instance exists but methods are not ready yet. Deferring cue.");
      }
    }
  }
  
  renderEpisodesGrid(episodes);
  loadComments(episode.id);
  incrementPlayCount(episode.id);
}

function extractVideoId(url) {
  const match = url.match(/^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/);
  return (match && match[2].length === 11) ? match[2] : null;
}

function renderEpisodesGrid(items) {
  elements.episodesGrid.innerHTML = "";
  items.forEach(ep => {
    const card = document.createElement("div");
    card.className = `episode-card glass ${activeEpisode?.id === ep.id ? "active-card" : ""}`;
    card.innerHTML = `
      <div class="archive-card-meta"><div class="tag-row">${(ep.topic_tags || ["General"]).map(t=>`<span class="tag">${t}</span>`).join("")}</div></div>
      <h3 class="archive-card-title">${ep.headline}</h3>
      <div class="archive-card-footer"><span>${new Date(ep.created_at).toLocaleDateString()}</span><span class="play-badge">▶ PLAY</span></div>
    `;
    card.addEventListener("click", () => {
      selectEpisode(ep);
      document.querySelector(".now-playing-section").scrollIntoView({ behavior: "smooth" });
    });
    elements.episodesGrid.appendChild(card);
  });
}

function startNeuralPulse() {
  if (visualizerAnimationId) cancelAnimationFrame(visualizerAnimationId);
  function draw() {
    visualizerAnimationId = requestAnimationFrame(draw);
    const ctx = elements.visualizer.getContext("2d");
    const { width, height } = elements.visualizer;
    ctx.clearRect(0, 0, width, height);
    const time = Date.now() * 0.002;
    const bars = 32;
    const barW = (width / bars) * 1.5;
    for (let i = 0; i < bars; i++) {
      const h = (Math.abs(Math.sin(i * 0.5 + time) * Math.cos(i * 0.2 - time * 0.5)) * height * 0.8) + 10;
      const grad = ctx.createLinearGradient(0, height, 0, height - h);
      grad.addColorStop(0, "#af52ff"); grad.addColorStop(1, "#00f0ff");
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.roundRect(i * barW, height - h, barW - 4, h, [4, 4, 0, 0]); ctx.fill();
    }
  }
  draw();
}

function stopNeuralPulse() {
  cancelAnimationFrame(visualizerAnimationId);
  visualizerAnimationId = null;
}

// --- 6. YOUTUBE API ---
window.onYouTubeIframeAPIReady = function () {
  if (CURRENT_ENV === "local") return;
  const currentOrigin = window.location.origin;
  console.log(`[Echo] YouTube API Ready. Origin: ${currentOrigin}`);

  ytPlayer = new YT.Player('yt-player-frame', {
    height: '100%', width: '100%', videoId: '',
    playerVars: {
      'autoplay': 0,
      'modestbranding': 1,
      'origin': currentOrigin,
      'enablejsapi': 1
    },
    events: {
      'onReady': () => {
        ytPlayerReady = true;
        console.log("[Echo] YouTube Player API Methods Fully Loaded.");

        elements.ytFrame = document.getElementById('yt-player-frame');

        if (activeEpisode && activeEpisode.video_url) {
          const isLocalFile = activeEpisode.video_url?.includes("output/") || activeEpisode.audio_url?.includes("output/");
          const videoId = extractVideoId(activeEpisode.video_url);
          if (videoId && !isLocalFile) {
            console.log(`[Echo] Executing deferred cue for YouTube ID: ${videoId}`);
            ytPlayer.cueVideoById(videoId);
          }
        }
      },
      'onStateChange': (e) => {
        if (e.data === YT.PlayerState.PLAYING) {
          elements.playIcon.classList.add("hidden"); elements.pauseIcon.classList.remove("hidden");
          elements.visualizerPlaceholder.classList.add("hidden"); startNeuralPulse();
        } else {
          elements.playIcon.classList.remove("hidden"); elements.pauseIcon.classList.add("hidden");
          stopNeuralPulse();
        }
      }
    }
  });
};

// --- 7. EVENT LISTENERS ---
function setupUIEventListeners() {
  elements.btnPlayPause.addEventListener("click", () => {
    const isLocalFile = activeEpisode?.video_url?.includes("output/") || activeEpisode?.audio_url?.includes("output/");
    if (isLocalFile) {
      elements.localPlayer.paused ? elements.localPlayer.play() : elements.localPlayer.pause();
    } else {
      if (!ytPlayer || !ytPlayerReady) return;
      ytPlayer.getPlayerState() === YT.PlayerState.PLAYING ? ytPlayer.pauseVideo() : ytPlayer.playVideo();
    }
  });

  elements.archiveSearch.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase().trim();
    renderEpisodesGrid(q ? episodes.filter(ep => ep.headline.toLowerCase().includes(q)) : episodes);
  });

  elements.btnLike.addEventListener("click", () => {
    if (!activeEpisode) return;
    incrementLikeCount(activeEpisode.id);
  });

  elements.commentForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (CURRENT_ENV === "local") return alert("Comments disabled in Local Offline mode.");
    const text = elements.commenterText.value.trim();
    if (!text || !supabaseClient) return;
    try {
      await supabaseClient.from("comments").insert({ episode_id: activeEpisode.id, author_name: elements.commenterName.value.trim() || "Human", comment_text: text });
      elements.commenterText.value = ""; loadComments(activeEpisode.id);
    } catch (err) { alert("Comment failed."); }
  });
}

async function loadComments(id) {
  if (CURRENT_ENV === "local" || !supabaseClient) return elements.commentsList.innerHTML = "<p>Comments restricted locally.</p>";
  const { data } = await supabaseClient.from("comments").select("*").eq("episode_id", id).order("created_at", { ascending: true });
  elements.commentsCount.innerText = `${data?.length || 0} comments`;
  elements.commentsList.innerHTML = (data || []).map(c => `<div class="comment-bubble"><span class="comment-author">${c.author_name}</span><p class="comment-text">${c.comment_text}</p></div>`).join("");
}

async function incrementPlayCount(id) {
  if (CURRENT_ENV !== "local" && supabaseClient) {
    await supabaseClient.rpc("increment_plays", { row_id: id });
  } else if (CURRENT_ENV === "local") {
    try {
      await fetch("/api/play", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row_id: id })
      });
    } catch (e) { console.warn("[Echo] Local play sync failed."); }
  }
}

async function incrementLikeCount(id) {
  // Optimistic UI
  const currentLikes = parseInt(elements.activeLikes.innerText) || 0;
  elements.activeLikes.innerText = currentLikes + 1;
  
  if (CURRENT_ENV !== "local" && supabaseClient) {
    try {
      await supabaseClient.rpc("increment_likes", { row_id: id });
    } catch (e) {
      console.error("[Echo] Like failed:", e);
      elements.activeLikes.innerText = currentLikes; // Revert on failure
    }
  } else if (CURRENT_ENV === "local") {
    try {
      const response = await fetch("/api/like", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ row_id: id })
      });
      if (!response.ok) throw new Error("Local update failed");
    } catch (e) {
      console.error("[Echo] Local like failed:", e);
      elements.activeLikes.innerText = currentLikes; // Revert on failure
    }
  }
}

// --- 8. BOOTSTRAP ---
initApp();
