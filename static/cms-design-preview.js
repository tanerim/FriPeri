"use strict";
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".cms-design-page form[action='/admin/cms-design'][method='post']");
  const root = document.querySelector(".cms-preview-root");
  const viewport = document.querySelector(".cms-preview-viewport");
  if (!form || !root || !viewport) return;
  const value = (name) => form.elements.namedItem(name)?.value || "";
  const checked = (name) => !!form.elements.namedItem(name)?.checked;
  const update = () => {
    const fields = {
      archiveColumns:"columns", archiveCardStyle:"card_style", layout:"layout",
      orientation:"orientation", imagePosition:"image_position", imageRatio:"image_ratio",
      cardHeight:"card_height", spacing:"spacing", textAlign:"text_align",
      excerptLength:"excerpt_length"
    };
    for (const [key, name] of Object.entries(fields)) root.dataset[key] = value(name);
    const colors = {
      accent:"--archive-accent", background:"--archive-page-bg",
      card_background:"--archive-card-bg",text_color:"--archive-card-text"
    };
    for (const [name, prop] of Object.entries(colors)) {
      const hex = value(name).trim();
      if (/^#[0-9a-f]{6}$/i.test(hex)) root.style.setProperty(prop,hex);
      else root.style.removeProperty(prop);
    }
    const selectors = {
      show_image:".category-publication-image",
      show_title:".category-publication-card-title",
      show_date:".category-publication-meta time",
      show_excerpt:".category-publication-card-excerpt",
      show_author:".cms-preview-author",
      show_category:".category-publication-meta-type",
      show_likes:".cms-preview-likes",
      show_comments:".cms-preview-comments"
    };
    for (const [name,selector] of Object.entries(selectors))
      root.querySelectorAll(selector).forEach(el => {el.hidden = !checked(name) || (name==="show_excerpt" && value("excerpt_length")==="hidden");});
    root.querySelectorAll(".category-publication-card").forEach(card => {
      const image=card.querySelector(".category-publication-image");
      card.classList.toggle("no-image",!image || image.hidden);
    });
  };
  form.addEventListener("input",update);
  form.addEventListener("change",update);
  document.querySelectorAll(".cms-preview-devices button").forEach(button => {
    button.addEventListener("click", () => {
      const mobile=button.dataset.device==="mobile";
      viewport.classList.toggle("is-mobile",mobile);
      document.querySelectorAll(".cms-preview-devices button").forEach(item =>
        item.setAttribute("aria-pressed",String(item===button)));
    });
  });
  update();
});
