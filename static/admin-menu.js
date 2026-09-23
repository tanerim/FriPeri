(() => {
  // Scroll to highlighted category row if present
  const highlightId = document.querySelector('input[name="highlight_category"]');
  if (highlightId) {
    const row = highlightId.closest('.menu-category-row');
    if (row) {
      setTimeout(() => row.scrollIntoView({ behavior: 'smooth', block: 'center' }), 200);
    }
  }
  const list = document.getElementById('custom-menu-items');
  function updateParents() {
    const groups = [...list.querySelectorAll('.custom-menu-row')].map(row => {
      const id = row.querySelector('[name="custom_id"]').value;
      return {key:'custom-' + id, label:row.querySelector(`[name="custom_en_${id}"]`).value.trim() || '…'};
    });
    document.querySelectorAll('[data-menu-parent]').forEach(select => {
      const value = select.value;
      select.replaceChildren(new Option(select.dataset.rootLabel, ''));
      groups.filter(group => group.key !== select.dataset.menuParent).forEach(group => {
        select.add(new Option(group.label, group.key));
      });
      select.value = groups.some(group => group.key === value && group.key !== select.dataset.menuParent) ? value : '';
    });
  }
  let nextId = 0;
  document.getElementById('add-menu-item').addEventListener('click', () => {
    const fragment = document.getElementById('custom-menu-template').content.cloneNode(true);
    const id = 'new-' + Date.now() + '-' + nextId++;
    fragment.querySelectorAll('input,select').forEach(input => {
      input.name = input.name.replace('__NEW__', id);
      if(input.dataset.menuParent) input.dataset.menuParent = input.dataset.menuParent.replace('__NEW__', id);
      if (input.name === 'custom_id') input.value = id;
    });
    list.append(fragment);
    updateParents();
    list.lastElementChild.querySelector('input:not([type="hidden"])').focus();
  });
  list.addEventListener('click', event => {
    const button = event.target.closest('[data-delete-menu]');
    if (button) { button.closest('.social-settings-item').remove(); updateParents(); }
  });
  list.addEventListener('input', event => { if(event.target.name?.startsWith('custom_en_')) updateParents(); });
})();
