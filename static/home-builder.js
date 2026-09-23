(() => {
  const config = JSON.parse(document.getElementById('builder-config').textContent);
  const page = config.page || 'home';
  let endpoint = config.endpoint || (page === 'about' ? '/admin/about' : '/admin/custom-home');
  const contentPrefix = page === 'post' ? 'post_' : page === 'page' ? 'page_' : (page === 'about' ? 'about_page_' : 'custom_home_');
  const details = document.getElementById('page-details');
  const metadata = () => details ? JSON.stringify([...new FormData(details)].map(([key,value]) => [key, value instanceof File ? [value.name,value.size,value.name ? value.lastModified : 0] : value])) : '';
  let savedMetadata = metadata();
  const t = key => config.labels[key] || key;
  let documents = config.documents, language = config.languages[0].suffix, selected = -1, busy = 0;
  let saved = JSON.stringify(documents), history = [saved], cursor = 0, timer;
  const canvas = document.getElementById('builder-canvas');
  const status = document.getElementById('builder-status');
  const saveButton = document.getElementById('builder-save');
  const previewButton = document.getElementById('builder-preview');
  const historyReplace = url => window.history.replaceState(null,'',url);
  const snapshot = () => JSON.stringify(documents);
  const blocks = () => documents[language];
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const button = (label, action, className = 'builder-tool') => {
    const node = el('button', className, label); node.type = 'button';
    node.addEventListener('click', action); return node;
  };
  async function responseJSON(response) {
    try { return await response.json(); } catch { throw new Error(t('error')); }
  }
  function message(text, error = false) {
    status.className = text ? (error ? 'error' : 'notice') : '';
    status.textContent = text;
  }
  function updateStatus() {
    document.getElementById('builder-dirty').textContent = snapshot() === saved && metadata() === savedMetadata ? t('ready') : t('changed');
    document.getElementById('builder-undo').disabled = cursor === 0;
    document.getElementById('builder-redo').disabled = cursor === history.length - 1;
    saveButton.disabled = previewButton.disabled = busy > 0;
    canvas.inert = busy > 0;
    document.getElementById('builder-add-blocks').inert = busy > 0;
    document.getElementById('builder-language').disabled = busy > 0;
    document.getElementById('builder-undo').disabled ||= busy > 0;
    document.getElementById('builder-redo').disabled ||= busy > 0;
    document.getElementById('builder-starter').disabled = busy > 0;
    document.dispatchEvent(new CustomEvent('homepage:builder-busy', {detail: busy > 0}));
  }
  function checkpoint() {
    clearTimeout(timer);
    const value = snapshot();
    if (history[cursor] !== value) {
      history = history.slice(0, cursor + 1); history.push(value);
      if (history.length > 60) history.shift();
      cursor = history.length - 1;
    }
    updateStatus();
  }
  function change() { clearTimeout(timer); timer = setTimeout(checkpoint, 350); updateStatus(); }
  function mutate(action) { checkpoint(); action(); checkpoint(); render(); }
  function field(label, value, onInput, type = 'text') {
    const wrapper = el('label', 'builder-field'); wrapper.append(el('span', '', label));
    const input = el('input'); input.type = type; input.value = value || '';
    input.addEventListener('input', () => { onInput(input.value); change(); });
    wrapper.append(input); return wrapper;
  }
  function select(label, value, options, onChange) {
    const wrapper = el('label', 'builder-select'); wrapper.append(el('span', '', label));
    const input = el('select');
    options.forEach(([key, name]) => { const option = el('option', '', name); option.value = key; input.append(option); });
    input.value = value;
    input.addEventListener('change', () => mutate(() => onChange(input.value)));
    wrapper.append(input); return wrapper;
  }
  function editable(tag, value, label, onInput, rich = false) {
    const node = el(tag, 'builder-editable');
    if (rich) node.innerHTML = value; else node.textContent = value;
    node.contentEditable = 'true'; node.setAttribute('role', 'textbox');
    node.setAttribute('aria-label', label); node.setAttribute('aria-multiline', 'true');
    node.dataset.placeholder = label;
    node.addEventListener('input', () => { onInput(rich ? node.innerHTML : node.textContent); change(); });
    // Pasted content is text only; formatting comes from the trusted toolbar.
    node.addEventListener('paste', event => {
      event.preventDefault(); document.execCommand('insertText', false, event.clipboardData.getData('text/plain'));
    });
    node.addEventListener('drop', event => event.preventDefault());
    return node;
  }
  function newBlock(type) {
    const common = {type, tone:'plain', align:'left', width:'normal'};
    return Object.assign(common, {
      category:{category:config.categories[0]?.slug || '',count:4},
      heading:{text:t('heading_hint'),level:'h2'}, text:{html:'',foreground:''},
      list:{items:[t('item')],ordered:false}, table:{rows:[[t('heading'),t('heading')],[t('item'),t('item')]],caption:''},
      image:{url:'',alt:'',caption:''},video:{url:'',alt:'',caption:''},button:{text:t('starter_button'),url:''},divider:{},
      quote:{text:t('quote_hint'),attribution:''},callout:{title:t('callout'),text:t('text_hint')},
      stats:{items:[{value:'100+',label:t('stat_label')}]},faq:{items:[{question:t('question'),answer:t('answer')}]},legacy_html:{html:''}
    }[type]);
  }
  function add(type) {
    if (blocks().length >= 80) return message(t('limit'), true);
    mutate(() => { const index = selected < 0 ? blocks().length : selected + 1; blocks().splice(index,0,newBlock(type)); selected = index; });
    canvas.children[selected]?.scrollIntoView({block:'nearest',behavior:'smooth'});
    canvas.children[selected]?.querySelector('[contenteditable],input')?.focus({preventScroll:true});
  }
  const symbols = {heading:'H',text:'¶',list:'☷',table:'▦',image:'▧',video:'▷',button:'↗',quote:'❝',callout:'!',stats:'№',faq:'?',divider:'―',category:'▤',legacy_html:'<>'};
  Object.keys(symbols).forEach(type => {
    const node = button('', () => add(type), 'builder-add-button');
    node.dataset.blockType = type;
    node.append(el('span','builder-block-symbol',symbols[type]),el('span','',t(type)));
    document.getElementById('builder-add-blocks').append(node);
  });
  function safeURL(value, media = false) {
    if (/[\s\x00-\x1f\x7f\\]/.test(value)) return '';
    if (value.startsWith('/') && !value.startsWith('//')) return !media || /^\/static\/uploads\/[\w.-]+$/.test(value) ? value : '';
    try { const url = new URL(value); return (media ? url.protocol === 'https:' : ['https:','http:'].includes(url.protocol)) && !url.username && !url.password ? value : ''; } catch { return ''; }
  }
  function videoURL(value) {
    value = safeURL(value,true); if (!value) return null;
    const url = new URL(value, location.origin), host = url.hostname;
    let id = '';
    if (['youtube.com','www.youtube.com','m.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com'].includes(host)) id = url.pathname === '/watch' ? url.searchParams.get('v') || '' : /^\/(embed|shorts)\//.test(url.pathname) ? url.pathname.split('/')[2] : '';
    if (host === 'youtu.be') id = url.pathname.slice(1);
    if (/^[\w-]{11}$/.test(id)) return {kind:'iframe',url:'https://www.youtube-nocookie.com/embed/'+id};
    if (['vimeo.com','www.vimeo.com','player.vimeo.com'].includes(host)) { id = url.pathname.split('/').filter(Boolean).pop(); if (/^\d{1,12}$/.test(id)) return {kind:'iframe',url:'https://player.vimeo.com/video/'+id}; }
    return /\.(mp4|webm|ogg)$/i.test(url.pathname) ? {kind:'video',url:value} : null;
  }
  async function upload(file, block, onUploaded = null) {
    if (!file) return;
    const limit = (block.type === 'image' ? 8 : 40) * 1024 * 1024;
    if (file.size > limit) return message(t('upload_error'),true);
    const data = new FormData();data.set('editor_token',config.token);data.set('homepage_mode','custom');data.set('kind',block.type);data.set('file',file);
    busy++;updateStatus();message(t('uploading'));
    try {
      const response = await fetch(endpoint+'/upload',{method:'POST',body:data});
      const result = await responseJSON(response); if (!response.ok) throw new Error(result.error || t('error'));
      if (onUploaded) onUploaded(result.url);
      else mutate(() => { block.url = result.url; });
      message('');
    } catch(error) { message(error.message || t('error'),true); }
    finally { busy--;updateStatus(); }
  }
  function inlineImages(editor, block) {
    const panel = el('details', 'builder-inline-images');
    panel.append(el('summary', '', t('inline_image')));
    const controls = el('div', 'builder-inline-image-controls');
    let selectedImage = null, insertionRange = null;
    const rememberRange = () => {
      const selection = window.getSelection();
      if (selection.rangeCount && editor.contains(selection.anchorNode) && editor.contains(selection.focusNode)) {
        insertionRange = selection.getRangeAt(0).cloneRange();
      }
    };
    ['keyup', 'mouseup', 'focusout'].forEach(event => editor.addEventListener(event, rememberRange));
    const inputField = (label, type = 'text') => {
      const wrapper = el('label', 'builder-field'), input = el('input');
      input.type = type; wrapper.append(el('span', '', label), input); controls.append(wrapper);
      return input;
    };
    const url = inputField(t('url')); url.placeholder = 'https://… /static/uploads/…';
    const alt = inputField(t('alt')); alt.maxLength = 500;
    const choose = (label, options, value) => {
      const wrapper = el('label', 'builder-field'), input = el('select');
      options.forEach(([key, text]) => input.add(new Option(text, key)));
      input.value = value; wrapper.append(el('span', '', label), input); controls.append(wrapper);
      return input;
    };
    const flow = choose(t('image_flow'), [['left', t('image_left')], ['right', t('image_right')], ['none', t('image_none')]], 'left');
    const width = choose(t('image_width'), ['25','40','50','100'].map(value => [value, value + '%']), '40');
    const file = inputField(t('upload'), 'file'); file.accept = 'image/png,image/jpeg,image/webp';
    file.addEventListener('change', () => upload(file.files[0], {type:'image'}, value => {
      if (!editor.isConnected) return;
      if (safeURL(value, true)) {
        url.value = value;
        insertImage(value);
      } else {
        message(t('invalid'), true);
      }
    }));
    const commit = action => {
      checkpoint(); action(); block.html = editor.innerHTML; checkpoint();
    };
    function insertImage(src) {
      commit(() => {
        const image = selectedImage && editor.contains(selectedImage) ? selectedImage : el('img');
        image.src = src; image.alt = alt.value;
        image.className = `rich-image rich-image-${flow.value} rich-image-width-${width.value}`;
        image.loading = 'lazy';
        if (!editor.contains(image)) {
          if (insertionRange && editor.contains(insertionRange.commonAncestorContainer)) {
            insertionRange.collapse(false); insertionRange.insertNode(image);
          } else editor.prepend(image);
        }
        selectedImage = image;
        insertionRange = document.createRange(); insertionRange.setStartAfter(image); insertionRange.collapse(true);
        editor.focus(); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(insertionRange);
      });
      remove.disabled = false; message('');
    }
    const apply = button(t('image_apply'), () => {
      const src = safeURL(url.value.trim(), true);
      if (!src) { message(t('invalid'), true); url.focus(); return; }
      insertImage(src);
    });
    const remove = button(t('image_remove'), () => {
      if (selectedImage && editor.contains(selectedImage)) commit(() => selectedImage.remove());
      selectedImage = null; remove.disabled = true; url.value = ''; alt.value = '';
    });
    remove.disabled = true;
    editor.addEventListener('click', event => {
      const image = event.target.closest('img');
      selectedImage = image && editor.contains(image) ? image : null;
      remove.disabled = !selectedImage;
      if (!selectedImage) return;
      url.value = image.getAttribute('src'); alt.value = image.alt;
      flow.value = ['left','right','none'].find(value => image.classList.contains('rich-image-' + value)) || 'none';
      width.value = ['25','40','50','100'].find(value => image.classList.contains('rich-image-width-' + value)) || '40';
      panel.open = true;
    });
    const actions = el('div', 'builder-actions'); actions.append(apply, remove);
    panel.append(controls, actions, el('p', 'builder-help', t('image_flow_help')));
    return panel;
  }
  function media(block, body) {
    if (block.type === 'image' && safeURL(block.url,true)) {
      const image = el('img');image.src = block.url;image.alt = block.alt;body.append(image);
    } else if (block.type === 'video' && videoURL(block.url)) {
      const source = videoURL(block.url); const node = el(source.kind); node.src=source.url;
      if (source.kind === 'video') {node.controls=true;node.preload='metadata';} else {node.title=block.alt || t('video');node.loading='lazy';node.allowFullscreen=true;}
      body.append(node);
    } else {body.append(el('div','builder-media-placeholder',symbols[block.type]+' '+t(block.type)));}
    const controls = el('div','builder-media-fields');
    const urlField = field(t('url'),block.url,value => {block.url=value;});
    urlField.querySelector('input').addEventListener('change',() => render());
    controls.append(urlField);
    const uploadField = el('label','builder-field');uploadField.append(el('span','',t('upload')));
    const file = el('input');file.type='file';file.accept=block.type==='image'?'image/png,image/jpeg,image/webp':'video/mp4,video/webm';
    file.addEventListener('change',()=>upload(file.files[0],block));
    if(block.type==='image' && block.url.startsWith('/static/uploads/')) controls.append(button(t('crop'),async()=>{
      const source=file.files[0] || block.url;
      if(!source)return;
      busy++;updateStatus();
      try { const cropped=await window.cropContentImage(source);if(cropped)await upload(cropped,block); }
      finally {busy--;updateStatus();}
    }));uploadField.append(file);controls.append(uploadField);
    controls.append(field(t('alt'),block.alt,value=>{block.alt=value;}),field(t('caption'),block.caption,value=>{block.caption=value;}));
    body.append(controls);if(block.type==='video')body.append(el('p','builder-help',t('video_help')));
  }
  function render() {
    canvas.replaceChildren();
    if (!blocks().length) { const empty = el('div','builder-empty');empty.append(el('span','builder-block-symbol','＋'),el('h2','',t('empty')),el('p','',t('add_help')));canvas.append(empty); }
    blocks().forEach((block,index) => {
      const card = el('section','builder-block'+(selected===index?' is-selected':''));
      card.addEventListener('focusin',() => { selected=index;canvas.querySelectorAll('.builder-block').forEach((n,i)=>n.classList.toggle('is-selected',i===index)); });
      const header=el('header','builder-block-header');header.append(el('strong','',String(index+1).padStart(2,'0')+' / '+t(block.type)));
      const actions=el('div','builder-block-actions');
      const up=button('↑',()=>mutate(()=>{[blocks()[index-1],blocks()[index]]=[blocks()[index],blocks()[index-1]];selected=index-1;}));up.title=t('up');up.setAttribute('aria-label',t('up'));up.disabled=index===0;
      const down=button('↓',()=>mutate(()=>{[blocks()[index+1],blocks()[index]]=[blocks()[index],blocks()[index+1]];selected=index+1;}));down.title=t('down');down.setAttribute('aria-label',t('down'));down.disabled=index===blocks().length-1;
      const copy=button(t('duplicate'),()=>{if(blocks().length>=80)return message(t('limit'),true);mutate(()=>{blocks().splice(index+1,0,structuredClone(block));selected=index+1;});});
      actions.append(up,down,copy,button(t('remove'),()=>mutate(()=>{blocks().splice(index,1);selected=Math.min(index,blocks().length-1);})));header.append(actions);card.append(header);
      const styles=el('div','builder-style-controls');
      for (const [key,values] of [['tone',['plain','soft','accent','dark','white','custom']],['align',['left','center','right']],['width',['normal','wide']]])styles.append(select(t(key),block[key],values.map(v=>[v,t(v)]),v=>{block[key]=v;}));
      // Text/color picker — always available for any block type
      if(block.type!=='divider'){
        const textColorPicker = field(t('color_selection'),block.foreground||'#17243b',v=>{block.foreground=v;card.querySelector('.custom-block').style.setProperty('--text-color',v);},'color');
        styles.append(textColorPicker);
      }
      if(block.tone==='custom') {
        const bgColor = field(t('color_selection'),block.background || '#ffffff',v=>{block.background=v;card.querySelector('.custom-block').style.backgroundColor=v;},'color');
        styles.append(bgColor);
      }
      if(block.type==='heading')styles.append(select(t('heading'),block.level,[['h1','H1'],['h2','H2'],['h3','H3']],v=>{block.level=v;}));
      card.append(styles);
      const body=el('div',`custom-block custom-${block.type} tone-${block.tone} align-${block.align} width-${block.width}`);
      if(block.tone==='custom') body.style.backgroundColor=block.background || '#ffffff';
      if(block.foreground) body.style.setProperty('--text-color',block.foreground);
      if(block.type==='category') {
        const options = config.categories.map(cat=>[cat.slug,cat.name]);
        if(!options.some(([slug])=>slug===block.category))options.unshift([block.category,block.category || '—']);
        body.append(select(t('category_source'),block.category,options,v=>{block.category=v;}));
        body.append(select(t('count'),String(block.count),Array.from({length:16},(_,i)=>[String(i+1),String(i+1)]),v=>{block.count=Number(v);}));
        body.append(el('p','builder-help',t('category_help')));
      }
      if(block.type==='heading')body.append(editable(block.level,block.text,t('heading_hint'),v=>{block.text=v;}));
      if(block.type==='legacy_html') {
        body.append(el('p','builder-help',t('legacy_help')));
        const source = el('textarea','builder-legacy-source');
        source.value = block.html; source.rows = 12; source.setAttribute('aria-label',t('legacy_html'));
        source.addEventListener('input',()=>{block.html=source.value;change();});
        body.append(source);
      }
      if(block.type==='text') {
        const editor=editable('div',block.html,t('text_hint'),v=>{block.html=v;},true);editor.classList.add('custom-rich-text');
        const toolbar=el('div','builder-rich-toolbar');
        for(const [command,key] of [['bold','bold'],['italic','italic'],['createLink','link'],['unlink','unlink']]){
          const tool=button(t(key),()=>{let value=null;if(command==='createLink'){value=prompt(t('url'));if(!value)return;if(!safeURL(value))return message(t('invalid'),true);}editor.focus();document.execCommand(command,false,value);block.html=editor.innerHTML;change();});
          tool.addEventListener('mousedown',e=>e.preventDefault());toolbar.append(tool);
        }
        body.append(toolbar,editor,inlineImages(editor,block));
      }
      if(block.type==='list') {
        const toggle=el('label','builder-ordered');const check=el('input');check.type='checkbox';check.checked=block.ordered;check.addEventListener('change',()=>mutate(()=>{block.ordered=check.checked;}));toggle.append(check,document.createTextNode(t('ordered')));body.append(toggle);
        const list=el(block.ordered?'ol':'ul');
        block.items.forEach((item,i)=>{const li=el('li');li.append(editable('span',item,t('item'),v=>{block.items[i]=v;}),button('×',()=>mutate(()=>block.items.splice(i,1))));li.lastChild.setAttribute('aria-label',t('remove'));list.append(li);});body.append(list,button(t('add_item'),()=>{if(block.items.length<100)mutate(()=>block.items.push(t('item')));}));
      }
      if(block.type==='table') {
        const wrap=el('div','custom-table-scroll'),table=el('table');
        block.rows.forEach((row,r)=>{const tr=el('tr');row.forEach((cell,c)=>{tr.append(editable(r===0?'th':'td',cell,t('item'),v=>{block.rows[r][c]=v;}));});table.append(tr);});wrap.append(table);body.append(wrap);
        const tools=el('div','builder-table-tools');
        tools.append(button(t('add_row'),()=>{if(block.rows.length<30)mutate(()=>block.rows.push(Array(block.rows[0]?.length||2).fill('')));}),button(t('add_column'),()=>{if((block.rows[0]?.length||0)<8)mutate(()=>block.rows.forEach(row=>row.push('')));}),button(t('remove_row'),()=>{if(block.rows.length>1)mutate(()=>block.rows.pop());}),button(t('remove_column'),()=>{if(block.rows[0]?.length>1)mutate(()=>block.rows.forEach(row=>row.pop()));}));body.append(tools,field(t('caption'),block.caption,v=>{block.caption=v;}));
      }
      if(['image','video'].includes(block.type))media(block,body);
      if(block.type==='button') {body.append(editable('span',block.text,t('button'),v=>{block.text=v;}));body.lastChild.classList.add('custom-button');body.append(field(t('url'),block.url,v=>{block.url=v;}));}
      if(block.type==='quote') {
        const quote=el('blockquote');
        quote.append(editable('p',block.text,t('quote_hint'),v=>{block.text=v;}));
        body.append(quote,field(t('attribution'),block.attribution,v=>{block.attribution=v;}));
      }
      if(block.type==='callout') {
        body.append(editable('h3',block.title,t('heading_hint'),v=>{block.title=v;}),
                    editable('p',block.text,t('text_hint'),v=>{block.text=v;}));
      }
      if(['stats','faq'].includes(block.type)) {
        const group=el('div',block.type==='stats'?'custom-stats-grid':'custom-faq-items');
        const keys=block.type==='stats'?['value','label']:['question','answer'];
        block.items.forEach((item,i)=>{
          const row=el('div','builder-repeat-item');
          keys.forEach(key=>row.append(editable(key==='value'?'strong':'p',item[key],t(key==='label'?'stat_label':key),v=>{item[key]=v;})));
          row.append(button(t('remove'),()=>mutate(()=>block.items.splice(i,1))));group.append(row);
        });
        body.append(group,button(t('add_item'),()=>{
          const limit=block.type==='stats'?8:20;
          if(block.items.length<limit)mutate(()=>block.items.push(Object.fromEntries(keys.map(key=>[key,'']))));
        }));
      }
      if(block.type==='divider')body.append(el('hr'));
      card.append(body);canvas.append(card);
    });updateStatus();
  }
  document.getElementById('builder-language').addEventListener('change',event=>{checkpoint();language=event.target.value;selected=-1;document.querySelectorAll('[data-builder-language-fields]').forEach(node=>{node.hidden=node.dataset.builderLanguageFields!==language;});render();});
  document.getElementById('builder-undo').addEventListener('click',()=>{checkpoint();if(cursor>0){documents=JSON.parse(history[--cursor]);selected=-1;render();}});
  document.getElementById('builder-redo').addEventListener('click',()=>{if(cursor<history.length-1){documents=JSON.parse(history[++cursor]);selected=-1;render();}});
  document.getElementById('builder-starter').addEventListener('click',()=>{
    if(blocks().length>77)return message(t('limit'),true);
    mutate(()=>{blocks().push({...newBlock('heading'),text:t('starter_title'),level:'h1',tone:'soft',align:'center',width:'wide'},{...newBlock('text'),html:el('p','',t('starter_text')).outerHTML,align:'center'},{...newBlock('button'),text:t('starter_button'),url:'/contact',align:'center'});});
  });
  function formData() { const data=new FormData();data.set('editor_token',config.token);data.set('content_language_code',config.languageCode);data.set('homepage_mode','custom');return data; }
  saveButton.addEventListener('click',async()=>{
    if(busy) return;
    if(details && !details.checkValidity()) {
      const invalid = details.querySelector(':invalid');
      const panel = invalid?.closest('[data-builder-language-fields]');
      if(panel) { const picker=document.getElementById('builder-language');picker.value=panel.dataset.builderLanguageFields;picker.dispatchEvent(new Event('change')); }
      details.reportValidity(); return;
    }
    checkpoint();const data=formData(),sent=snapshot(),sentMetadata=metadata();
    if(details) new FormData(details).forEach((value,key)=>data.set(key,value));
    Object.entries(documents).forEach(([suffix,doc])=>data.set(contentPrefix+suffix,JSON.stringify(doc)));
    busy++;updateStatus();message(t('saving'));
    try {const response=await fetch(endpoint,{method:'POST',body:data});const result=await responseJSON(response);if(!response.ok)throw new Error(result.error||t('error'));saved=sent;savedMetadata=sentMetadata;message(result.message);
      if(page === 'post' && result.endpoint){
        endpoint=result.endpoint;details.action=endpoint;historyReplace(endpoint);
        if(metadata() === sentMetadata) {
          document.dispatchEvent(new CustomEvent('content:image-saved', {detail:result.image_path}));
          savedMetadata=metadata();
        }
      }
      if(result.url && page === 'page'){const link=document.getElementById('page-public-link');link.href=result.url;link.hidden=false;}if(page === 'home') document.dispatchEvent(new CustomEvent('homepage:saved', {detail:'custom'}));}
    catch(error){message(error.message||t('error'),true);}finally{busy--;updateStatus();}
  });
  const dialog=document.getElementById('builder-preview-dialog'),frame=document.getElementById('builder-preview-frame');
  previewButton.addEventListener('click',async()=>{
    const data=formData();if(page==='post' && details)new FormData(details).forEach((value,key)=>{if(!(value instanceof File))data.set(key,value);});data.set('document',JSON.stringify(blocks()));busy++;updateStatus();
    const code=config.languages.find(item=>item.suffix===language).code;
    try {const response=await fetch(endpoint+'/preview?lang='+encodeURIComponent(code),{method:'POST',body:data});if(!response.ok){const result=await responseJSON(response);throw new Error(result.error||t('error'));}frame.srcdoc=await response.text();dialog.showModal();}
    catch(error){message(error.message||t('error'),true);}finally{busy--;updateStatus();}
  });
  document.querySelectorAll('[data-preview-width]').forEach(node=>node.addEventListener('click',()=>{frame.classList.toggle('is-mobile',node.dataset.previewWidth==='mobile');}));
  document.getElementById('builder-close-preview').addEventListener('click',()=>dialog.close());
  details?.addEventListener('input',updateStatus);
  details?.addEventListener('change',updateStatus);
  details?.addEventListener('submit',event=>{event.preventDefault();saveButton.click();});
  window.addEventListener('beforeunload',event=>{if(snapshot()!==saved || metadata()!==savedMetadata || busy){event.preventDefault();event.returnValue='';}});
  render();
})();
