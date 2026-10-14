import {normalize, prepareIndex, searchEpisodes} from './podcast-search-core.mjs';

const search = document.querySelector('.podcast-search');
const input = document.querySelector('#podcast-search-input');
const clear = document.querySelector('#podcast-search-clear');
const status = document.querySelector('#podcast-search-status');
const list = document.querySelector('#spotify-episode-list');
const originalItems = [...list.children];
const byUrl = new Map(originalItems.map(item => [item.querySelector('a').getAttribute('href'), item]));
let indexPromise;
let debounce;
let revision = 0;

function loadIndex() {
  if (!indexPromise) {
    indexPromise = fetch(search.dataset.indexUrl, {signal: AbortSignal.timeout(15000)})
      .then(response => {
        if (!response.ok) throw new Error('Search index unavailable');
        return response.json();
      }).then(data => {
        if (data.version !== 1 || !Array.isArray(data.episodes)) throw new Error('Search index invalid');
        return prepareIndex(data.episodes);
      }).catch(error => {
        indexPromise = undefined; // A later input/focus can retry after a network failure.
        throw error;
      });
  }
  return indexPromise;
}

function updateUrl() {
  const url = new URL(location.href);
  const query = input.value.trim();
  if (query) url.searchParams.set('q', query);
  else url.searchParams.delete('q');
  if (url.href !== location.href) history.pushState(null, '', url);
}

async function render(updateHistory = true) {
  const current = ++revision;
  const query = input.value;
  clear.hidden = !query;
  if (updateHistory) updateUrl();
  if (!normalize(query)) {
    list.replaceChildren(...originalItems);
    status.textContent = '';
    return;
  }
  status.textContent = 'Searching episodes…';
  try {
    const index = await loadIndex();
    if (current !== revision) return;
    const matches = searchEpisodes(index, query).filter(record => byUrl.has(record.url));
    list.replaceChildren(...matches.map(record => byUrl.get(record.url)));
    status.textContent = matches.length
      ? `${matches.length} ${matches.length === 1 ? 'episode' : 'episodes'}`
      : 'No episodes found. Try another search.';
  } catch {
    if (current !== revision) return;
    list.replaceChildren(...originalItems);
    status.textContent = 'Search is unavailable right now. You can still browse all episodes below.';
  }
}

input.addEventListener('focus', () => { loadIndex().catch(() => {}); });
input.addEventListener('input', () => {
  ++revision; // Ignore pending results while the user continues typing.
  clear.hidden = !input.value;
  clearTimeout(debounce);
  debounce = setTimeout(() => render(), 150);
});
clear.addEventListener('click', () => {
  clearTimeout(debounce);
  input.value = '';
  render();
  input.focus();
});
window.addEventListener('popstate', () => {
  clearTimeout(debounce);
  input.value = new URL(location.href).searchParams.get('q') || '';
  render(false);
});
search.hidden = false;
input.value = new URL(location.href).searchParams.get('q') || '';
if (input.value) render(false);
