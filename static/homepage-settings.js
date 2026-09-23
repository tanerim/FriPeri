(() => {
  const form = document.getElementById('homepage-form');
  if (!form) return;
  const config = JSON.parse(document.getElementById('builder-config').textContent);
  const choices = [...form.querySelectorAll('input[name="homepage_mode"]')];
  const feed = document.getElementById('homepage-feed-panel');
  const custom = document.getElementById('homepage-custom-panel');
  const status = document.getElementById('homepage-save-status');
  let savedMode = config.mode, saving = false, builderBusy = false;
  const mode = () => choices.find(input => input.checked).value;
  const feedSnapshot = () => JSON.stringify([...new FormData(form)].filter(([key]) => key !== 'homepage_mode').map(([key,value]) => [key, value instanceof File ? (value.name ? [value.name,value.size,value.lastModified] : null) : value]));
  // Capture feed fields even when the initial selection is Custom Home.
  feed.disabled = false;
  let savedFeed = feedSnapshot();
  const update = () => {
    const isCustom = mode() === 'custom';
    feed.hidden = feed.disabled = isCustom;
    custom.hidden = custom.disabled = !isCustom;
    form.querySelectorAll('[data-feed-save]').forEach(button => { button.hidden = isCustom; button.disabled = saving || builderBusy; });
    choices.forEach(input => { input.disabled = saving || builderBusy; });
  };
  choices.forEach(input => input.addEventListener('change', () => {
    update(); status.textContent = '';
    document.getElementById('builder-status').textContent = '';
    form.querySelector('.settings-notice')?.remove();
  }));
  document.addEventListener('homepage:builder-busy', event => { builderBusy = event.detail; update(); });
  document.addEventListener('homepage:saved', event => { savedMode = event.detail; });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (saving || builderBusy) return;
    if (mode() === 'custom') { document.getElementById('builder-save').click(); return; }
    const data = new FormData(form), sent = feedSnapshot();
    saving = true; update(); status.className = 'notice'; status.textContent = config.labels.saving;
    try {
      const response = await fetch(form.action, {method:'POST',body:data});
      if (!response.ok || new URL(response.url).pathname !== '/admin/homepage') throw new Error(config.labels.error);
      savedFeed = sent; savedMode = 'feed'; status.textContent = config.labels.saved;
    } catch (error) { status.className = 'error'; status.textContent = error.message || config.labels.error; }
    finally { saving = false; update(); }
  });
  window.addEventListener('beforeunload', event => {
    const wasDisabled = feed.disabled;
    feed.disabled = false;
    const changed = savedFeed !== feedSnapshot();
    feed.disabled = wasDisabled;
    if (saving || changed || mode() !== savedMode) { event.preventDefault(); event.returnValue = ''; }
  });
  update();
})();
