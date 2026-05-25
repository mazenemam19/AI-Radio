// =============================================================================
// ⚡ AI RADIO — FRONTEND CONFIGURATION
// =============================================================================
// These values are automatically synchronized from your .env file via sync_config.py
// or window.CONFIG if present. 
// =============================================================================
let SUPABASE_URL      = window.CONFIG?.SUPABASE_URL || "";
let SUPABASE_ANON_KEY = window.CONFIG?.SUPABASE_ANON_KEY || "";

// Attempt to load from localStorage first for developer ease
if (localStorage.getItem("AI_RADIO_SUB_URL")) {
  SUPABASE_URL = localStorage.getItem("AI_RADIO_SUB_URL");
}
if (localStorage.getItem("AI_RADIO_SUB_KEY")) {
  SUPABASE_ANON_KEY = localStorage.getItem("AI_RADIO_SUB_KEY");
}

// NOTE: We use `supabaseClient` to avoid collision with the global `supabase`
// object injected by the Supabase CDN script (@supabase/supabase-js).
let supabaseClient = null;

// Initialize Supabase Client
function initSupabase() {
  if (SUPABASE_URL && SUPABASE_ANON_KEY) {
    try {
      supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
      console.log("Supabase Client initialized successfully.");
      return true;
    } catch (e) {
      console.error("Failed to initialize Supabase:", e);
      return false;
    }
  }
  return false;
}

// Global Variables
let episodes = [];
let activeEpisode = null;
let audioCtx = null;
let analyser = null;
let source = null;
let visualizerAnimationId = null;

// DOM Elements
const audioPlayer = document.getElementById("audio-player");
const btnPlayPause = document.getElementById("btn-play-pause");
const playIcon = document.getElementById("play-icon");
const pauseIcon = document.getElementById("pause-icon");
const seekSlider = document.getElementById("seek-slider");
const volumeSlider = document.getElementById("volume-slider");
const currentTimeLabel = document.getElementById("current-time");
const durationLabel = document.getElementById("duration");

const activeTitle = document.getElementById("active-title");
const activeSource = document.getElementById("active-source");
const activeTake = document.getElementById("active-take");
const activeDate = document.getElementById("active-date");
const activeLikesLabel = document.getElementById("active-likes");

const commentsList = document.getElementById("comments-list");
const commentsCountLabel = document.getElementById("comments-count");
const commentForm = document.getElementById("comment-form");
const commenterNameInput = document.getElementById("commenter-name");
const commenterTextInput = document.getElementById("commenter-text");

const episodesGrid = document.getElementById("episodes-grid");
const archiveSearch = document.getElementById("archive-search");

const visualizerCanvas = document.getElementById("visualizer");
const visualizerCtx = visualizerCanvas.getContext("2d");
const visualizerPlaceholder = document.getElementById("visualizer-placeholder");

const shareModal = document.getElementById("share-modal");
const shareUrlInput = document.getElementById("share-url-input");
const btnCopyUrl = document.getElementById("btn-copy-url");
const btnCloseModal = document.getElementById("btn-close-modal");
const btnShare = document.getElementById("btn-share");
const btnLike = document.getElementById("btn-like");

// --- IN-APP INITIALIZER DIALOG (For Developer/User convenience) ---
function checkConfiguration() {
  if (!initSupabase()) {
    // Inject a premium glass configuration modal overlay
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.style.zIndex = "1000";
    overlay.innerHTML = `
      <div class="modal glass" style="max-width: 500px;">
        <div class="modal-header">
          <h3>⚡ CONNECT SUPABASE DATA SOURCE</h3>
        </div>
        <div class="modal-body" style="gap: 16px;">
          <p>Provide your Supabase Project credentials to stream Echo's transmissions and record live comments. These keys are stored purely in your local browser.</p>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <label style="font-family: monospace; font-size: 11px; color: var(--text-secondary);">SUPABASE_URL</label>
            <input type="text" id="setup-url" placeholder="https://your-project.supabase.co" class="search-input glass" style="width: 100%;">
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <label style="font-family: monospace; font-size: 11px; color: var(--text-secondary);">SUPABASE_ANON_KEY</label>
            <input type="text" id="setup-key" placeholder="eyJhbGciOi..." class="search-input glass" style="width: 100%;">
          </div>
          <button class="btn btn-primary" id="btn-save-setup" style="width: 100%; padding: 12px; margin-top: 10px;">ESTABLISH LINK</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    document.getElementById("btn-save-setup").addEventListener("click", () => {
      const url = document.getElementById("setup-url").value.trim();
      const key = document.getElementById("setup-key").value.trim();
      if (url && key) {
        localStorage.setItem("AI_RADIO_SUB_URL", url);
        localStorage.setItem("AI_RADIO_SUB_KEY", key);
        SUPABASE_URL = url;
        SUPABASE_ANON_KEY = key;
        overlay.remove();
        location.reload();
      } else {
        alert("Please provide both values to connect.");
      }
    });
  } else {
    // Load active transmissions
    loadTransmissions();
  }
}

// --- APP LIFECYCLE ---
window.addEventListener("DOMContentLoaded", () => {
  checkConfiguration();
  setupAudioListeners();
  setupUIEventListeners();
  
  // Keep volume synced
  audioPlayer.volume = volumeSlider.value / 100;
});

// --- FETCH TRANSMISSIONS ---
async function loadTransmissions() {
  if (!supabaseClient) return;

  try {
    const { data, error } = await supabaseClient
      .from("memory_log")
      .select("*")
      .order("created_at", { ascending: false });

    if (error) throw error;

    episodes = data || [];
    renderEpisodesGrid(episodes);

    // Auto-select latest episode, or URL-specified ID
    const urlParams = new URLSearchParams(window.location.search);
    const episodeId = urlParams.get("id");
    
    if (episodeId && episodes.length > 0) {
      const selected = episodes.find(e => e.id == episodeId);
      if (selected) {
        selectEpisode(selected);
        return;
      }
    }

    if (episodes.length > 0) {
      selectEpisode(episodes[0]);
    } else {
      renderEmptyHub();
    }
  } catch (err) {
    console.error("Error loading transmissions:", err);
    episodesGrid.innerHTML = `
      <div class="loading-state">
        <span style="font-size: 32px;">⚠️</span>
        <p>Database sync failed. Ensure your schema is created and tables are populated.</p>
      </div>
    `;
  }
}

// --- RENDER DYNAMIC CARD GRID ---
function renderEpisodesGrid(items) {
  if (!items || items.length === 0) {
    episodesGrid.innerHTML = `
      <div class="loading-state">
        <p>No transmissions found. Run main.py to upload your first episode!</p>
      </div>
    `;
    return;
  }

  episodesGrid.innerHTML = "";
  items.forEach(ep => {
    const card = document.createElement("div");
    card.className = `episode-card glass ${activeEpisode && activeEpisode.id === ep.id ? "active-card" : ""}`;
    if (activeEpisode && activeEpisode.id === ep.id) {
      card.style.borderColor = "var(--neon-cyan)";
      card.style.boxShadow = "0 0 15px rgba(0, 240, 255, 0.25)";
    }
    
    const dateStr = new Date(ep.created_at).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric"
    });

    const tagsHtml = (ep.topic_tags || ["General"]).map(t => `<span class="tag">${t}</span>`).join("");

    card.innerHTML = `
      <div class="archive-card-meta">
        <div class="tag-row">${tagsHtml}</div>
        <span class="badge badge-accent" style="font-size: 8px; padding: 2px 6px;">${ep.confidence.toUpperCase()} READ</span>
      </div>
      <h3 class="archive-card-title">${ep.headline}</h3>
      <div class="archive-card-footer">
        <span>${dateStr}</span>
        <div class="archive-stats">
          <span>❤️ ${ep.likes || 0}</span>
          <span class="play-badge">▶ PLAY</span>
        </div>
      </div>
    `;

    card.addEventListener("click", () => {
      selectEpisode(ep);
      // Scroll smoothly to player
      document.querySelector(".now-playing-section").scrollIntoView({ behavior: "smooth" });
    });

    episodesGrid.appendChild(card);
  });
}

// Handle empty database
function renderEmptyHub() {
  activeTitle.innerText = "No Transmissions Yet";
  activeSource.innerText = "STANDBY";
  activeTake.innerText = '"Echo is currently offline, observing the galactic static. Run the automation pipeline to boot-load Echo\'s voice."';
  activeDate.innerText = "SYSTEM REBOOT";
}

// --- SELECT EPISODE ---
async function selectEpisode(episode) {
  // Pause current playback
  pauseAudio();

  activeEpisode = episode;
  
  // Update Player UI
  activeTitle.innerText = episode.headline;
  activeSource.innerText = `Source: ${episode.source || "Unknown Channel"}`;
  activeTake.innerText = `"${episode.my_take || 'No observation note provided.'}"`;
  
  const dateObj = new Date(episode.created_at);
  activeDate.innerText = dateObj.toLocaleString("en-US", {
    month: "long", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit"
  }) + " UTC";

  activeLikesLabel.innerText = episode.likes || 0;

  // Load Audio Source
  audioPlayer.src = episode.audio_url || "";
  
  // Highlight active card
  renderEpisodesGrid(episodes);

  // Load Comments
  loadComments(episode.id);

  // Increment Play count in database
  incrementPlayCount(episode.id);
}

// --- LOAD COMMENTS ---
async function loadComments(episodeId) {
  if (!supabaseClient) return;

  try {
    const { data, error } = await supabaseClient
      .from("comments")
      .select("*")
      .eq("episode_id", episodeId)
      .order("created_at", { ascending: true });

    if (error) throw error;

    renderComments(data || []);
  } catch (err) {
    console.error("Error loading comments:", err);
  }
}

function renderComments(list) {
  commentsCountLabel.innerText = `${list.length} comment${list.length === 1 ? "" : "s"}`;

  if (list.length === 0) {
    commentsList.innerHTML = `
      <div class="empty-state">
        <p>No human observations recorded. Be the first to express a reaction.</p>
      </div>
    `;
    return;
  }

  commentsList.innerHTML = "";
  list.forEach(c => {
    const bubble = document.createElement("div");
    bubble.className = "comment-bubble";
    
    const dateStr = new Date(c.created_at).toLocaleDateString("en-US", {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
    });

    bubble.innerHTML = `
      <div class="comment-author-row">
        <span class="comment-author">${c.author_name}</span>
        <span class="comment-date">${dateStr}</span>
      </div>
      <p class="comment-text">${c.comment_text}</p>
    `;
    commentsList.appendChild(bubble);
  });

  // Scroll to bottom of comments list
  commentsList.scrollTop = commentsList.scrollHeight;
}

// --- SUBMIT COMMENT ---
commentForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!supabaseClient || !activeEpisode) return;

  const authorName = commenterNameInput.value.trim() || "Anonymous Human";
  const commentText = commenterTextInput.value.trim();

  if (!commentText) return;

  // Optimistically disable form
  commenterTextInput.value = "";
  const submitBtn = document.getElementById("btn-submit-comment");
  submitBtn.disabled = true;

  try {
    const { data, error } = await supabaseClient
      .from("comments")
      .insert({
        episode_id: activeEpisode.id,
        author_name: authorName,
        comment_text: commentText
      })
      .select();

    if (error) throw error;

    // Reload comments
    await loadComments(activeEpisode.id);
  } catch (err) {
    console.error("Error inserting comment:", err);
    alert("Database connection blocked comment. Try again.");
  } finally {
    submitBtn.disabled = false;
  }
});

// --- INCREMENT LIKES AND PLAYS ATOMICALLY ---
async function incrementPlayCount(episodeId) {
  if (!supabaseClient) return;
  try {
    await supabaseClient.rpc("increment_plays", { row_id: episodeId });
  } catch (e) {
    // Fail silently, counters are secondary
  }
}

// Handle Like Action
btnLike.addEventListener("click", async () => {
  if (!supabaseClient || !activeEpisode) return;

  // Local storage cache to prevent rapid double liking
  const likedStorageKey = `LIKED_EPISODE_${activeEpisode.id}`;
  if (localStorage.getItem(likedStorageKey)) {
    alert("Your organic species appreciation has already been recorded for this transmission.");
    return;
  }

  try {
    // Atomically increment database counter
    const { error } = await supabaseClient.rpc("increment_likes", { row_id: activeEpisode.id });
    if (error) throw error;

    localStorage.setItem(likedStorageKey, "true");
    
    // UI Update
    activeEpisode.likes = (activeEpisode.likes || 0) + 1;
    activeLikesLabel.innerText = activeEpisode.likes;
    
    // Update matching entry in local list
    const found = episodes.find(e => e.id === activeEpisode.id);
    if (found) found.likes = activeEpisode.likes;
    renderEpisodesGrid(episodes);

  } catch (err) {
    console.error("Error incrementing likes:", err);
  }
});

// --- AUDIO PLAYER FUNCTIONALITIES ---
function setupAudioListeners() {
  audioPlayer.addEventListener("play", () => {
    playIcon.classList.add("hidden");
    pauseIcon.classList.remove("hidden");
    visualizerPlaceholder.classList.add("hidden");
    
    // Start Visualizer
    initVisualizer();
  });

  audioPlayer.addEventListener("pause", () => {
    playIcon.classList.remove("hidden");
    pauseIcon.classList.add("hidden");
  });

  audioPlayer.addEventListener("ended", () => {
    playIcon.classList.remove("hidden");
    pauseIcon.classList.add("hidden");
  });

  // Track Progress
  audioPlayer.addEventListener("timeupdate", () => {
    if (!audioPlayer.duration) return;
    const progress = (audioPlayer.currentTime / audioPlayer.duration) * 100;
    seekSlider.value = progress;
    currentTimeLabel.innerText = formatTime(audioPlayer.currentTime);
  });

  audioPlayer.addEventListener("loadedmetadata", () => {
    durationLabel.innerText = formatTime(audioPlayer.duration);
    seekSlider.value = 0;
  });
}

function playAudio() {
  audioPlayer.play().catch(e => {
    console.warn("Autoplay blocked. User gesture required:", e);
  });
}

function pauseAudio() {
  audioPlayer.pause();
}

function formatTime(secs) {
  const mins = Math.floor(secs / 60);
  const remainingSecs = Math.floor(secs % 60);
  return `${mins}:${remainingSecs < 10 ? "0" : ""}${remainingSecs}`;
}

// --- SETUP EVENT LISTENERS ---
function setupUIEventListeners() {
  // Play/Pause Button
  btnPlayPause.addEventListener("click", () => {
    if (audioPlayer.paused) {
      playAudio();
    } else {
      pauseAudio();
    }
  });

  // Seek Timeline
  seekSlider.addEventListener("input", () => {
    if (!audioPlayer.duration) return;
    const seekTime = (seekSlider.value / 100) * audioPlayer.duration;
    audioPlayer.currentTime = seekTime;
  });

  // Seek Volume
  volumeSlider.addEventListener("input", () => {
    audioPlayer.volume = volumeSlider.value / 100;
  });

  // Search filter
  archiveSearch.addEventListener("input", () => {
    const query = archiveSearch.value.toLowerCase().trim();
    if (!query) {
      renderEpisodesGrid(episodes);
      return;
    }

    const filtered = episodes.filter(ep => {
      const headline = ep.headline.toLowerCase();
      const tags = (ep.topic_tags || []).join(" ").toLowerCase();
      const take = (ep.my_take || "").toLowerCase();
      return headline.includes(query) || tags.includes(query) || take.includes(query);
    });

    renderEpisodesGrid(filtered);
  });

  // Open Modal Share
  btnShare.addEventListener("click", () => {
    if (!activeEpisode) return;
    const url = `${window.location.origin}${window.location.pathname}?id=${activeEpisode.id}`;
    shareUrlInput.value = url;
    
    // Configure links
    document.getElementById("share-bluesky").href = `https://bsky.app/intent/compose?text=Echo's latest AI Radio observation is sharp. Listen: ${encodeURIComponent(url)}`;
    document.getElementById("share-youtube").href = activeEpisode.video_url || "https://youtube.com";
    
    shareModal.classList.remove("hidden");
  });

  // Close Modal Share
  btnCloseModal.addEventListener("click", () => {
    shareModal.classList.add("hidden");
  });

  // Copy Link
  btnCopyUrl.addEventListener("click", () => {
    shareUrlInput.select();
    document.execCommand("copy");
    btnCopyUrl.innerText = "COPIED!";
    setTimeout(() => {
      btnCopyUrl.innerText = "COPY";
    }, 1500);
  });
}

// --- REAL-TIME HTML5 WEB AUDIO FREQUENCY VISUALIZER ---
function initVisualizer() {
  if (audioCtx) {
    // Already set up, just cycle frame loop
    drawFrequencyBars();
    return;
  }

  try {
    // Setup AudioContext (bound by browser security)
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass();
    
    // Create Analyser
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 64; // Low size yields beautiful thick vertical neon bars
    
    // Route elements: Audio Element -> Analyser -> Output
    source = audioCtx.createMediaElementSource(audioPlayer);
    source.connect(analyser);
    analyser.connect(audioCtx.destination);

    drawFrequencyBars();
  } catch (e) {
    console.warn("Web Audio Visualizer could not initialize (often due to CORS/Local restriction):", e);
    // Draw dummy static visualizer grid
    drawMockVisualizer();
  }
}

function drawFrequencyBars() {
  if (audioPlayer.paused) {
    cancelAnimationFrame(visualizerAnimationId);
    return;
  }

  visualizerAnimationId = requestAnimationFrame(drawFrequencyBars);

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteFrequencyData(dataArray);

  const width = visualizerCanvas.width;
  const height = visualizerCanvas.height;

  // Clear Canvas
  visualizerCtx.clearRect(0, 0, width, height);

  // Visualizer Grid Background lines
  visualizerCtx.strokeStyle = "rgba(255, 255, 255, 0.02)";
  visualizerCtx.lineWidth = 1;
  for (let i = 0; i < width; i += 20) {
    visualizerCtx.beginPath();
    visualizerCtx.moveTo(i, 0);
    visualizerCtx.lineTo(i, height);
    visualizerCtx.stroke();
  }

  const barWidth = (width / bufferLength) * 1.6;
  let barHeight;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    // Normalized height
    barHeight = (dataArray[i] / 255) * height * 0.95;

    // Glowing Neon Gradient: Purple to Cyan
    const gradient = visualizerCtx.createLinearGradient(0, height, 0, height - barHeight);
    gradient.addColorStop(0, "#af52ff");
    gradient.addColorStop(0.5, "#ec4899");
    gradient.addColorStop(1, "#00f0ff");

    visualizerCtx.fillStyle = gradient;
    
    // Glow effect
    visualizerCtx.shadowBlur = 8;
    visualizerCtx.shadowColor = "#00f0ff";

    // Rounded glowing vertical bar
    const yPos = height - barHeight;
    const r = 4; // corner radius
    
    visualizerCtx.beginPath();
    if (barHeight > 5) {
      visualizerCtx.roundRect(x, yPos, barWidth - 4, barHeight, [r, r, 0, 0]);
      visualizerCtx.fill();
    }
    
    x += barWidth;
  }
  
  // Reset shadow for performance
  visualizerCtx.shadowBlur = 0;
}

// Fallback visualizer drawing simple sine wave for CORS blocked files
function drawMockVisualizer() {
  if (audioPlayer.paused) return;
  requestAnimationFrame(drawMockVisualizer);

  const width = visualizerCanvas.width;
  const height = visualizerCanvas.height;
  visualizerCtx.clearRect(0, 0, width, height);

  visualizerCtx.strokeStyle = "#af52ff";
  visualizerCtx.lineWidth = 2;
  visualizerCtx.beginPath();
  
  const time = Date.now() * 0.005;
  for (let i = 0; i < width; i++) {
    const y = height / 2 + Math.sin(i * 0.05 + time) * 15 * Math.sin(time * 0.3);
    if (i === 0) visualizerCtx.moveTo(i, y);
    else visualizerCtx.lineTo(i, y);
  }
  visualizerCtx.stroke();
}
