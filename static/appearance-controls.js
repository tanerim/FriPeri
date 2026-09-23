/* Form values remain authoritative; previews never save implicitly. */
(() => {
  document.querySelectorAll('[data-color-control]').forEach(control => {
    const picker = control.querySelector('[data-color-picker]');
    const value = control.querySelector('[data-color-value]');
    picker.addEventListener('input', () => {
      // Keep an existing alpha channel when changing only the color swatch.
      const alpha = value.maxLength === 9 && /^#[\da-f]{8}$/i.test(value.value) ? value.value.slice(7) : '';
      value.value = picker.value + alpha;
      value.dispatchEvent(new Event('input', {bubbles:true}));
    });
    value.addEventListener('input', () => {
      if (value.validity.valid) picker.value = (value.value || value.dataset.fallback).slice(0,7);
    });
  });
  document.querySelectorAll('[data-category-appearance]').forEach(card => {
    const preview = card.querySelector('.category-card-preview');
    const update = () => {
      for (const [key,property] of [['background','backgroundColor'],['text_color','color']]) {
        const input = card.querySelector(`[name$="_${key}"]`);
        if (input.validity.valid) preview.style[property] = input.value || input.dataset.fallback;
      }
      card.querySelectorAll('[data-card-preview]').forEach(item => {
        item.hidden = !card.querySelector(`[name$="_${item.dataset.cardPreview}"]`).checked;
      });
    };
    card.addEventListener('input',update);
    card.querySelector('[data-card-reset]').addEventListener('click', () => {
      card.querySelectorAll('[data-color-value]').forEach(input => {
        input.value = ''; input.dispatchEvent(new Event('input',{bubbles:true}));
      });
      card.querySelectorAll('input[type="checkbox"]').forEach(input => { input.checked = true; });
      update();
    });
    update();
  });
})();
