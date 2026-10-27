(() => {
  const search = document.getElementById('game-search');
  const cards = Array.from(document.querySelectorAll('.game-card'));
  const empty = document.getElementById('empty-state');

  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase('ko');
    let visible = 0;

    cards.forEach((card) => {
      const text = (card.dataset.search + ' ' + card.innerText).toLocaleLowerCase('ko');
      const match = text.includes(query);
      card.hidden = !match;
      if (match) visible++;
    });

    empty.hidden = visible !== 0;
  });
})();
