"use strict";
/* Accessible, reusable HTML5 dialog for published Image blocks. */
document.addEventListener("click", event => {
  const trigger=event.target.closest?.(".friperi-image-lightbox-trigger, .custom-rich-text img.rich-image[data-rich-action='lightbox']");
  if(!trigger || trigger.closest('[contenteditable]'))return;
  const source=trigger.matches('img')?trigger:trigger.querySelector("img");
  if(!source?.src)return;
  let dialog=document.getElementById("friperi-image-lightbox");
  if(!dialog){
    dialog=document.createElement("dialog");
    dialog.id="friperi-image-lightbox";
    dialog.className="friperi-image-lightbox";
    const close=document.createElement("button");
    close.type="button";
    close.className="friperi-image-lightbox-close";
    close.textContent="Close";
    close.setAttribute("aria-label","Close image preview");
    close.addEventListener("click",()=>dialog.close());
    const image=document.createElement("img");
    image.alt="";
    image.decoding="async";
    const caption=document.createElement("p");
    caption.className="friperi-image-lightbox-caption";
    dialog.append(close,image,caption);
    dialog.addEventListener("click",ev=>{if(ev.target===dialog)dialog.close()});
    document.body.append(dialog);
  }
  const image=dialog.querySelector("img");
  image.src=source.currentSrc||source.src;
  image.alt=source.alt;
  const caption=trigger.closest("figure")?.querySelector("figcaption")?.textContent||source.alt;
  dialog.querySelector(".friperi-image-lightbox-caption").textContent=caption;
  dialog.showModal();
});
