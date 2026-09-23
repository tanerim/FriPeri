/* Shared local image cropper. Nothing is uploaded until the caller saves. */
(() => {
  const labels = JSON.parse(document.getElementById('image-crop-labels').textContent);
  const t = key => labels[key] || key;
  window.cropContentImage = source => new Promise(resolve => {
    const dialog = document.createElement('dialog');
    dialog.className = 'image-crop-dialog';
    dialog.setAttribute('aria-labelledby', 'image-crop-title');
    const heading = document.createElement('h2');
    heading.id = 'image-crop-title'; heading.textContent = t('title');
    const help = document.createElement('p'); help.textContent = t('help');
    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-label', t('keyboard_help'));
    canvas.tabIndex = 0;
    const dimensions = document.createElement('output'); dimensions.className = 'image-crop-dimensions';
    dimensions.setAttribute('aria-live','polite');
    const controls = document.createElement('div'); controls.className = 'image-crop-controls';
    const field = (key, input) => {
      const label = document.createElement('label');
      const span = document.createElement('span'); span.textContent = t(key);
      label.append(span, input); controls.append(label); return input;
    };
    const ratio = field('ratio', document.createElement('select'));
    for (const [value, text] of [['original',t('original')],['1','1:1'],['1.5','3:2'],['1.7777777778','16:9'],['1.3333333333','4:3'],['0.75','3:4'],['0.8','4:5'],['0.5625','9:16']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = text; ratio.append(option);
    }
    const range = (key, max, value) => {
      const input = document.createElement('input'); input.type = 'range';
      input.min = key === 'zoom' ? '1' : '0'; input.max = max; input.step = '0.01'; input.value = value;
      return field(key, input);
    };
    const zoom = range('zoom', '4', '1'), horizontal = range('horizontal', '1', '0.5'), vertical = range('vertical', '1', '0.5');
    const toolbar = document.createElement('div'); toolbar.className = 'image-crop-toolbar';
    const tool = (key, action) => {
      const button = document.createElement('button'); button.type = 'button';
      button.className = 'admin-secondary'; button.textContent = t(key); button.dataset.cropAction = key;
      button.addEventListener('click', action); toolbar.append(button); return button;
    };
    const oriented = document.createElement('canvas');
    let rotation = 0, flipX = 1, flipY = 1, showGrid = true;
    const center = () => { horizontal.value = vertical.value = '0.5'; };
    tool('rotate_left', () => { rotation = (rotation + 270) % 360; center(); transform(); });
    tool('rotate_right', () => { rotation = (rotation + 90) % 360; center(); transform(); });
    tool('flip_horizontal', () => { flipX *= -1; transform(); });
    tool('flip_vertical', () => { flipY *= -1; transform(); });
    const gridButton = tool('grid', () => { showGrid = !showGrid; gridButton.setAttribute('aria-pressed',String(showGrid)); draw(); });
    gridButton.setAttribute('aria-pressed','true');
    tool('reset', () => { rotation = 0; flipX = flipY = 1; ratio.value = 'original'; zoom.value = '1'; center(); transform(); });
    const format = field('format', document.createElement('select'));
    for (const value of ['webp','png']) { const option = document.createElement('option'); option.value = value; option.textContent = value.toUpperCase(); format.append(option); }
    const error = document.createElement('p'); error.className = 'error'; error.setAttribute('role','alert'); error.hidden = true;
    const actions = document.createElement('div'); actions.className = 'image-crop-actions';
    const cancel = document.createElement('button'), apply = document.createElement('button');
    cancel.type = apply.type = 'button'; cancel.className = 'admin-secondary'; apply.className = 'settings-primary';
    cancel.textContent = t('cancel'); apply.textContent = t('apply'); apply.disabled = true;
    actions.append(cancel, apply); dialog.append(heading, help, toolbar, canvas, dimensions, controls, error, actions); document.body.append(dialog);
    const originalFocus = document.activeElement;
    const image = new Image();
    let objectURL, loaded = false, finished = false, exporting = false;
    const finish = file => {
      if (finished) return;
      finished = true; dialog.close(); dialog.remove();
      if (objectURL) URL.revokeObjectURL(objectURL);
      originalFocus?.focus(); resolve(file);
    };
    const fail = () => { error.textContent = t('error'); error.hidden = false; };
    const transform = () => {
      if (!loaded) return;
      // Bound the working canvas while retaining the existing 4096px export limit.
      const scale = Math.min(1,4096/image.naturalWidth,4096/image.naturalHeight);
      const width = Math.max(1,Math.round(image.naturalWidth*scale)), height = Math.max(1,Math.round(image.naturalHeight*scale));
      oriented.width = rotation % 180 ? height : width; oriented.height = rotation % 180 ? width : height;
      const ctx = oriented.getContext('2d');
      ctx.translate(oriented.width/2,oriented.height/2); ctx.scale(flipX,flipY); ctx.rotate(rotation*Math.PI/180);
      ctx.drawImage(image,-width/2,-height/2,width,height); draw();
    };
    const rect = () => {
      const aspect = ratio.value === 'original' ? oriented.width / oriented.height : Number(ratio.value);
      const width = Math.min(oriented.width, oriented.height * aspect) / Number(zoom.value);
      const height = width / aspect;
      return {width, height, x: (oriented.width-width)*Number(horizontal.value), y: (oriented.height-height)*Number(vertical.value)};
    };
    const draw = () => {
      if (!loaded) return;
      const crop = rect(), scale = Math.min(640/crop.width, 420/crop.height, 1);
      canvas.width = Math.max(1, Math.round(crop.width*scale)); canvas.height = Math.max(1, Math.round(crop.height*scale));
      const ctx = canvas.getContext('2d');
      ctx.drawImage(oriented,crop.x,crop.y,crop.width,crop.height,0,0,canvas.width,canvas.height);
      if (showGrid) {
        ctx.strokeStyle = '#ffffffaa'; ctx.lineWidth = 1; ctx.beginPath();
        for (const part of [1/3,2/3]) {
          ctx.moveTo(canvas.width*part,0); ctx.lineTo(canvas.width*part,canvas.height);
          ctx.moveTo(0,canvas.height*part); ctx.lineTo(canvas.width,canvas.height*part);
        }
        ctx.stroke();
      }
      dimensions.textContent = t('output') + ': ' + Math.max(1,Math.round(crop.width)) + ' × ' + Math.max(1,Math.round(crop.height)) + ' px · ' + Math.round(Number(zoom.value)*100) + '%';
    };
    controls.addEventListener('input', draw);
    let drag;
    canvas.addEventListener('pointerdown', event => {
      if (!loaded) return;
      drag = {x:event.clientX, y:event.clientY, horizontal:Number(horizontal.value), vertical:Number(vertical.value), crop:rect()};
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove', event => {
      if (!drag) return;
      const box = canvas.getBoundingClientRect(), crop = drag.crop;
      const dx = oriented.width-crop.width, dy = oriented.height-crop.height;
      if (dx > 0) horizontal.value = String(Math.max(0,Math.min(1,drag.horizontal-(event.clientX-drag.x)*crop.width/box.width/dx)));
      if (dy > 0) vertical.value = String(Math.max(0,Math.min(1,drag.vertical-(event.clientY-drag.y)*crop.height/box.height/dy)));
      draw();
    });
    canvas.addEventListener('keydown', event => {
      const moves = {ArrowLeft: [horizontal,-1], ArrowRight: [horizontal,1], ArrowUp: [vertical,-1], ArrowDown: [vertical,1]};
      if (!moves[event.key] || !loaded) return;
      event.preventDefault(); const [input,direction] = moves[event.key];
      input.value = String(Math.max(0,Math.min(1,Number(input.value)+direction*(event.shiftKey ? 0.1 : 0.02)))); draw();
    });
    canvas.addEventListener('lostpointercapture', () => { drag = null; });
    canvas.addEventListener('pointerup', () => { drag = null; });
    canvas.addEventListener('pointercancel', () => { drag = null; });
    cancel.addEventListener('click', () => finish(null));
    dialog.addEventListener('cancel', event => { event.preventDefault(); finish(null); });
    apply.addEventListener('click', () => {
      if (!loaded || exporting) return;
      exporting = true; apply.disabled = true;
      const crop = rect(), output = document.createElement('canvas');
      const scale = Math.min(1,4096/crop.width,4096/crop.height);
      output.width = Math.max(1,Math.round(crop.width*scale)); output.height = Math.max(1,Math.round(crop.height*scale));
      try {
        output.getContext('2d').drawImage(oriented,crop.x,crop.y,crop.width,crop.height,0,0,output.width,output.height);
        output.toBlob(blob => {
          if (finished) return;
          if (!blob) { fail(); exporting = false; apply.disabled = false; return; }
          const name = source instanceof File ? source.name.replace(/\.[^.]+$/, '') : 'image';
          finish(new File([blob], name+'-cropped.'+(blob.type === 'image/webp' ? 'webp' : 'png'), {type:blob.type}));
        }, 'image/'+format.value, 0.92);
      } catch { fail(); exporting = false; apply.disabled = false; }
    });
    image.onload = () => { if (!finished) { loaded = true; apply.disabled = false; transform(); } };
    image.onerror = fail;
    dialog.showModal();
    if (source instanceof File) {
      objectURL = URL.createObjectURL(source); image.src = objectURL;
    } else if (typeof source === 'string' && source.startsWith('/static/uploads/')) {
      image.src = source;
    } else { fail(); }
  });
})();
