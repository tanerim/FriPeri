/* Color templates only populate the Design form; the existing Save action persists it. */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".design-settings-form");
  const source = document.getElementById("design-color-template-data");
  if (!form || !source) return;
  const presets = JSON.parse(source.textContent || "[]");
  const buttons = [...form.querySelectorAll("[data-color-template]")];
  const feedback = document.getElementById("design-template-feedback");
  let selectedId = null;

  const markSelection = (id) => {
    selectedId = id;
    buttons.forEach(button => {
      const selected = button.dataset.colorTemplate === id;
      button.setAttribute("aria-pressed", String(selected));
    });
  };

  buttons.forEach(button => button.addEventListener("click", () => {
    const template = presets.find(item => item.id === button.dataset.colorTemplate);
    if (!template) return;
    for (const [key, color] of Object.entries(template.settings)) {
      const field = form.elements.namedItem(key);
      if (!field) continue;
      field.value = color;
      field.dispatchEvent(new Event("input", {bubbles: true}));
      field.dispatchEvent(new Event("change", {bubbles: true}));
      const picker = field.closest("[data-color-control]")?.querySelector("[data-color-picker]");
      if (picker) picker.value = color.slice(0, 7);
    }
    markSelection(template.id);
    if (feedback) feedback.textContent = template.name + " applied to all Design colors. Select Save changes to publish.";
  }));

  // The chosen template is a starting point, not a lock: manual edits remain possible.
  form.querySelectorAll("[data-color-value]").forEach(field => field.addEventListener("input", event => {
    if (event.isTrusted && selectedId) {
      markSelection(null);
      if (feedback) feedback.textContent = "Custom colors selected. Save changes to publish.";
    }
  }));
});
