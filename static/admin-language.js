(() => {
  const form = document.querySelector('[data-language-form]');
  if (!form) return;
  const select = form.elements.secondary_language;
  const name = form.elements.secondary_language_name;
  const code = form.elements.secondary_language_code;
  const editorCode = form.elements.translation_language_code;
  function update() {
    const custom = select.value === 'custom';
    form.querySelectorAll('[data-custom-language]').forEach(el => { el.hidden = !custom; });
    name.required = code.required = custom;
    form.querySelector('[data-switcher-card]').hidden = !select.value;
    form.querySelectorAll('[data-secondary-name]').forEach(el => { el.textContent = name.value; });
    if (!editorCode.value) editorCode.value = code.value.trim().toLowerCase();
  }
  select.addEventListener('change', update);
  name.addEventListener('input', update);
  function changeCode() {
    const normalized = code.value.trim().toLowerCase();
    if (editorCode.value && editorCode.value !== normalized) {
      form.querySelectorAll('textarea[name^="translation_"]').forEach(input => { input.value = ''; });
    }
    editorCode.value = normalized;
    update();
  }
  code.addEventListener('change', changeCode);
  const detected = form.querySelector('[data-detected-name]');
  const button = form.querySelector('[data-use-detected]');
  if (detected && button) {
    try {
      const display = new Intl.DisplayNames(['en'], {type: 'language'}).of(detected.dataset.code);
      if (display) { detected.textContent = display; button.dataset.name = display; }
    } catch (_) { /* Keep the server-provided, escaped language code. */ }
    button.textContent = button.dataset.label.replace('{name}', button.dataset.name);
    button.addEventListener('click', () => {
      select.value = button.dataset.supported === '1' ? button.dataset.code : 'custom';
      if (select.value === 'custom') {
        name.value = button.dataset.name;
        code.value = button.dataset.code;
        changeCode();
      }
      update();
      select.focus();
    });
  }
  update();
})();
