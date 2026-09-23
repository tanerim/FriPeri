(() => {
  const nav = document.querySelector('.nav-links');
  if (!nav) return;
  const closeAll = () => nav.querySelectorAll('.nav-group[open]').forEach(group => { group.open = false; });
  document.addEventListener('click', event => { if (!nav.contains(event.target)) closeAll(); });
  nav.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const group = event.target.closest('.nav-group[open]');
    if (group) { group.open = false; group.querySelector('summary').focus(); event.preventDefault(); }
    else closeAll();
  });
  nav.addEventListener('toggle', event => {
    const group = event.target;
    if (group.matches('.nav-group') && group.open) {
      [...group.parentElement.children].forEach(sibling => {
        if (sibling !== group && sibling.matches('.nav-group')) sibling.open = false;
      });
    }
  }, true);
})();
