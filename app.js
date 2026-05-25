// Global Variables
let episodes = [];
let activeEpisode = null;
let ytPlayer = null; 
let visualizerAnimationId = null;

// DOM Elements
const activeTitle = document.getElementById("active-title");
const activeSource = document.getElementById("active-source");
const activeTake = document.getElementById("active-take");
const activeDate = document.getElementById("active-date");
const activeLikesLabel = document.getElementById("active-likes");

const btnPlayPause = document.getElementById("btn-play-pause");
const playIcon = document.getElementById("play-icon");
const pauseIcon = document.getElementById("pause-icon");

const visualizerCanvas = document.getElementById("visualizer");
const visualizerCtx = visualizerCanvas.getContext("2d");
const visualizerPlaceholder = document.getElementById("visualizer-placeholder");

// --- YOUTUBE IFRAME API SETUP ---
window.onYouTubeIframeAPIReady = function() {
  ytPlayer = new YT.Player('yt-player-frame', {
    height: '100%',
    width: '100%',
    videoId: '', 
    playerVars: {
      'autoplay': 0,
      'controls': 1,
      'modestbranding': 1,
      'rel': 0
    },
    events: {
      'onStateChange': onPlayerStateChange
    }
  });
};

function onPlayerStateChange(event) {
  if (event.data === YT.PlayerState.PLAYING) {
    playIcon.classList.add("hidden");
    pauseIcon.classList.remove("hidden");
    visualizerPlaceholder.classList.add("hidden");
    startNeuralPulse();
  } else {
    playIcon.classList.remove("hidden");
    pauseIcon.classList.add("hidden");
    stopNeuralPulse();
  }
}

// --- SELECT EPISODE ---
async function selectEpisode(episode) {
  activeEpisode = episode;
  
  // Update UI
  activeTitle.innerText = episode.headline;
  activeSource.innerText = `Source: ${episode.source || "Unknown Channel"}`;
  activeTake.innerText = `"${episode.my_take || 'No observation note provided.'}"`;
  
  const dateObj = new Date(episode.created_at);
  activeDate.innerText = dateObj.toLocaleString("en-US", {
    month: "long", day: "numeric", year: "numeric"
  });

  activeLikesLabel.innerText = episode.likes || 0;

  // Load Video into YouTube Player
  if (ytPlayer && episode.video_url) {
    const videoId = extractVideoId(episode.video_url);
    if (videoId) {
      ytPlayer.cueVideoById(videoId);
    }
  }
  
  renderEpisodesGrid(episodes);
  loadComments(episode.id);
  incrementPlayCount(episode.id);
}

function extractVideoId(url) {
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
  const match = url.match(regExp);
  return (match && match[2].length === 11) ? match[2] : null;
}

// --- NEURAL PULSE VISUALIZER (Procedural Simulation) ---
function startNeuralPulse() {
  if (visualizerAnimationId) cancelAnimationFrame(visualizerAnimationId);
  drawPulse();
}

function stopNeuralPulse() {
  cancelAnimationFrame(visualizerAnimationId);
  visualizerAnimationId = null;
}

function drawPulse() {
  visualizerAnimationId = requestAnimationFrame(drawPulse);
  
  const width = visualizerCanvas.width;
  const height = visualizerCanvas.height;
  visualizerCtx.clearRect(0, 0, width, height);

  const time = Date.now() * 0.002;
  const bars = 32;
  const barWidth = (width / bars) * 1.5;

  for (let i = 0; i < bars; i++) {
    const noise = Math.sin(i * 0.5 + time) * Math.cos(i * 0.2 - time * 0.5);
    const barHeight = Math.abs(noise) * height * 0.8 + 10;
    const x = i * barWidth;
    const gradient = visualizerCtx.createLinearGradient(0, height, 0, height - barHeight);
    gradient.addColorStop(0, "#af52ff");
    gradient.addColorStop(1, "#00f0ff");
    visualizerCtx.fillStyle = gradient;
    visualizerCtx.shadowBlur = 10;
    visualizerCtx.shadowColor = "#00f0ff";
    visualizerCtx.beginPath();
    visualizerCtx.roundRect(x, height - barHeight, barWidth - 4, barHeight, [4, 4, 0, 0]);
    visualizerCtx.fill();
  }
}

// --- APP LIFECYCLE ---
window.addEventListener("DOMContentLoaded", () => {
  checkConfiguration();
  setupUIEventListeners();
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
    const urlParams = new URLSearchParams(window.location.search);
    const episodeId = urlParams.get("id");
    if (episodeId && episodes.length > 0) {
      const selected = episodes.find(e => e.id == episodeId);
      if (selected) { selectEpisode(selected); return; }
    }
    if (episodes.length > 0) selectEpisode(episodes[0]);
    else renderEmptyHub();
  } catch (err) {
    console.error("Error loading transmissions:", err);
  }
}

// --- RENDER DYNAMIC CARD GRID ---
function renderEpisodesGrid(items) {
  if (!items || items.length === 0) {
    episodesGrid.innerHTML = `<div class="loading-state"><p>No transmissions found.</p></div>`;
    return;
  }
  episodesGrid.innerHTML = "";
  items.forEach(ep => {
    const card = document.createElement("div");
    card.className = `episode-card glass ${activeEpisode && activeEpisode.id === ep.id ? "active-card" : ""}`;
    const dateStr = new Date(ep.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    const tagsHtml = (ep.topic_tags || ["General"]).map(t => `<span class="tag">${t}</span>`).join("");
    card.innerHTML = `
      <div class="archive-card-meta"><div class="tag-row">${tagsHtml}</div></div>
      <h3 class="archive-card-title">${ep.headline}</h3>
      <div class="archive-card-footer"><span>${dateStr}</span><span class="play-badge">▶ PLAY</span></div>
    `;
    card.addEventListener("click", () => {
      selectEpisode(ep);
      document.querySelector(".now-playing-section").scrollIntoView({ behavior: "smooth" });
    });
    episodesGrid.appendChild(card);
  });
}

function renderEmptyHub() {
  activeTitle.innerText = "No Transmissions Yet";
  activeTake.innerText = '"Echo is currently offline."';
}

// --- SETUP EVENT LISTENERS ---
function setupUIEventListeners() {
  btnPlayPause.addEventListener("click", () => {
    if (!ytPlayer) return;
    const state = ytPlayer.getPlayerState();
    if (state === YT.PlayerState.PLAYING) ytPlayer.pauseVideo();
    else ytPlayer.playVideo();
  });

  archiveSearch.addEventListener("input", () => {
    const query = archiveSearch.value.toLowerCase().trim();
    if (!query) { renderEpisodesGrid(episodes); return; }
    const filtered = episodes.filter(ep => ep.headline.toLowerCase().includes(query));
    renderEpisodesGrid(filtered);
  });
}

// --- CONFIGURATION MANAGEMENT ---
let SUPABASE_URL = window.CONFIG?.SUPABASE_URL || "";
let SUPABASE_ANON_KEY = window.CONFIG?.SUPABASE_ANON_KEY || "";
if (localStorage.getItem("AI_RADIO_SUB_URL")) SUPABASE_URL = localStorage.getItem("AI_RADIO_SUB_URL");
if (localStorage.getItem("AI_RADIO_SUB_KEY")) SUPABASE_ANON_KEY = localStorage.getItem("AI_RADIO_SUB_KEY");
let supabaseClient = null;

function initSupabase() {
  if (SUPABASE_URL && SUPABASE_ANON_KEY) {
    try {
      supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
      return true;
    } catch (e) { return false; }
  }
  return false;
}

function checkConfiguration() {
  if (!initSupabase()) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `<div class="modal glass"><h3>⚡ CONNECT SUPABASE</h3><input type="text" id="setup-url" placeholder="URL"><input type="text" id="setup-key" placeholder="Anon Key"><button id="btn-save-setup">CONNECT</button></div>`;
    document.body.appendChild(overlay);
    document.getElementById("btn-save-setup").addEventListener("click", () => {
      localStorage.setItem("AI_RADIO_SUB_URL", document.getElementById("setup-url").value.trim());
      localStorage.setItem("AI_RADIO_SUB_KEY", document.getElementById("setup-key").value.trim());
      location.reload();
    });
  } else { loadTransmissions(); }
}

// DOM Elements
const commentsList = document.getElementById("comments-list");
const commentsCountLabel = document.getElementById("comments-count");
const commentForm = document.getElementById("comment-form");
const commenterNameInput = document.getElementById("commenter-name");
const commenterTextInput = document.getElementById("commenter-text");
const episodesGrid = document.getElementById("episodes-grid");
const archiveSearch = document.getElementById("archive-search");

// --- LOAD COMMENTS ---
async function loadComments(episodeId) {
  if (!supabaseClient) return;
  try {
    const { data, error } = await supabaseClient.from("comments").select("*").eq("episode_id", episodeId).order("created_at", { ascending: true });
    if (error) throw error;
    renderComments(data || []);
  } catch (err) {}
}

function renderComments(list) {
  commentsCountLabel.innerText = `${list.length} comments`;
  commentsList.innerHTML = list.length === 0 ? "<p>No comments.</p>" : "";
  list.forEach(c => {
    const bubble = document.createElement("div");
    bubble.className = "comment-bubble";
    bubble.innerHTML = `<span class="comment-author">${c.author_name}</span><p class="comment-text">${c.comment_text}</p>`;
    commentsList.appendChild(bubble);
  });
}

async function incrementPlayCount(episodeId) {
  if (supabaseClient) await supabaseClient.rpc("increment_plays", { row_id: episodeId });
}
