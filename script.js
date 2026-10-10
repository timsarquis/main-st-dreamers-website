const SPOTIFY_SHOW = "spotify:show:0kGpjoeXh3ykY0ItzQsVod";
const podcast = document.querySelector(".spotify-podcast");
const previewEpisodeId = podcast.dataset.previewEpisodeId;
const previewUri = /^[A-Za-z0-9]+$/.test(previewEpisodeId || "")
  ? `spotify:episode:${previewEpisodeId}` : SPOTIFY_SHOW;
const playerContainer = document.querySelector("#spotify-featured-player");
const episodeList = document.querySelector("#spotify-episode-list");
const listStatus = document.querySelector("#spotify-list-status");
const retryButton = document.querySelector("#spotify-retry");
let controller = null;
let episodes = [];
let selectedId = null;
let engaged = false;
let pendingPlay = false;
let refreshing = false;

function markSelected() {
  episodeList.querySelectorAll("button").forEach((button) => {
    const selected = button.dataset.episodeId === selectedId;
    if (selected) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  });
}

function selectEpisode(episode, play = false) {
  selectedId = episode.id;
  if (play) engaged = true;
  document.querySelector("#spotify-playing-title").textContent = episode.title;
  document.querySelector("#spotify-playing-label").textContent =
    episode.id === episodes[0]?.id ? "Latest episode" : "Selected episode";
  document.querySelector("#spotify-featured-link").href = episode.url;
  markSelected();
  if (controller) {
    controller.loadEntity(episode.uri, true);
    if (play) controller.play();
  } else {
    pendingPlay = play;
    const fallback = playerContainer.querySelector("iframe");
    if (fallback) fallback.src = `https://open.spotify.com/embed/episode/${episode.id}`;
  }
}

function renderEpisodes() {
  const fragment = document.createDocumentFragment();
  episodes.forEach((episode, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "spotify-episode-button";
    button.dataset.episodeId = episode.id;
    button.setAttribute("aria-label", `Play ${episode.title}`);
    const playIcon = document.createElement("span");
    playIcon.className = "spotify-episode-play";
    playIcon.setAttribute("aria-hidden", "true");
    playIcon.textContent = "▶";
    const copy = document.createElement("span");
    const title = document.createElement("span");
    title.className = "spotify-episode-name";
    title.textContent = episode.title;
    const meta = document.createElement("span");
    meta.className = "spotify-episode-meta";
    const date = new Date(`${episode.releaseDate.slice(0, 10)}T12:00:00`);
    const formattedDate = Number.isNaN(date.getTime()) ? episode.releaseDate :
      new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);
    meta.textContent = [formattedDate, episode.durationMs ? `${Math.ceil(episode.durationMs / 60000)} min` : ""].filter(Boolean).join(" · ");
    copy.append(title, meta);
    const label = document.createElement("span");
    label.className = "spotify-episode-label";
    label.textContent = index === 0 ? "Newest" : "";
    button.append(playIcon, copy, label);
    button.addEventListener("click", () => selectEpisode(episode, true));
    item.append(button);
    fragment.append(item);
  });
  episodeList.replaceChildren(fragment);
  markSelected();
}

async function refreshEpisodes() {
  if (refreshing) return;
  refreshing = true;
  retryButton.hidden = true;
  if (!episodes.length) listStatus.textContent = "Getting the latest episodes…";
  try {
    if (location.protocol === "file:") throw new Error("The episode service needs an HTTP preview.");
    const response = await fetch(podcast.dataset.episodesUrl, { cache: "no-store", signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error("Episode service unavailable.");
    const data = await response.json();
    if (!Array.isArray(data.episodes)) throw new Error("Invalid episode list.");
    const nextEpisodes = data.episodes.filter((episode) =>
      /^[A-Za-z0-9]+$/.test(episode.id) && typeof episode.title === "string" &&
      episode.uri === `spotify:episode:${episode.id}` &&
      episode.url === `https://open.spotify.com/episode/${episode.id}`,
    ).sort((a, b) => b.releaseDate.localeCompare(a.releaseDate));
    if (!nextEpisodes.length) throw new Error("No episodes available.");
    const changed = JSON.stringify(nextEpisodes) !== JSON.stringify(episodes);
    episodes = nextEpisodes;
    if (changed) renderEpisodes();
    // A new publication updates the list without interrupting someone's episode.
    if (!selectedId || (!engaged && selectedId !== episodes[0].id)) selectEpisode(episodes[0]);
    const updatedAt = Date.parse(data.updatedAt);
    const stale = data.stale || (Number.isFinite(updatedAt) && Date.now() - updatedAt > 2 * 60 * 60 * 1000);
    listStatus.textContent = stale ? "We haven’t been able to check for new episodes recently. You can still pick one below." : "";
    retryButton.hidden = !stale;
  } catch {
    listStatus.textContent = episodes.length
      ? "We couldn’t check for new episodes right now. You can still choose one below."
      : "The episode list isn’t loading right now. You can still listen in the Spotify player.";
    retryButton.hidden = false;
  } finally {
    refreshing = false;
  }
}

window.onSpotifyIframeApiReady = (api) => {
  const selected = episodes.find((episode) => episode.id === selectedId);
  const target = selected?.uri || previewUri;
  playerContainer.querySelector("iframe")?.remove();
  api.createController(playerContainer, { uri: target, width: "100%", height: 352 }, (embedController) => {
    controller = embedController;
    controller.addListener("playback_started", () => { engaged = true; });
    const current = episodes.find((episode) => episode.id === selectedId);
    // Request video even when the local preview cannot fetch the episode list.
    controller.loadEntity(current?.uri || previewUri, true);
    if (pendingPlay) {
      controller.addListener("ready", () => {
        if (pendingPlay) { pendingPlay = false; controller.play(); }
      });
    }
  });
};
const apiScript = document.createElement("script");
apiScript.src = "https://open.spotify.com/embed/iframe-api/v1";
apiScript.async = true;
document.body.append(apiScript);
retryButton.addEventListener("click", refreshEpisodes);
refreshEpisodes();
window.setInterval(() => {
  if (!document.hidden) refreshEpisodes();
}, 5 * 60 * 1000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshEpisodes();
});

const menuButton = document.querySelector(".menu-toggle");
const siteNav = document.querySelector("#site-nav");
menuButton.addEventListener("click", () => {
  const isOpen = siteNav.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(isOpen));
});
siteNav.addEventListener("click", () => {
  siteNav.classList.remove("open");
  menuButton.setAttribute("aria-expanded", "false");
});
document.querySelector("#year").textContent = new Date().getFullYear();
