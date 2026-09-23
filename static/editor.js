function panelEditor(button) {
  return button.closest('[data-editor-panel]').querySelector('[data-editor]');
}
function formatDoc(button, command, value = null) {
  const editor = panelEditor(button);
  editor.focus();
  document.execCommand(command, false, value);
}
function syncEditor(validate = false) {
  let valid = true;
  document.querySelectorAll('[data-editor]').forEach(editor => {
    const target = document.querySelector('[name="' + editor.dataset.editor + '"]');
    if (target) target.value = editor.textContent.trim() ? editor.innerHTML : '';
    if (validate && editor.dataset.required === '1' && !editor.textContent.trim()) {
      editor.focus(); editor.setAttribute('aria-invalid', 'true'); valid = false;
    } else { editor.removeAttribute('aria-invalid'); }
  });
  return valid;
}
function promptLink(button) {
  const url = prompt(button.dataset.prompt);
  if (url) formatDoc(button, 'createLink', url);
}
function insertTable(button) {
  const table = document.createElement('table');
  for (const tag of ['th', 'td']) {
    const row = table.insertRow();
    for (let i = 0; i < 2; i++) {
      const cell = document.createElement(tag);
      cell.textContent = tag === 'th' ? button.dataset.header : button.dataset.cell;
      row.append(cell);
    }
  }
  formatDoc(button, 'insertHTML', table.outerHTML + '<p><br></p>');
}

function updateSubmitStatus() {
  const select = document.querySelector('[data-status-select]');
  const button = document.querySelector('[data-draft-label][data-publish-label]');
  if (!select || !button) return;
  button.textContent = select.value === 'published' ? button.dataset.publishLabel : button.dataset.draftLabel;
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!confirm(form.dataset.confirm || 'Are you sure?')) event.preventDefault();
    });
  });

  const status = document.querySelector('[data-status-select]');
  if (status) {
    updateSubmitStatus();
    status.addEventListener('change', updateSubmitStatus);
  }

  const translationToggle = document.getElementById('translation-toggle-input');
  const translationPanel = document.getElementById('translation-panel');
  if (translationToggle && translationPanel) {
    translationToggle.addEventListener('change', () => {
      if (translationToggle.checked) {
        translationPanel.classList.remove('is-collapsed');
      } else {
        const hasExisting = translationToggle.dataset.hasExisting === '1';
        const titleSec = document.querySelector('[name="title_secondary"]');
        const excerptSec = document.querySelector('[name="excerpt_secondary"]');
        const editorSec = document.querySelector('[data-editor="body_html_secondary"]');
        const hasValues = (titleSec && titleSec.value.trim()) ||
                          (excerptSec && excerptSec.value.trim()) ||
                          (editorSec && editorSec.textContent.trim());

        if (hasExisting || hasValues) {
          const confirmMsg = translationToggle.dataset.confirmHide || 'Hide translation fields? Existing translation will be preserved.';
          if (!confirm(confirmMsg)) {
            translationToggle.checked = true;
            return;
          }
        }
        translationPanel.classList.add('is-collapsed');
      }
    });
  }

  const imageInput = document.getElementById('content-image-input');
  const imagePreviewContainer = document.getElementById('image-preview-container');
  const imagePreviewImg = document.getElementById('image-preview-img');
  const fileNameLabel = document.getElementById('file-upload-name');
  const clearBtn = document.getElementById('clear-image-btn');

  let originalImage = imagePreviewImg?.getAttribute('src') || '';
  let cropSource = originalImage, applyingCrop = false;
  document.addEventListener('content:image-saved', event => {
    originalImage = cropSource = event.detail || '';
    if (imageInput) imageInput.value = '';
    if (imagePreviewImg) imagePreviewImg.src = originalImage;
    if (fileNameLabel) fileNameLabel.textContent = 'No file selected';
    if (imagePreviewContainer) imagePreviewContainer.classList.toggle('is-hidden', !originalImage);
  });
  const cropBtn = document.getElementById('crop-image-btn');
  if (cropBtn && imageInput) cropBtn.addEventListener('click', async () => {
    const source = cropSource || imageInput.files[0] || originalImage;
    if (!source) return;
    cropBtn.disabled = true;
    try {
      const cropped = await window.cropContentImage(source);
      if (cropped) {
        const transfer = new DataTransfer(); transfer.items.add(cropped);
        imageInput.files = transfer.files; applyingCrop = true;
        imageInput.dispatchEvent(new Event('change')); applyingCrop = false;
      }
    } finally { cropBtn.disabled = false; }
  });

  if (imageInput) {
    imageInput.addEventListener('change', () => {
      const file = imageInput.files && imageInput.files[0];
      if (file) {
        if (!applyingCrop) cropSource = file;
        if (fileNameLabel) fileNameLabel.textContent = file.name;
        const reader = new FileReader();
        reader.onload = (e) => {
          if (imagePreviewImg) imagePreviewImg.src = e.target.result;
          if (imagePreviewContainer) imagePreviewContainer.classList.remove('is-hidden');
        };
        reader.readAsDataURL(file);
      } else {
        if (fileNameLabel) fileNameLabel.textContent = 'No file selected';
      }
    });
  }

  if (clearBtn && imageInput) {
    clearBtn.addEventListener('click', () => {
      imageInput.value = ''; cropSource = originalImage;
      if (fileNameLabel) fileNameLabel.textContent = 'No file selected';
      if (imagePreviewImg) imagePreviewImg.src = originalImage;
      if (imagePreviewContainer) imagePreviewContainer.classList.toggle('is-hidden', !originalImage);
      imageInput.dispatchEvent(new Event('change', {bubbles: true}));
    });
  }
});
