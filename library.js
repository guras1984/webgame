// Browser-local library: no account, tracking request, or game-save changes.
(() => {
  'use strict';
  const list = document.getElementById('game-list');
  const cards = [...list.querySelectorAll('.game')];
  const search = document.getElementById('search');
  const genre = document.getElementById('game-genre');
  const empty = document.getElementById('empty');
  const status = document.getElementById('library-status');
  const key = 'my-world:library:v1';
  const viewKey = 'my-world:library-view:v1';
  const ids = new Set(cards.map(card => card.dataset.game));
  const normalize = value => String(value || '').normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g, ' ').trim();
  const clean = value => ({
    favorites: [...new Set(Array.isArray(value?.favorites) ? value.favorites.filter(id => ids.has(id)) : [])],
    recent: Object.fromEntries(Object.entries(value?.recent && typeof value.recent === 'object' ? value.recent : {}).filter(([id, time]) => ids.has(id) && Number.isSafeInteger(time) && time > 0 && time <= Date.now() + 60000))
  });
  let memory = clean(null), savedView = {}, filter = 'all', storageUnavailable = false;
  function load() { if (storageUnavailable) return memory; try { memory = clean(JSON.parse(localStorage.getItem(key) || 'null')); } catch {} return memory; }
  function save() { try { localStorage.setItem(key, JSON.stringify(memory)); } catch { storageUnavailable = true; status.textContent = '저장 공간을 사용할 수 없어 이번 화면에서만 기억해요.'; } }
  try { savedView = JSON.parse(sessionStorage.getItem(viewKey) || '{}') || {}; } catch {}
  if (['all', 'recent', 'favorites'].includes(savedView.filter)) filter = savedView.filter;
  if (typeof savedView.query === 'string') search.value = savedView.query.slice(0, 100);
  if ([...genre.options].some(option => option.value === savedView.genre)) genre.value = savedView.genre;
  function saveView() {
    try { sessionStorage.setItem(viewKey, JSON.stringify({ filter, query: search.value.slice(0, 100), genre: genre.value, left: list.scrollLeft })); } catch {}
  }
  function recentLink() {
    const id = Object.keys(memory.recent).sort((a, b) => memory.recent[b] - memory.recent[a])[0];
    const row = document.getElementById('last-game');
    const card = cards.find(card => card.dataset.game === id);
    row.hidden = !card;
    if (!card) return;
    const link = row.querySelector('a');
    link.href = card.querySelector('a.play').href;
    link.dataset.game = id;
    link.textContent = card.querySelector('h2').textContent + ' 다시 열기 ↗';
  }
  function render(reset = false) {
    const left = reset ? 0 : list.scrollLeft;
    const words = normalize(search.value).split(' ').filter(Boolean);
    const order = filter === 'recent' ? cards.slice().sort((a, b) => (memory.recent[b.dataset.game] || 0) - (memory.recent[a.dataset.game] || 0)) : cards;
    let count = 0;
    for (const card of order) {
      const id = card.dataset.game;
      const liked = memory.favorites.includes(id);
      const haystack = normalize(card.dataset.search + ' ' + card.querySelector('h2').textContent);
      card.hidden = !words.every(word => haystack.includes(word)) || (genre.value !== 'all' && card.dataset.genre !== genre.value) || (filter === 'favorites' && !liked) || (filter === 'recent' && !memory.recent[id]);
      const button = card.querySelector('.game-favorite');
      button.setAttribute('aria-pressed', String(liked));
      button.setAttribute('aria-label', card.querySelector('h2').textContent + (liked ? ' 좋아요 해제' : ' 좋아요'));
      button.textContent = liked ? '♥' : '♡';
      if (!card.hidden) count++;
      list.insertBefore(card, empty);
    }
    document.querySelectorAll('[data-library-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.libraryFilter === filter)));
    document.getElementById('game-count').textContent = count + '개';
    empty.hidden = count !== 0;
    empty.querySelector('span').textContent = filter === 'favorites' && !memory.favorites.length ? '하트를 누르면 좋아하는 게임을 여기서 모아 볼 수 있어요.' : filter === 'recent' && !Object.keys(memory.recent).length ? '게임을 열면 최근 목록에 자동으로 모여요.' : '조건에 맞는 게임이 없어요. 검색이나 분류를 바꿔 보세요.';
    list.scrollLeft = left;
    recentLink(); saveView();
  }
  function opened(id) {
    if (!ids.has(id)) return;
    load(); memory.recent[id] = Date.now(); save(); recentLink(); saveView();
  }
  for (const card of cards) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'game-favorite';
    card.append(button);
    button.addEventListener('click', () => {
      load(); const id = card.dataset.game;
      memory.favorites = memory.favorites.includes(id) ? memory.favorites.filter(value => value !== id) : [...memory.favorites, id];
      render(); save();
      if (card.hidden) document.querySelector('[data-library-filter="' + filter + '"]').focus();
    });
    const link = card.querySelector('a.play');
    link.addEventListener('click', () => opened(card.dataset.game));
    link.addEventListener('auxclick', event => { if (event.button === 1) opened(card.dataset.game); });
  }
  document.querySelectorAll('[data-library-filter]').forEach(button => button.addEventListener('click', () => { filter = button.dataset.libraryFilter; render(true); }));
  search.addEventListener('input', () => render(true));
  genre.addEventListener('change', () => render(true));
  document.getElementById('reset-library').addEventListener('click', () => { filter = 'all'; genre.value = 'all'; search.value = ''; render(true); search.focus(); });
  document.querySelector('#last-game a').addEventListener('click', event => opened(event.currentTarget.dataset.game));
  let scrollFrame;
  list.addEventListener('scroll', () => { cancelAnimationFrame(scrollFrame); scrollFrame = requestAnimationFrame(saveView); }, { passive: true });
  addEventListener('pagehide', saveView);
  addEventListener('storage', event => { if (event.key === key || event.key === null) { load(); render(); } });
  addEventListener('pageshow', () => { load(); render(); });
  load(); render();
  requestAnimationFrame(() => { if (Number.isFinite(savedView.left)) list.scrollLeft = Math.max(0, savedView.left); });
})();
