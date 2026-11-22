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
  const saveDraftButton = document.getElementById('builder-save-draft');
  let forcedPostStatus = null;
  const previewButton = document.getElementById('builder-preview');
  const removeDialog = document.getElementById('builder-remove-dialog');
  const collapsedBlocks = new WeakSet();
  let pendingRemoval;
  document.getElementById('builder-cancel-remove').addEventListener('click',()=>removeDialog.close('cancel'));
  document.getElementById('builder-confirm-remove').addEventListener('click',()=>removeDialog.close('remove'));
  removeDialog.addEventListener('close',()=>{
    if (removeDialog.returnValue === 'remove') pendingRemoval?.();
    pendingRemoval=undefined;
  });
  const historyReplace = url => window.history.replaceState(null,'',url);
  const snapshot = () => JSON.stringify(documents);
  const blocks = () => documents[language];
  const blockCount = items => items.reduce((count, block) => count + 1 + blockCount(block.children || []), 0);
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
    if (saveDraftButton) saveDraftButton.disabled = busy > 0;
    canvas.inert = busy > 0;
    document.getElementById('builder-add-blocks').inert = busy > 0;
    document.getElementById('builder-section-presets').inert = busy > 0;
    document.getElementById('builder-language').disabled = busy > 0;
    document.getElementById('builder-undo').disabled ||= busy > 0;
    document.getElementById('builder-redo').disabled ||= busy > 0;
    document.getElementById('builder-starter').disabled = busy > 0;
    if (collapseAllButton) collapseAllButton.disabled=busy>0 || !blocks().length;
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
    // Filter pasted HTML before inserting it into the live document.
    node.addEventListener('paste', event => {
      event.preventDefault();
      const html = rich && event.clipboardData.getData('text/html');
      document.execCommand(html ? 'insertHTML' : 'insertText', false, html ? cleanRichPaste(html) : event.clipboardData.getData('text/plain'));
    });
    node.addEventListener('drop', event => event.preventDefault());
    return node;
  }
  function newBlock(type) {
    const common = {type, tone:'plain', align:'left', width:'normal'};
    return Object.assign(common, {
      section:{width:'wide',children:[],image:'',anchor:'',appearance:{}},
      category:{category:config.categories[0]?.slug || '',count:4},
      heading:{text:t('heading_hint'),level:'h2'}, text:{html:'',foreground:''},
      list:{items:[t('item')],ordered:false}, table:{rows:[[t('heading'),t('heading')],[t('item'),t('item')]],caption:''},
      image:{url:'',alt:'',caption:''},video:{url:'',alt:'',caption:''},button:{text:t('starter_button'),url:'',appearance:{icon:'none'}},icon_button:{text:'Home',url:'/',icon_name:'house',appearance:{variant:'solid'}},divider:{line_width:2,line_style:'single',line_color:'#a5b3be'},
      quote:{text:t('quote_hint'),attribution:''},callout:{title:t('callout'),text:t('text_hint')},
      stats:{items:[{value:'100+',label:t('stat_label')}]},team:{width:'wide',items:[{photo:'',name:'',title:'',shape:'rectangle',orientation:'landscape',fit:'cover',zoom:1,focal_x:50,focal_y:50}]},faq:{items:[{question:t('question'),answer:t('answer')}]},legacy_html:{html:''}
    }[type]);
  }
  function add(type) {
    if (blockCount(blocks()) >= 80) return message(t('limit'), true);
    mutate(() => { const index = selected < 0 ? blocks().length : selected + 1; blocks().splice(index,0,newBlock(type)); selected = index; });
    canvas.children[selected]?.scrollIntoView({block:'nearest',behavior:'smooth'});
    canvas.children[selected]?.querySelector('[contenteditable],input')?.focus({preventScroll:true});
  }
  function addSectionPreset(dark) {
    const section = {
      ...newBlock('section'),
      tone: dark ? 'dark' : 'soft',
      appearance:{
        layout:'split', surface:'full', min_height:560, content_width:1440, padding_y:88,
        gap:48, svg_pattern:dark ? 'ribbons' : 'grid', svg_opacity:dark ? 78 : 32, edge:'wave'
      },
      children:[
        {...newBlock('section'), children:[
          {...newBlock('heading'), level:blocks().length ? 'h2' : 'h1', text:t('starter_title'),
            appearance:{font_size:96,font_weight:'heavy'}},
          {...newBlock('text'), html:el('p','',t('starter_text')).outerHTML},
          {...newBlock('section'), appearance:{layout:'actions',gap:14}, children:[
            {...newBlock('button'), url:'/contact', appearance:{
              variant:'solid',radius:12,icon:'none'
            }},
            {...newBlock('button'), text:t('section_secondary_action'), url:'/about',
              appearance:{variant:'outline',radius:12,icon:'none'}}
          ]}
        ]},
        newBlock('image')
      ]
    };
    if (blockCount(blocks()) + blockCount([section]) > 80) return message(t('limit'),true);
    mutate(()=>{
      selected=selected < 0 ? blocks().length : selected+1;
      blocks().splice(selected,0,section);
    });
    canvas.children[selected]?.scrollIntoView({block:'nearest',behavior:'smooth'});
    canvas.children[selected]?.querySelector('.builder-hero-editor input')?.focus({preventScroll:true});
  }
  const symbols = {icon_button:'◎',section:'▥',heading:'H',text:'¶',list:'☷',table:'▦',image:'▧',video:'▷',button:'↗',quote:'❝',callout:'!',stats:'№',team:'♙',faq:'?',divider:'―',category:'▤',legacy_html:'<>'};
  Object.keys(symbols).forEach(type => {
    const node = button('', () => add(type), 'builder-add-button');
    node.dataset.blockType = type;
    node.append(el('span','builder-block-symbol',symbols[type]),el('span','',type==='icon_button'?'Icon Button':t(type)));
    document.getElementById('builder-add-blocks').append(node);
  });
  function addTwoColumnHero() {
    const makeColumn = (heading, text, url) => ({
      ...newBlock('section'),
      appearance:{layout:'stack', surface:'standard', gap:22, padding_y:12, padding_x:12},
      children:[
        {...newBlock('heading'), level:blocks().length ? 'h2' : 'h1', text:heading},
        {...newBlock('text'), html:el('p','',text).outerHTML},
        {...newBlock('button'), text:t('starter_button'), url}
      ]
    });
    const section = {
      ...newBlock('section'),
      tone:'soft',
      appearance:{layout:'two',surface:'full',content_width:1440,padding_y:72,gap:40,edge:'flat'},
      children:[
        makeColumn(t('two_column_first_heading'),t('starter_text'),'/contact'),
        makeColumn(t('two_column_second_heading'),t('starter_text'),'/about')
      ]
    };
    if (blockCount(blocks()) + blockCount([section]) > 80) return message(t('limit'),true);
    mutate(()=>{
      selected=selected<0 ? blocks().length : selected+1;
      blocks().splice(selected,0,section);
    });
    canvas.children[selected]?.scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  const presets = document.getElementById('builder-section-presets');
  for (const [theme,key] of [['dark','section_split_preset'],['two-column','two_column_hero'],['light','section_light_preset']]) {
    const preset=button('',()=>theme === 'two-column' ? addTwoColumnHero() : addSectionPreset(theme === 'dark'),'builder-preset');
    preset.dataset.theme=theme;
    const thumbnail=el('span','builder-preset-thumbnail');
    thumbnail.setAttribute('aria-hidden','true');
    thumbnail.append(el('span','builder-preset-copy'),el('span','builder-preset-visual'));
    preset.append(thumbnail,el('span','builder-preset-label',t(key)),el('span','builder-preset-add','+'));
    preset.lastChild.setAttribute('aria-hidden','true');
    presets.append(preset);
  }

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
    const limit = (block.type === 'image' ? 25 : 40) * 1024 * 1024;
    if (file.size > limit) return message(block.type === 'image'
      ? 'Image exceeds the 25 MB upload limit.' : 'Video exceeds the 40 MB upload limit.', true);
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
  function cleanRichPaste(html) {
    const template = document.createElement('template'); template.innerHTML = html;
    const allowed = new Set('strong b em i u s strike del ins sub sup mark small span a br p div img h1 h2 h3 h4 h5 h6 blockquote pre code kbd samp var abbr cite q hr ul ol li dl dt dd table caption thead tbody tfoot tr th td figure figcaption details summary'.split(' '));
    const clean = parent => {
      for (const node of [...parent.childNodes]) {
        if (node.nodeType === Node.COMMENT_NODE) { node.remove(); continue; }
        if (node.nodeType !== Node.ELEMENT_NODE) continue;
        const tag = node.localName;
        if (['script','style','iframe','object','svg','math','template','link','meta'].includes(tag)) { node.remove(); continue; }
        clean(node);
        if (!allowed.has(tag)) { node.replaceWith(...node.childNodes); continue; }
        for (const attribute of [...node.attributes]) {
          const {name,value} = attribute;
          if (['title','dir','colspan','rowspan','scope','start','value','alt'].includes(name)) continue;
          if (name === 'href' && tag === 'a' && (safeURL(value) || /^(#[A-Za-z][\w:.-]*|mailto:[^\s<>"\\]+|tel:[+0-9().-]+)$/.test(value))) continue;
          if (name === 'src' && tag === 'img' && safeURL(value,true)) continue;
          if (name === 'style') {
            const style = document.createElement('span').style;
            for (const key of ['text-align','color','background-color','font-size','font-weight','font-style','vertical-align','text-decoration','font-family','line-height','margin-left']) {
              const value = node.style.getPropertyValue(key);
              if (value && !/url|var\(|expression|[\\<>]/i.test(value)) style.setProperty(key,value);
            }
            node.setAttribute('style',style.cssText); continue;
          }
          node.removeAttribute(name);
        }
        if (tag === 'img') {
          if (!node.getAttribute('src')) node.remove();
          else node.className = 'rich-image rich-image-none rich-image-width-40';
        }
      }
    };
    clean(template.content); return template.innerHTML;
  }
  function richToolbar(editor, block) {
    const escaped = key => el('span', '', t(key)).innerHTML;
    const toolbar = el('div', 'builder-rich-toolbar');
    toolbar.setAttribute('role', 'group'); toolbar.setAttribute('aria-label', t('formatting'));
    let range = null;
    const remember = () => {
      const selection = window.getSelection();
      if (selection.rangeCount && editor.contains(selection.anchorNode) && editor.contains(selection.focusNode)) range = selection.getRangeAt(0).cloneRange();
    };
    ['keyup', 'mouseup', 'input', 'focusout'].forEach(event => editor.addEventListener(event, remember));
    const restore = () => {
      editor.focus();
      const selection = window.getSelection();
      if (!range || !editor.contains(range.commonAncestorContainer)) {
        range = document.createRange(); range.selectNodeContents(editor); range.collapse(false);
      }
      selection.removeAllRanges(); selection.addRange(range);
    };
    const commit = () => { block.html = editor.innerHTML; remember(); change(); };
    const command = (name, value = null) => {
      checkpoint(); restore(); document.execCommand('styleWithCSS', false, true);
      document.execCommand(name, false, value); commit();
    };
    const settings = el('div', 'builder-rich-settings');
    const tools = el('div', 'builder-rich-tools'); toolbar.append(settings, tools);
    const icons = {
      bold: '<path d="M6 4h7a4 4 0 0 1 0 8H6m0 0h8a4 4 0 0 1 0 8H6V4"/>',
      italic: '<path d="M10 4h10M4 20h10M15 4 9 20"/>',
      underline: '<path d="M6 3v7a6 6 0 0 0 12 0V3M4 21h16"/>',
      strikethrough: '<path d="M18 6c-2-4-12-3-12 2 0 5 12 3 12 8 0 5-10 6-13 2M3 12h18"/>',
      subscript: '<path d="m4 5 9 10m0-10L4 15m13 1c0-3 5-3 5 0 0 2-5 3-5 6h5"/>',
      superscript: '<path d="m4 9 9 10m0-10L4 19m13-16c0-3 5-3 5 0 0 2-5 3-5 6h5"/>',
      bullet_list: '<path d="M9 5h12M9 12h12M9 19h12"/><circle cx="3" cy="5" r="1"/><circle cx="3" cy="12" r="1"/><circle cx="3" cy="19" r="1"/>',
      ordered: '<path d="M10 5h11M10 12h11M10 19h11M3 2h1v6M2 8h4M2 15c0-3 4-3 4 0l-4 6h4"/>',
      indent: '<path d="M3 4h18M10 9h11M10 15h11M3 20h18m0-11 3 3-3 3"/>',
      outdent: '<path d="M3 4h18M10 9h11M10 15h11M3 20h18m3-11-3 3 3 3"/>',
      left: '<path d="M3 4h18M3 9h12M3 15h18M3 20h12"/>',
      center: '<path d="M3 4h18M6 9h12M3 15h18M6 20h12"/>',
      right: '<path d="M3 4h18M9 9h12M3 15h18M9 20h12"/>',
      justify: '<path d="M3 4h18M3 9h18M3 15h18M3 20h18"/>',
      clear_format: '<path d="M4 4h14M11 4 7 18m7-5 7 7m0-7-7 7"/>',
      link: '<path d="m10 7 3-3a5 5 0 0 1 7 7l-3 3m-3 3-3 3a5 5 0 0 1-7-7l3-3m1 6 8-8"/>',
      unlink: '<path d="m10 7 3-3a5 5 0 0 1 7 7l-2 2m-4 4-3 3a5 5 0 0 1-7-7l2-2M3 3l18 18"/>',
      inline_code: '<path d="m7 6-6 6 6 6m10-12 6 6-6 6M14 3l-4 18"/>',
      divider: '<path d="M3 12h18"/>',
      table: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
      add_row: '<path d="M3 3h18v10H3zM3 8h18M12 16v6M9 19h6"/>',
      add_column: '<path d="M3 3h10v18H3zM8 3v18M16 12h6M19 9v6"/>',
      remove_row: '<path d="M3 3h18v10H3zM3 8h18M9 19h6"/>',
      remove_column: '<path d="M3 3h10v18H3zM8 3v18M16 12h6"/>'
    };
    const groups = new Map();
    const groupFor = key => ['bullet_list','ordered','indent','outdent'].includes(key) ? 'list'
      : ['left','center','right','justify'].includes(key) ? 'align'
      : ['table','add_row','add_column','remove_row','remove_column'].includes(key) ? 'table'
      : ['link','unlink','inline_code','definition_list','disclosure','divider'].includes(key) ? 'add' : 'formatting';
    const add = (key, action) => {
      const tool = button(t(key), action); tool.title = t(key); tool.setAttribute('aria-label', t(key));
      if (icons[key]) {
        tool.classList.add('builder-icon-tool');
        tool.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'+icons[key]+'</svg>';
      }
      const keyGroup = groupFor(key);
      if (!groups.has(keyGroup)) {
        const group = el('div','builder-rich-group'); group.setAttribute('role','group'); group.setAttribute('aria-label',t(keyGroup));
        groups.set(keyGroup, group); tools.append(group);
      }
      tool.addEventListener('mousedown', event => { remember(); event.preventDefault(); }); groups.get(keyGroup).append(tool);
    };
    const choice = (key, options, action) => {
      const label = el('label', 'builder-rich-choice'); label.append(el('span', '', t(key)));
      const input = el('select'); options.forEach(([value, title]) => input.add(new Option(title, value)));
      input.addEventListener('change', () => action(input.value)); label.append(input); settings.append(label);
    };
    const wrap = tag => {
      checkpoint(); restore();
      const node = document.createElement(tag);
      node.append(range.extractContents());
      if (!node.hasChildNodes()) node.textContent = t('text_hint');
      range.insertNode(node); range.selectNodeContents(node); commit();
    };
    choice('paragraph', [['p', t('paragraph')], ...[1,2,3,4,5,6].map(n => ['h'+n, 'H'+n]), ['blockquote', t('quote')], ['pre', t('code_block')]], value => command('formatBlock', value));
    for (const [name,key] of [['bold','bold'],['italic','italic'],['underline','underline'],['strikeThrough','strikethrough'],['subscript','subscript'],['superscript','superscript'],['insertUnorderedList','bullet_list'],['insertOrderedList','ordered'],['indent','indent'],['outdent','outdent'],['justifyLeft','left'],['justifyCenter','center'],['justifyRight','right'],['justifyFull','justify'],['removeFormat','clear_format'],['unlink','unlink']]) add(key, () => command(name));
    add('link', () => {
      remember(); const value = prompt(t('url'));
      if (!value) return;
      if (!safeURL(value) && !/^(#[A-Za-z][\w:.-]*|mailto:[^\s<>"\\]+|tel:[+0-9().-]+)$/.test(value)) return message(t('invalid'), true);
      command('createLink', value);
    });
    add('inline_code', () => wrap('code'));
    choice('semantic', [['code',t('inline_code')],['mark',t('highlight')],['small',t('small_text')],['kbd',t('keyboard')],['abbr',t('abbreviation')],['cite',t('citation')]], value => {
      wrap(value);
      if (value === 'abbr') { const title = prompt(t('abbreviation')); if (title) { range.commonAncestorContainer.title=title; commit(); } }
    });
    add('definition_list', () => command('insertHTML', '<dl><dt>'+escaped('heading')+'</dt><dd>'+escaped('item')+'</dd></dl><p><br></p>'));
    add('disclosure', () => command('insertHTML', '<details open><summary>'+escaped('heading')+'</summary><p>'+escaped('item')+'</p></details><p><br></p>'));
    add('divider', () => command('insertHorizontalRule'));
    choice('font_family', [['sans-serif',t('sans_serif')],['serif',t('serif')],['monospace',t('monospace')]], value => command('fontName', value));
    choice('font_size', [12,14,16,18,20,24,32,48,72].map(n => [String(n), n+' px']), value => {
      checkpoint(); restore();
      const span = document.createElement('span'); span.style.fontSize = value+'px';
      span.append(range.extractContents()); if (!span.hasChildNodes()) span.textContent = t('text_hint');
      range.insertNode(span); range.selectNodeContents(span); commit();
    });
    for (const [key,name,value] of [['text_color','foreColor','#17243b'],['highlight','hiliteColor','#ffff00']]) {
      const label = el('label','builder-rich-choice'); label.append(el('span','',t(key)));
      const input = el('input'); input.type='color'; input.value=value;
      input.addEventListener('input', () => command(name,input.value)); label.append(input); settings.append(label);
    }
    choice('direction', [['auto',t('automatic')],['ltr','LTR'],['rtl','RTL']], value => {
      checkpoint(); restore();
      const node = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
      const paragraph = node.closest('p,div,h1,h2,h3,h4,h5,h6,li,blockquote,pre');
      if (paragraph && paragraph !== editor && editor.contains(paragraph)) paragraph.dir = value;
      else { const wrapper=document.createElement('div'); wrapper.dir=value; wrapper.append(...editor.childNodes); editor.append(wrapper); }
      commit();
    });
    add('table', () => {
      const rows = Number(prompt(t('table_rows'), '3')); if (!Number.isInteger(rows) || rows < 1 || rows > 30) return;
      const columns = Number(prompt(t('table_columns'), '3')); if (!Number.isInteger(columns) || columns < 1 || columns > 8) return;
      command('insertHTML', '<table><caption>'+escaped('caption')+'</caption><tbody>'+Array.from({length:rows}, (_,r) => '<tr>'+Array.from({length:columns}, () => r === 0 ? '<th scope="col">'+escaped('heading')+'</th>' : '<td>'+escaped('item')+'</td>').join('')+'</tr>').join('')+'</tbody></table><p><br></p>');
    });
    const tableAction = action => {
      checkpoint(); restore();
      const node = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
      const cell = node.closest('td,th'); if (!cell || !editor.contains(cell)) return;
      const table = cell.closest('table'); action(cell, table); commit();
    };
    add('add_row', () => tableAction((cell,table) => {
      if (table.rows.length >= 30) return;
      const row = table.insertRow(cell.parentElement.rowIndex+1);
      Array.from(cell.parentElement.cells).forEach(() => row.insertCell().append(document.createElement('br')));
    }));
    add('add_column', () => tableAction((cell,table) => {
      if (cell.parentElement.cells.length >= 8) return;
      const index=cell.cellIndex;
      Array.from(table.rows).forEach(row => { const next=document.createElement(row.rowIndex === 0 ? 'th' : 'td'); next.append(document.createElement('br')); row.insertBefore(next,row.cells[index+1] || null); });
    }));
    add('remove_row', () => tableAction((cell,table) => { table.deleteRow(cell.parentElement.rowIndex); if (!table.rows.length) table.remove(); }));
    add('remove_column', () => tableAction((cell,table) => { const index=cell.cellIndex; Array.from(table.rows).forEach(row => { if(row.cells[index]) row.deleteCell(index); }); if (!table.rows[0]?.cells.length) table.remove(); }));
    return toolbar;
  }

  function inlineImages(editor, block) {
    const panel = el('details', 'builder-inline-images');
    const summary = el('summary', '', t('inline_image'));
    const badge = el('span', 'builder-image-pending-badge', t('image_pending_short')); badge.hidden = true;
    summary.append(badge); panel.append(summary);
    const feedback = el('p', 'builder-image-feedback', t('image_apply_help'));
    feedback.setAttribute('role', 'status'); feedback.setAttribute('aria-live', 'polite');
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
    const values = () => JSON.stringify([url.value.trim(), alt.value, flow.value, width.value]);
    let appliedValues = values();
    const updatePending = (applied = false) => {
      const pending = values() !== appliedValues;
      panel.classList.toggle('has-pending-image', pending); badge.hidden = !pending;
      apply.disabled = !pending;
      apply.textContent = t(selectedImage ? 'image_update_action' : 'image_insert_action');
      feedback.textContent = t(pending ? 'image_pending_help' : applied ? 'image_applied_help' : 'image_apply_help');
    };
    [url, alt, flow, width].forEach(input => {
      input.addEventListener('input', () => updatePending());
      input.addEventListener('change', () => updatePending());
    });
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
      remove.disabled = false; appliedValues = values(); updatePending(true); message('');
    }
    const apply = button(t('image_apply'), () => {
      const src = safeURL(url.value.trim(), true);
      if (!src) { message(t('invalid'), true); url.focus(); return; }
      insertImage(src);
    });
    apply.classList.add('builder-image-apply');
    const remove = button(t('image_remove'), () => {
      if (selectedImage && editor.contains(selectedImage)) commit(() => selectedImage.remove());
      selectedImage = null; remove.disabled = true; url.value = ''; alt.value = '';
      appliedValues = values(); updatePending();
    });
    remove.disabled = true;
    editor.addEventListener('click', event => {
      const image = event.target.closest('img');
      if (!image || !editor.contains(image)) return;
      selectedImage = image && editor.contains(image) ? image : null;
      remove.disabled = !selectedImage;
      if (!selectedImage) return;
      url.value = image.getAttribute('src'); alt.value = image.alt;
      flow.value = ['left','right','none'].find(value => image.classList.contains('rich-image-' + value)) || 'none';
      width.value = ['25','40','50','100'].find(value => image.classList.contains('rich-image-width-' + value)) || '40';
      appliedValues = values(); updatePending();
      panel.open = true;
    });
    const actions = el('div', 'builder-actions'); actions.append(apply, remove);
    panel.append(controls, feedback, actions, el('p', 'builder-help', t('image_flow_help')));
    updatePending();
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
  const sectionControls = [
    ['section_layout', [
      ['layout',['stack','two','split','reverse_split','three','six','actions']],['surface',['standard','full']],
      ['vertical_align',['start','center','end']],['content_width',360,1920,1240],['min_height',0,1200,0],
      ['padding_y',0,200,68],['padding_x',0,120,42],['gap',0,100,24],['radius',0,120,20]
    ]],
    ['section_background', [
      ['background_fit',['cover','contain']],['background_position',['center','left','right','top','bottom']],
      ['overlay_color','color','#131c32'],['overlay_opacity',0,100,0],
      ['edge',['flat','wave']],
      ['edge_color','color','#f7f8f5']
    ]]
  ];
  const appearanceFields = {
    section: [...sectionControls.flatMap(([, fields]) => fields),
      ['svg_pattern'],['svg_primary'],['svg_secondary'],['svg_opacity']],
    heading: [['font_size',18,160,48],['font_weight',['normal','bold','heavy']],['accent_color','color','#2563eb'],['accent_opacity',0,100,100],['accent_style',['color_only','underline']],['accent_new_line',['no','yes']]],
    list: [['font_size',10,72,18],['item_gap',0,48,8]],
    table: [['cell_background','color','#ffffff'],['cell_color','color','#17243b'],['header_background','color','#eef2ff'],['header_color','color','#17243b']],
    icon_button: [['button_background','color',config.design?.accent || '#286e7a'],['button_hover','color',config.design?.navHover || '#20435b'],['button_text','color','#ffffff'],['button_hover_text','color','#ffffff'],['font_size',10,48,20],['variant',['solid','outline','ghost','text_link','underlined']],['width_mode',['auto','full','custom']],['width_px',40,1200,64],['height',24,240,52],['radius',0,120,12],['target',['same_tab','new_tab']]],
    button: [['button_background','color',config.design?.accent || '#286e7a'],['button_hover','color',config.design?.navHover || '#20435b'],['button_text','color','#ffffff'],['button_hover_text','color','#ffffff'],['font_size',10,48,16],['width_mode',['auto','full','custom']],['width_px',40,1200,240],['height',24,240,56],['radius',0,120,100],
      ['variant',['solid','outline','ghost','text_link','underlined']],['icon',['none','arrow','external']],
      ['border_width',0,8,0],['border_color','color','#2563eb'],['padding_x',0,96,24],['padding_y',0,48,16],['target',['same_tab','new_tab']]],
    quote: [['font_size',12,72,28],['attribution_size',10,36,14],['quote_color','color','#17243b'],['attribution_color','color','#65738a'],['border_color','color','#65738a'],['border_width',0,12,3],['font_style',['normal','italic']]],
    stats: [['value_color','color','#17243b'],['label_color','color','#65738a'],['card_background','color','#ffffff'],['value_size',16,120,48],['label_size',10,48,14],['columns',1,4,3],['gap',0,64,24],['padding',0,64,0]]
  };
  function applyAppearance(block, body) {
    for (const [key] of appearanceFields[block.type] || []) {
      const value = block.appearance?.[key];
      const variable = '--block-'+key.replaceAll('_','-');
      if (value === undefined) body.style.removeProperty(variable);
      else {
        const unit = key.endsWith('_opacity') ? '%' : typeof value === 'number' && key !== 'columns' ? 'px' : '';
        body.style.setProperty(variable, value + unit);
      }
    }
    body.dataset.buttonWidth = block.appearance?.width_mode || 'auto';
    body.dataset.statsColumns = block.appearance?.columns ?? '';
    const appearance = block.appearance || {};
    if (block.type === 'heading') {
      body.dataset.headingWeight = appearance.font_weight || '';
      body.dataset.accent = appearance.accent_style || '';
      body.dataset.accentNewLine = appearance.accent_new_line || 'no';
      body.toggleAttribute('data-heading-size', appearance.font_size !== undefined);
    }
    if (block.type === 'button' || block.type === 'icon_button') {
      body.dataset.variant = appearance.variant || 'solid';
      const icon = body.querySelector('.builder-button-icon');
      if (icon) {
        icon.hidden = !appearance.icon || appearance.icon === 'none';
        icon.textContent = appearance.icon === 'arrow' ? '→' : '↗';
      }
    }
    if (block.type === 'section') {
      Object.assign(body.dataset, {
        layout:appearance.layout || 'stack', surface:appearance.surface || 'standard',
        vertical:appearance.vertical_align || 'center', fit:appearance.background_fit || 'cover',
        position:appearance.background_position || 'center', edge:appearance.edge || 'flat'
      });
      const currentArt = body.querySelector(':scope > .section-art');
      const pattern = appearance.svg_pattern || 'none';
      if (currentArt?.dataset.pattern !== pattern) {
        currentArt?.remove();
        const art = document.getElementById('builder-art-'+pattern)?.content.firstElementChild.cloneNode(true);
        if (art) { art.dataset.pattern = pattern; body.prepend(art); }
      }
      const edge = body.querySelector(':scope > .section-edge');
      if (edge) edge.hidden = appearance.edge !== 'wave';
    }
  }
  function appearanceControls(block, body, definitions = appearanceFields[block.type]) {
    if (!definitions) return null;
    const panel=el('div','builder-style-controls builder-appearance-controls');
    const set = (key,value) => {
      block.appearance ||= {};
      if (value === undefined) delete block.appearance[key]; else block.appearance[key]=value;
      applyAppearance(block,body); change();
    };
    definitions.forEach(([key,kind,max,fallback]) => {
      const label=el('label','builder-select');
      label.append(el('span','',t(key)+(typeof kind === 'number' && key !== 'columns' ? (key.endsWith('_opacity') ? ' (%)' : ' (px)') : '')));
      let input;
      if(Array.isArray(kind)) {
        input=el('select'); input.add(new Option(t('theme_default'),''));
        kind.forEach(value=>input.add(new Option(t('option_'+value),value)));
        input.value=block.appearance?.[key] ?? '';
        input.addEventListener('change',()=>set(key,input.value || undefined));
      } else {
        input=el('input');
        input.type=key==='accent_opacity'?'range':kind==='color'?'color':'number';
        if(kind==='color') input.value=block.appearance?.[key] || max;
        else { input.min=kind;input.max=max;input.step=1;input.placeholder=String(fallback);input.value=block.appearance?.[key] ?? (key==='accent_opacity'?100:''); }
        const percentage=key==='accent_opacity' ? el('output','builder-color-opacity-value',String(input.value)+'%') : null;
        input.addEventListener('input',()=>{
          if(input.value==='') set(key,undefined);
          else if(input.checkValidity()) set(key,kind==='color'?input.value:Number(input.value));
          if(percentage)percentage.textContent=String(input.value)+'%';
        });
        if(percentage)label.append(percentage);
      }
      label.append(input);panel.append(label);
    });
    panel.append(button(t('reset_appearance'), () => mutate(() => {
      if (!block.appearance) return;
      definitions.forEach(([key]) => { delete block.appearance[key]; });
    })));
    return panel;
  }
  function syncCellStyles(block) {
    if(block.cell_styles) block.cell_styles=block.rows.map((row,r)=>row.map((_,c)=>block.cell_styles[r]?.[c] || {}));
  }
  function tableCellControls(block, table) {
    const panel=el('div','builder-style-controls builder-cell-controls');
    const hint=el('span','builder-help',t('cell_select_help')); panel.append(hint);
    let selectedCell=null;
    const inputs={};
    for(const [key,label,defaultColor] of [['background','cell_background','#ffffff'],['color','cell_color','#17243b']]) {
      const wrapper=el('label','builder-select'); wrapper.append(el('span','',t(label)));
      const input=el('input');input.type='color';input.value=defaultColor;input.disabled=true;
      input.addEventListener('input',()=>{
        if(!selectedCell) return;
        block.cell_styles ||= block.rows.map(row=>row.map(()=>({})));
        const r=selectedCell.parentElement.rowIndex,c=selectedCell.cellIndex;
        block.cell_styles[r][c][key]=input.value;
        selectedCell.style.setProperty(key==='background'?'background-color':'color',input.value);change();
      }); inputs[key]=input; wrapper.append(input);panel.append(wrapper);
    }
    const reset=button(t('reset_cell'),()=>{
      if(!selectedCell) return;
      if(block.cell_styles) block.cell_styles[selectedCell.parentElement.rowIndex][selectedCell.cellIndex]={};
      selectedCell.style.removeProperty('background-color');selectedCell.style.removeProperty('color');change();
    });reset.disabled=true;panel.append(reset);
    table.addEventListener('focusin',event=>{
      const cell=event.target.closest('td,th');if(!cell) return;
      selectedCell=cell;
      table.querySelectorAll('.is-active-cell').forEach(node=>node.classList.remove('is-active-cell'));cell.classList.add('is-active-cell');
      const r=cell.parentElement.rowIndex,c=cell.cellIndex;
      hint.textContent=t('selected_cell')+' '+(r+1)+' / '+(c+1);
      for(const [key,input] of Object.entries(inputs)) {input.disabled=false;input.value=block.cell_styles?.[r]?.[c]?.[key] || (key==='background'?'#ffffff':'#17243b');}
      reset.disabled=false;
    });
    return panel;
  }

  function sectionSvgGenerator(block, body) {
    const panel = el('details','builder-section-panel builder-svg-generator');
    panel.open = true;
    panel.append(el('summary','',t('section_svg_title')));
    const preview = el('div','builder-svg-preview');
    const settings = el('div','builder-svg-controls');
    const note = el('p','builder-help');
    note.setAttribute('role','status');
    const actions = el('div','builder-actions');
    const draft = {
      svg_pattern: block.appearance?.svg_pattern === 'none' ? 'ribbons' : block.appearance?.svg_pattern || 'ribbons',
      svg_primary: block.appearance?.svg_primary || '#7466ef',
      svg_secondary: block.appearance?.svg_secondary || '#5ed8ce',
      svg_opacity: block.appearance?.svg_opacity ?? 100
    };
    const redraw = () => {
      const template = document.getElementById('builder-art-'+draft.svg_pattern);
      preview.replaceChildren(template.content.firstElementChild.cloneNode(true));
      preview.style.setProperty('--block-svg-primary',draft.svg_primary);
      preview.style.setProperty('--block-svg-secondary',draft.svg_secondary);
      preview.style.setProperty('--block-svg-opacity',draft.svg_opacity + '%');
      preview.style.backgroundColor = getComputedStyle(body).backgroundColor;
      note.textContent = block.svg_url && Object.keys(draft).every(key=>block.appearance?.[key] === draft[key])
        ? t('section_svg_saved') : t('section_svg_preview_help');
    };
    const patternField = el('label','builder-select');
    patternField.append(el('span','',t('svg_pattern')));
    const pattern = el('select');
    for (const name of ['ribbons','waves','grid']) pattern.add(new Option(t('option_'+name),name));
    pattern.value = draft.svg_pattern;
    pattern.addEventListener('change',()=>{ draft.svg_pattern=pattern.value; redraw(); });
    patternField.append(pattern); settings.append(patternField);
    for (const key of ['svg_primary','svg_secondary']) {
      settings.append(field(t(key),draft[key],value=>{ draft[key]=value; redraw(); },'color'));
    }
    const opacityField = el('label','builder-select');
    opacityField.append(el('span','',t('svg_opacity')));
    const opacity = el('input');
    opacity.type='range'; opacity.min='0'; opacity.max='100'; opacity.value=String(draft.svg_opacity);
    opacity.addEventListener('input',()=>{ draft.svg_opacity=Number(opacity.value); redraw(); });
    opacityField.append(opacity); settings.append(opacityField);

    const save = button(t('section_svg_save'),async()=>{
      const payload = new FormData();
      payload.set('editor_token',config.token);
      for (const [key,value] of Object.entries(draft)) payload.set(key,String(value));
      busy++; updateStatus(); note.textContent=t('section_svg_saving');
      try {
        const response = await fetch('/admin/section-svg',{method:'POST',body:payload});
        const result = await responseJSON(response);
        if (!response.ok || !result.url) throw new Error(result.error || t('section_svg_error'));
        checkpoint();
        block.svg_url=result.url;
        block.appearance={...block.appearance,...draft};
        applyAppearance(block,body);
        checkpoint();
        remove.disabled=false;
        redraw();
      } catch (error) {
        note.textContent=error.message || t('section_svg_error');
      } finally {
        busy--; updateStatus();
      }
    },'settings-primary');
    const remove = button(t('section_svg_remove'),()=>{
      checkpoint();
      delete block.svg_url;
      block.appearance={...block.appearance,svg_pattern:'none'};
      applyAppearance(block,body);
      checkpoint();
      remove.disabled=true;
      redraw();
    },'settings-secondary');
    remove.disabled = !block.appearance?.svg_pattern || block.appearance.svg_pattern === 'none';
    actions.append(save,remove);
    panel.append(preview,settings,actions,note);
    requestAnimationFrame(redraw);
    return panel;
  }

  const advancedHeroes = new WeakSet();

  function heroContent(block) {
    if (block.type !== 'section' || block.children.length !== 2) return null;
    const [copy,image] = block.children;
    if (copy.type !== 'section' || image.type !== 'image' || copy.children.length !== 3) return null;
    const [heading,text,actions] = copy.children;
    if (heading.type !== 'heading' || text.type !== 'text' || actions.type !== 'section' ||
        actions.children.length !== 2 || actions.children.some(action=>action.type !== 'button')) return null;
    return {heading,text,image,actions:actions.children};
  }

  function editHero(hero) {
    const editor=el('div','builder-hero-editor');
    const group = label => {
      const panel=el('fieldset','builder-hero-group');
      panel.append(el('legend','',t(label))); editor.append(panel);
      return panel;
    };
    const copy=group('hero_copy_fields');
    const textLabel=el('span','builder-hero-label',t('text'));
    const description=editable('div',hero.text.html,t('text'),value=>{hero.text.html=value;},true);
    description.classList.add('builder-hero-description');
    copy.append(
      field(t('heading'),hero.heading.text,value=>{hero.heading.text=value;}),
      field(t('heading_accent'),hero.heading.accent,value=>{hero.heading.accent=value;}),
      textLabel,description
    );
    hero.actions.forEach((action,index)=>{
      const controls=group(index ? 'hero_secondary_button' : 'hero_primary_button');
      controls.append(field(t('hero_button_label'),action.text,value=>{action.text=value;}),
                      field(t('url'),action.url,value=>{action.url=value.trim();}));
    });
    const image=group('hero_visual');
    image.append(el('p','builder-help',t('hero_image_optional')));
    media(hero.image,image);
    return editor;
  }

  function sectionEditor(block, body, card, depth, hero) {
    if (safeURL(block.image, true)) {
      const image = el('img','section-image'); image.src = block.image; image.alt = '';
      body.append(image);
    }
    body.append(el('div','section-overlay'));
    body.append(document.getElementById('builder-section-edge').content.firstElementChild.cloneNode(true));
    const tools = el('div','builder-section-settings');
    const layout = el('details','builder-section-panel');
    layout.append(el('summary','',t('section_layout')), appearanceControls(block, body, sectionControls[0][1]));
    layout.append(field(t('section_anchor'),block.anchor,value=>{block.anchor=value.trim();}));
    const background = el('details','builder-section-panel');
    background.append(el('summary','',t('section_background')), appearanceControls(block, body, sectionControls[1][1]));
    const mediaFields = el('div','builder-media-fields');
    const urlField = field(t('section_image'),block.image,value=>{block.image=value.trim();});
    urlField.querySelector('input').addEventListener('change',()=>{
      const image = body.querySelector(':scope > .section-image');
      const url = safeURL(block.image,true);
      if (!url) { image?.remove(); return; }
      const preview = image || el('img','section-image');
      preview.src=url; preview.alt='';
      if (!image) body.prepend(preview);
    });
    const uploadField=el('label','builder-field');
    const file=el('input'); file.type='file'; file.accept='image/png,image/jpeg,image/webp';
    file.addEventListener('change',()=>upload(file.files[0],{type:'image'},url=>{
      block.image=url; urlField.querySelector('input').value=url;
      urlField.querySelector('input').dispatchEvent(new Event('change'));
      checkpoint();
    }));
    uploadField.append(el('span','',t('upload')),file);
    mediaFields.append(urlField,uploadField);
    background.append(mediaFields);
    const generator = sectionSvgGenerator(block,body);
    generator.open = depth === 0 && !hero;
    tools.append(layout,background,generator);
    if (hero) card.append(editHero(hero));
    card.append(tools);
    const content = el('div','section-content builder-section-content');

    const addControls = el('div','builder-section-add-controls');
    const addLabel = el('label','builder-section-add-label');
    addLabel.append(el('span','',t('section_add')));
    const add = el('select','builder-section-add-select');
    add.setAttribute('aria-label',t('section_add'));
    add.add(new Option(t('section_add_placeholder'),''));
    for (const kind of Object.keys(symbols)) {
      if (kind !== 'section') add.add(new Option(t(kind),kind));
    }
    add.addEventListener('change',()=>{
      if (!add.value) return;
      const kind = add.value; add.value = '';
      if (blockCount(blocks()) >= 80) return message(t('limit'),true);
      mutate(()=>block.children.push(newBlock(kind)));
    });
    addLabel.append(add);
    addControls.append(addLabel);
    // Section nesting is supported by the validator to a maximum depth of three.
    if (depth < 2) {
      const addSection = button('+ '+t('section_add_section'),()=>{
        if (blockCount(blocks()) >= 80) return message(t('limit'),true);
        mutate(()=>block.children.push(newBlock('section')));
      },'builder-section-add-button');
      addControls.append(addSection);
    }
    if (hero) {
      const advanced=el('details','builder-section-panel builder-hero-advanced');
      advanced.append(el('summary','',t('hero_advanced')),content,addControls);
      advanced.open=advancedHeroes.has(block);
      const syncMode=()=>{
        const editor=card.querySelector(':scope > .builder-hero-editor');
        editor.hidden=advanced.open;
        content.replaceChildren();
        if (advanced.open) {
          advancedHeroes.add(block);
          renderBlocks(block.children,content,depth+1);
        } else {
          advancedHeroes.delete(block);
          const updated=heroContent(block);
          if (updated) editor.replaceWith(editHero(updated));
        }
      };
      card.querySelector(':scope > .builder-hero-editor').hidden=advanced.open;
      if (advanced.open) renderBlocks(block.children,content,depth+1);
      advanced.addEventListener('toggle',syncMode);
      body.append(advanced);
    } else {
      renderBlocks(block.children,content,depth+1);
      body.append(content,addControls);
    }
  }

  function render() {
    canvas.replaceChildren();
    if (!blocks().length) { const empty = el('div','builder-empty');empty.append(el('span','builder-block-symbol','＋'),el('h2','',t('empty')),el('p','',t('add_help')));canvas.append(empty); }
    renderBlocks(blocks(),canvas,0);
    updateStatus();
    updateCollapseAll();
  }

  function renderBlocks(items, container, depth) {
    items.forEach((block,index) => {
      const card = el('section','builder-block'+(!depth && selected===index?' is-selected':''));
      if (!depth) card.addEventListener('focusin',() => {
        selected=index;
        Array.from(canvas.children).forEach((node,i)=>node.classList.toggle('is-selected',i===index));
      });
      const hero=heroContent(block);
      const label=String(index+1).padStart(2,'0')+' / '+(block.type==='icon_button'?'Icon Button':t(hero ? 'hero_section' : block.type));
      const header=el('header','builder-block-header');
      const toggle=button('',()=>{
        if (collapsedBlocks.has(block)) collapsedBlocks.delete(block);
        else collapsedBlocks.add(block);
        showBlockState();
      },'builder-block-toggle');
      const chevron=el('span','builder-block-chevron');
      chevron.setAttribute('aria-hidden','true');
      toggle.append(chevron,el('strong','',label));
      const showBlockState=()=>{
        const expanded=!collapsedBlocks.has(block);
        toggle.setAttribute('aria-expanded',String(expanded));
        card.classList.toggle('is-collapsed',!expanded);
      };
      showBlockState();
      header.append(toggle);
      const actions=el('div','builder-block-actions');
      const move = direction => mutate(()=>{
        [items[index+direction],items[index]]=[items[index],items[index+direction]];
        if (!depth) selected=index+direction;
      });
      const up=button('↑',()=>move(-1));up.title=t('up');up.setAttribute('aria-label',t('up'));up.disabled=index===0;
      const down=button('↓',()=>move(1));down.title=t('down');down.setAttribute('aria-label',t('down'));down.disabled=index===items.length-1;
      const copy=button(t('duplicate'),()=>{
        if(blockCount(blocks())+blockCount([block])>80) return message(t('limit'),true);
        mutate(()=>{
          const duplicate=structuredClone(block);
          const clearAnchors = item => { if (item.type === 'section') { item.anchor=''; item.children.forEach(clearAnchors); } };
          clearAnchors(duplicate);
          items.splice(index+1,0,duplicate);
          if (!depth) selected=index+1;
        });
      });
      if (hero) actions.append(button(t('preview'),()=>previewButton.click()));
      const remove=button(t('remove'),()=>{
        pendingRemoval=()=>{
          mutate(()=>{
            items.splice(index,1);
            if (!depth) selected=Math.min(index,items.length-1);
          });
          const card = canvas.children[Math.max(selected,0)];
          (card?.querySelector('.builder-block-toggle') || document.querySelector('#builder-add-blocks button'))?.focus();
        };
        removeDialog.returnValue='cancel';
        document.getElementById('builder-remove-name').textContent=label;
        removeDialog.showModal();
      });
      actions.append(up,down,copy,remove);
      header.append(actions); card.append(header);
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
      if (block.type === 'section') sectionEditor(block,body,card,depth,hero);
      else {
        const appearance=appearanceControls(block,body);if(appearance)card.append(appearance);
      }
      if(block.type==='category') {
        const options = config.categories.map(cat=>[cat.slug,cat.name]);
        if(!options.some(([slug])=>slug===block.category))options.unshift([block.category,block.category || '—']);
        body.append(select(t('category_source'),block.category,options,v=>{block.category=v;}));
        body.append(select(t('count'),String(block.count),Array.from({length:16},(_,i)=>[String(i+1),String(i+1)]),v=>{block.count=Number(v);}));
        body.append(el('p','builder-help',t('category_help')));
      }
      if (block.type==='heading') {
        const heading=el(block.level);
        const accent=el('span','section-heading-accent',block.accent || '');
        const highlightedText=editable('span',block.text,t('heading_hint'),v=>{block.text=v;});
        const space=el('span','section-heading-accent-gap',' ');
        heading.append(highlightedText,space,accent);
        body.append(heading,field(t('heading_accent'),block.accent,value=>{block.accent=value;accent.textContent=value;}));
      }
      if(block.type==='legacy_html') {
        body.append(el('p','builder-help',t('legacy_help')));
        const source = el('textarea','builder-legacy-source');
        source.value = block.html; source.rows = 12; source.setAttribute('aria-label',t('legacy_html'));
        source.addEventListener('input',()=>{block.html=source.value;change();});
        body.append(source);
      }
      let imageControls = null;
      if(block.type==='text') {
        const editor=editable('div',block.html,t('text_hint'),v=>{block.html=v;},true);editor.classList.add('custom-rich-text');
        const toolbar=richToolbar(editor,block);
        card.append(toolbar); body.append(editor); imageControls=inlineImages(editor,block);
      }
      if(block.type==='list') {
        const toggle=el('label','builder-ordered');const check=el('input');check.type='checkbox';check.checked=block.ordered;check.addEventListener('change',()=>mutate(()=>{block.ordered=check.checked;}));toggle.append(check,document.createTextNode(t('ordered')));body.append(toggle);
        const list=el(block.ordered?'ol':'ul');
        block.items.forEach((item,i)=>{const li=el('li');li.append(editable('span',item,t('item'),v=>{block.items[i]=v;}),button('×',()=>mutate(()=>block.items.splice(i,1))));li.lastChild.setAttribute('aria-label',t('remove'));list.append(li);});body.append(list,button(t('add_item'),()=>{if(block.items.length<100)mutate(()=>block.items.push(t('item')));}));
      }
      if(block.type==='table') {
        const wrap=el('div','custom-table-scroll'),table=el('table');
        block.rows.forEach((row,r)=>{const tr=el('tr');row.forEach((cell,c)=>{const node=editable(r===0?'th':'td',cell,t('item'),v=>{block.rows[r][c]=v;});const style=block.cell_styles?.[r]?.[c];if(style?.background)node.style.backgroundColor=style.background;if(style?.color)node.style.color=style.color;tr.append(node);});table.append(tr);});wrap.append(table);body.append(tableCellControls(block,table),wrap);
        const tools=el('div','builder-table-tools');
        tools.append(button(t('add_row'),()=>{if(block.rows.length<30)mutate(()=>{block.rows.push(Array(block.rows[0]?.length||2).fill(''));syncCellStyles(block);});}),button(t('add_column'),()=>{if((block.rows[0]?.length||0)<8)mutate(()=>{block.rows.forEach(row=>row.push(''));syncCellStyles(block);});}),button(t('remove_row'),()=>{if(block.rows.length>1)mutate(()=>{block.rows.pop();syncCellStyles(block);});}),button(t('remove_column'),()=>{if(block.rows[0]?.length>1)mutate(()=>{block.rows.forEach(row=>row.pop());syncCellStyles(block);});}));body.append(tools,field(t('caption'),block.caption,v=>{block.caption=v;}));
      }
      if(['image','video'].includes(block.type))media(block,body);
      if (block.type==='button') {
        const preview=el('span','custom-button');
        const icon=el('span','builder-button-icon'); icon.setAttribute('aria-hidden','true');
        preview.append(editable('span',block.text,t('button'),v=>{block.text=v;}),icon);
        body.append(preview,field(t('url'),block.url,v=>{block.url=v;}));
      }
      if(block.type==='icon_button') {
        const names=['house','arrow-right','arrow-left','arrow-up-right','envelope','telephone','search','download','share','link-45deg','github','linkedin','instagram','youtube','heart','star','plus-lg','chevron-right','geo-alt','calendar','file-earmark-text','book','chat-dots','globe','people','graph-up','gear','play-fill','camera','image','info-circle','question-circle'];
        const preview=el('span','custom-button custom-icon-button');
        const glyph=el('i','bi bi-'+(block.icon_name || 'house'));glyph.setAttribute('aria-hidden','true');preview.append(glyph);
        body.append(preview);
        body.append(select('Icon',block.icon_name || 'house',names.map(name=>[name,name.replaceAll('-',' ')]),value=>{block.icon_name=value;glyph.className='bi bi-'+value;}));
        body.append(field('Accessible label',block.text || 'Home',value=>{block.text=value;}));
        body.append(field(t('url'),block.url,value=>{block.url=value;}));
      }
      if(block.type==='quote') {
        const quote=el('blockquote');
        quote.append(editable('p',block.text,t('quote_hint'),v=>{block.text=v;}));
        const figure=el('figure');figure.append(quote,editable('figcaption',block.attribution,t('attribution'),v=>{block.attribution=v;}));body.append(figure);
      }
      if(block.type==='callout') {
        body.append(editable('h3',block.title,t('heading_hint'),v=>{block.title=v;}),
                    editable('p',block.text,t('text_hint'),v=>{block.text=v;}));
      }
      if(block.type==='team') {
        const group=el('div','custom-team-grid builder-team-grid');
        block.items.forEach((item,i)=>{
          const row=el('div','builder-repeat-item builder-team-member');
          const portrait=el('div','builder-team-portrait');
          portrait.dataset.shape=item.shape || 'rectangle';
          portrait.dataset.orientation=item.orientation || 'landscape';
          portrait.setAttribute('aria-label',t('team_drag_help'));
          const image=el('img');
          const cropX=()=>Number.isFinite(item.focal_x)?item.focal_x:50;
          const cropY=()=>Number.isFinite(item.focal_y)?item.focal_y:50;
          const cropZoom=()=>Number.isFinite(item.zoom)?item.zoom:1;
          const updateCrop=()=>{
            if(!image.parentElement)return;
            image.style.objectFit=item.fit||'cover';
            // Keep the frame fixed while the photo moves inside it.
            // The object-position moves the fitted source image; the transform
            // adds predictable, bounded panning when zoomed in.
            const zoom=cropZoom();
            const offsetX=(50-cropX())*(zoom-1)/zoom;
            const offsetY=(50-cropY())*(zoom-1)/zoom;
            image.style.objectPosition=`${cropX()}% ${cropY()}%`;
            image.style.transformOrigin='center center';
            image.style.transform=`translate(${offsetX}%, ${offsetY}%) scale(${zoom})`;
          };
          if(safeURL(item.photo||'',true)){
            image.src=item.photo;image.alt='';
            portrait.append(image);
            updateCrop();
          } else portrait.append(el('span','builder-team-photo-placeholder','＋'));
          const controls=el('div','builder-team-controls');
          controls.append(
            field(t('team_name'),item.name||'',value=>{item.name=value;}),
            field(t('team_title'),item.title||'',value=>{item.title=value;}),
            field(t('team_photo'),item.photo||'',value=>{item.photo=value.trim();})
          );
          const uploader=el('label','builder-field');
          uploader.append(el('span','',t('upload')));
          const file=el('input');file.type='file';file.accept='image/png,image/jpeg,image/webp';
          file.addEventListener('change',()=>upload(file.files[0],{type:'image'},url=>{
            mutate(()=>{item.photo=url;item.zoom=1;item.focal_x=50;item.focal_y=50;});
          }));
          uploader.append(file);controls.append(uploader);
          controls.append(select(t('team_shape'),item.shape||'rectangle',[
            ['rectangle',t('team_rectangle')],['circle',t('team_circle')]
          ],value=>{item.shape=value;}));
          controls.append(select(t('team_orientation'),item.orientation||'landscape',[
            ['landscape',t('team_landscape')],['portrait',t('team_portrait')]
          ],value=>{item.orientation=value;}));

          const cropControls=el('div','builder-team-crop-controls');
          cropControls.append(select(t('team_fit'),item.fit||'cover',[
            ['cover',t('team_fit_cover')],['contain',t('team_fit_contain')]
          ],value=>{item.fit=value;}));
          const zoomLabel=el('label','builder-team-zoom');
          zoomLabel.append(el('span','',t('team_zoom')));
          const zoomSlider=el('input');
          zoomSlider.type='range';zoomSlider.min='1';zoomSlider.max='3';zoomSlider.step='0.05';zoomSlider.value=String(cropZoom());
          const zoomValue=el('output','',Math.round(cropZoom()*100)+'%');
          zoomSlider.addEventListener('input',()=>{
            item.zoom=Number(zoomSlider.value);
            zoomValue.textContent=Math.round(item.zoom*100)+'%';
            updateCrop();change();
          });
          zoomLabel.append(zoomSlider,zoomValue);
          const resetCrop=button(t('team_reset_crop'),()=>mutate(()=>{
            item.zoom=1;item.focal_x=50;item.focal_y=50;
          }));
          cropControls.append(zoomLabel,resetCrop,el('p','builder-help',t('team_drag_help')));
          controls.append(cropControls);

          if(image.parentElement){
            let pointer=null;
            portrait.addEventListener('pointerdown',event=>{
              if(event.button!==0)return;
              event.preventDefault();
              pointer={id:event.pointerId,x:event.clientX,y:event.clientY,
                       originX:cropX(),originY:cropY()};
              portrait.setPointerCapture(event.pointerId);
            });
            portrait.addEventListener('pointermove',event=>{
              if(!pointer||event.pointerId!==pointer.id)return;
              const width=portrait.clientWidth||1,height=portrait.clientHeight||1;
              const zoom=cropZoom();
              // Dragging right/down should move the image right/down.
              // A zoomed image needs a larger focal change per pixel.
              const factor=Math.max(1,zoom/(Math.max(zoom-1,0.15)));
              item.focal_x=Math.max(0,Math.min(100,Math.round((pointer.originX-(event.clientX-pointer.x)/width*100*factor)*100)/100));
              item.focal_y=Math.max(0,Math.min(100,Math.round((pointer.originY-(event.clientY-pointer.y)/height*100*factor)*100)/100));
              updateCrop();change();
            });
            const stop=event=>{if(pointer&&pointer.id===event.pointerId){pointer=null;checkpoint();}};
            portrait.addEventListener('pointerup',stop);
            portrait.addEventListener('pointercancel',stop);
            portrait.addEventListener('lostpointercapture',()=>{pointer=null;});
          }
          const ordering=el('div','builder-team-order');
          const up=button('↑',()=>mutate(()=>{
            [block.items[i-1],block.items[i]]=[block.items[i],block.items[i-1]];
          }));
          up.disabled=i===0;up.title=t('up');up.setAttribute('aria-label',t('up'));
          const down=button('↓',()=>mutate(()=>{
            [block.items[i],block.items[i+1]]=[block.items[i+1],block.items[i]];
          }));
          down.disabled=i===block.items.length-1;down.title=t('down');down.setAttribute('aria-label',t('down'));
          ordering.append(up,down,button(t('remove'),()=>mutate(()=>block.items.splice(i,1))));
          row.append(portrait,controls,ordering);
          group.append(row);
        });
        body.append(group,button(t('add_item'),()=>{
          if(block.items.length<8)mutate(()=>block.items.push({photo:'',name:'',title:'',shape:'rectangle',orientation:'landscape',fit:'cover',zoom:1,focal_x:50,focal_y:50}));
        }));
      }
      if(['stats','faq'].includes(block.type)) {
        const group=el('div',block.type==='stats'?'custom-stats-grid':'custom-faq-items');
        const keys=block.type==='stats'?['value','label']:['question','answer'];
        block.items.forEach((item,i)=>{
          const row=el('div','builder-repeat-item');
          keys.forEach(key=>{const itemNode=editable(key==='value'?'strong':'p',item[key],t(key==='label'?'stat_label':key),v=>{item[key]=v;});if(block.type==='stats')itemNode.classList.add('custom-stat-'+key);row.append(itemNode);});
          row.append(button(t('remove'),()=>mutate(()=>block.items.splice(i,1))));group.append(row);
        });
        body.append(group,button(t('add_item'),()=>{
          const limit=block.type==='stats'?8:20;
          if(block.items.length<limit)mutate(()=>block.items.push(Object.fromEntries(keys.map(key=>[key,'']))));
        }));
      }
      if(block.type==='divider') {
        const settings=el('div','builder-divider-controls');
        const visual=el('div','builder-divider-line');
        const styleName=()=>block.line_style||'single';
        const draw=()=>{
          visual.replaceChildren();
          visual.style.setProperty('--divider-width',(block.line_width||2)+'px');
          visual.style.setProperty('--divider-color',block.line_color||'#a5b3be');
          visual.className='builder-divider-line style-'+styleName();
          if(['wave','wave-tight','zigzag'].includes(styleName())) {
            const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
            svg.setAttribute('viewBox','0 0 1200 48');
            svg.setAttribute('preserveAspectRatio','none');
            svg.setAttribute('aria-hidden','true');
            const path=document.createElementNS('http://www.w3.org/2000/svg','path');
            const pieces=['M 0 24'];
            if(styleName()==='wave'){
              for(let x=0;x<1200;x+=80)
                pieces.push(`C ${x+20} 2 ${x+20} 2 ${x+40} 24 S ${x+60} 46 ${x+80} 24`);
            } else if(styleName()==='wave-tight'){
              for(let x=0;x<1200;x+=40)
                pieces.push(`Q ${x+10} 4 ${x+20} 24 T ${x+40} 24`);
            } else {
              for(let x=0;x<1200;x+=48)
                pieces.push(`L ${x+24} 5 L ${x+48} 24`);
            }
            path.setAttribute('d',pieces.join(' '));
            path.setAttribute('fill','none');
            path.setAttribute('stroke','var(--divider-color)');
            path.setAttribute('stroke-width','var(--divider-width)');
            path.setAttribute('vector-effect','non-scaling-stroke');
            path.setAttribute('stroke-linecap','round');
            path.setAttribute('stroke-linejoin','round');
            svg.append(path); visual.append(svg);
          } else visual.append(el('hr'));
        };
        const widthLabel=el('label','builder-field');
        widthLabel.append(el('span','',t('divider_line_width')));
        const widthInput=el('input');
        widthInput.type='number';widthInput.min='2';widthInput.max='20';widthInput.step='1';
        widthInput.value=String(block.line_width||2);
        widthInput.addEventListener('change',()=>{
          block.line_width=Math.max(2,Math.min(20,Math.round(Number(widthInput.value)||2)));
          widthInput.value=String(block.line_width);
          draw();change();
        });
        widthLabel.append(widthInput);
        const styleLabel=el('label','builder-select');
        styleLabel.append(el('span','',t('divider_line_style')));
        const styleInput=el('select');
        for(const [key,label] of [
          ['single','divider_single'],['dashed','divider_dashed'],
          ['dotted','divider_dotted'],['wave','divider_wave'],
          ['wave-tight','divider_wave_tight'],['zigzag','divider_zigzag']
        ]){const option=new Option(t(label),key);styleInput.add(option);}
        styleInput.value=styleName();
        styleInput.addEventListener('change',()=>{
          block.line_style=styleInput.value;draw();change();
        });
        styleLabel.append(styleInput);
        const colorLabel=el('label','builder-field');
        colorLabel.append(el('span','',t('divider_line_color')));
        const colorInput=el('input');colorInput.type='color';
        colorInput.value=block.line_color||'#a5b3be';
        colorInput.addEventListener('input',()=>{
          block.line_color=colorInput.value;draw();change();
        });
        colorLabel.append(colorInput);
        settings.append(widthLabel,styleLabel,colorLabel);
        body.append(settings,visual);
        draw();
      }
      applyAppearance(block,body);
      card.append(body); if(imageControls) card.append(imageControls); container.append(card);
    });
  }
  const collapseAllButton=document.getElementById('builder-collapse-all');
  const allBlocks=(items)=>items.flatMap(block=>[block,...allBlocks(block.children || [])]);
  const updateCollapseAll=()=>{
    if (!collapseAllButton) return;
    const every=allBlocks(blocks());
    const collapsed=every.length>0 && every.every(block=>collapsedBlocks.has(block));
    collapseAllButton.textContent=collapsed?'Expand All':'Collapse All';
    collapseAllButton.setAttribute('aria-expanded',String(!collapsed));
    collapseAllButton.disabled=busy>0 || every.length===0;
  };
  collapseAllButton?.addEventListener('click',()=>{
    const every=allBlocks(blocks());
    const shouldCollapse=!every.every(block=>collapsedBlocks.has(block));
    every.forEach(block=>shouldCollapse?collapsedBlocks.add(block):collapsedBlocks.delete(block));
    render();
  });
  document.getElementById('builder-language').addEventListener('change',event=>{checkpoint();language=event.target.value;selected=-1;document.querySelectorAll('[data-builder-language-fields]').forEach(node=>{node.hidden=node.dataset.builderLanguageFields!==language;});render();});
  document.getElementById('builder-undo').addEventListener('click',()=>{checkpoint();if(cursor>0){documents=JSON.parse(history[--cursor]);selected=-1;render();}});
  document.getElementById('builder-redo').addEventListener('click',()=>{if(cursor<history.length-1){documents=JSON.parse(history[++cursor]);selected=-1;render();}});
  // Page layout library. Each card inserts validated, fully editable existing blocks.
  const gallery=document.getElementById('page-layout-gallery');
  if (gallery) {
    const h=(text,level='h2')=>({...newBlock('heading'),text,level});
    const p=text=>({...newBlock('text'),html:el('p','',text).outerHTML});
    const action=(text,url)=>({...newBlock('button'),text,url,appearance:{icon:'none'}});
    const section=(children,layout='stack',tone='plain')=>({...newBlock('section'),tone,appearance:{layout,surface:'standard',gap:24,padding_y:36},children});
    const picture=()=>({...newBlock('image'),alt:'Add an image',url:''});
    const layouts=[
      ['Editorial Story','A prominent headline, text and supporting image',()=>[h('The story begins here','h1'),p('Introduce the main idea behind your story.'),picture(),h('A closer look'),p('Share the context, analysis and key findings.'),action('Learn more','/contact')]],
      ['Research Project','Overview, method, findings and next steps',()=>[h('Research project','h1'),p('Summarize the research question and why it matters.'),section([h('Research objectives'),p('Describe the objectives and scope.')],'two'),h('Methodology'),p('Describe methods, sources and analytical procedures.'),h('Findings'),picture(),action('Get in touch','/contact')]],
      ['Academic Profile','Biography, research interests and contact',()=>[h('Researcher profile','h1'),section([picture(),section([h('About'),p('Brief academic biography and research focus.'),action('Contact','/contact')])],'two'),h('Research interests'),{...newBlock('list'),items:['Communication','Digital humanities','Computational methods']}]],
      ['Project Showcase','Visual introduction, highlights and projects',()=>[section([h('Explore our work','h1'),p('A collection of ongoing and completed projects.'),action('View projects','/projects')],'split','soft'),section([picture(),picture(),picture()],'three'),h('Our approach'),p('The methods and questions driving our research.')]],
      ['Landing Page','Hero, benefits, call to action and FAQ',()=>[section([h('Ideas deserve a home.','h1'),p('Explain the value of your work in one clear sentence.'),action('Get started','/contact')],'stack','soft'),section([h('Why it matters'),p('Describe your goals and intended audience.')],'two'),{...newBlock('faq'),items:[{question:'How does it work?',answer:'Add your answer here.'}]}]],
      ['Publication','Abstract, article sections and references',()=>[h('Publication title','h1'),p('Authors · Year · Publication'),h('Abstract'),p('Summarize the main contribution.'),h('Introduction'),p('Provide context and theoretical background.'),h('Methods'),p('Describe the research design.'),h('Results'),p('Explain the findings.'),h('References'),p('List cited works here.')]],
      ['Team & Lab','Mission, team cards and collaboration',()=>[h('Meet our team','h1'),p('Introduce your research group and its mission.'),{...newBlock('team'),items:[{photo:'',name:'Team member',title:'Researcher',shape:'rectangle',orientation:'portrait',fit:'cover',zoom:1,focal_x:50,focal_y:50}]},h('Our mission'),p('What brings the group together?'),action('Collaborate with us','/contact')]],
      ['Minimal Portfolio','Simple introduction, gallery and contact',()=>[h('Selected work','h1'),p('A concise introduction to your portfolio.'),section([picture(),picture()],'two'),h('What I do'),p('Describe your work and expertise.'),action('Contact','/contact')]],
      ['FriPeri — Full Landing','A complete FriPeri introduction, features, workflow and FAQ',()=>[
        {...section([h('Ideas deserve a home.','h1'),p('Meet FriPeri: a flexible publishing framework for pages, posts and stories. Design, organize and publish content with an approachable visual editor.'),section([action('Discover FriPeri','/about'),action('Get in touch','/contact')],'actions')],'split','soft'),appearance:{layout:'split',surface:'full',gap:36,padding_y:88,content_width:1440,edge:'wave',svg_pattern:'ribbons',svg_opacity:38}},
        section([h('Build a website that feels like yours'),p('Start with a ready-to-edit page layout, customize individual blocks and create a look that fits your story.')]),
        section([
          section([h('Visual page builder','h3'),p('Compose pages from headings, text, images and flexible content sections.')]),
          section([h('Color templates','h3'),p('Explore coordinated palettes and fine-tune the colors of your website.')]),
          section([h('Organized publishing','h3'),p('Manage pages, categories and posts from one place.')])
        ],'three','soft'),
        section([section([h('Your content, your layout'),p('Mix media and text, tailor the appearance of each section and preview your changes.'),action('Explore more','/about')]),section([picture()])],'two'),
        section([h('How it works'),section([h('1. Choose a layout','h3'),p('Begin with a page template or a blank canvas.')],'stack'),section([h('2. Make it yours','h3'),p('Adjust the design, add media and edit each block.')],'stack'),section([h('3. Publish','h3'),p('Preview your work, then publish when you are ready.')],'stack')],'stack','soft'),
        section([h('Made for stories worth sharing'),p('Publish research updates, project pages, personal writing and more.'),picture()]),
        h('Frequently asked questions'),
        {...newBlock('faq'),items:[
          {question:'Can I customize the colors?',answer:'Yes. Choose a color template in Design, then edit individual colors as needed.'},
          {question:'Can I edit a page after publishing?',answer:'Yes. Return to the visual editor to update blocks and publish your changes.'},
          {question:'Can I build a page without coding?',answer:'Yes. Arrange the available content blocks directly in the editor.'}
        ]},
        section([h('Ready to create?'),p('Bring your ideas, research and stories together in one place.'),action('Contact us','/contact')],'stack','soft')
      ]],
      ['Event & Workshop','A workshop announcement, program, speakers and registration',()=>[
        section([h('Join our upcoming event','h1'),p('Add the date, venue and a brief invitation to your workshop.'),action('Register interest','/contact')],'stack','soft'),
        h('What to expect'),p('Introduce the event, who it is for and what participants will learn.'),
        section([section([h('Session 1','h3'),p('Opening talk and introduction.')]),section([h('Session 2','h3'),p('Hands-on activities and discussion.')]),section([h('Session 3','h3'),p('Questions and closing.')])],'three'),
        h('Speakers'),{...newBlock('team'),items:[{photo:'',name:'Speaker name',title:'Role or affiliation',shape:'rectangle',orientation:'portrait',fit:'cover',zoom:1,focal_x:50,focal_y:50}]},
        h('Event details'),p('Add time, location, accessibility and participation information.'),action('Ask a question','/contact')
      ]],
      ['Services & Solutions','Offerings, benefits, process and a contact call to action',()=>[
        section([h('Solutions built around your needs','h1'),p('Introduce your expertise and explain the outcomes you help visitors achieve.'),action('Start a conversation','/contact')],'split','soft'),
        h('What we offer'),
        section([section([h('Consulting','h3'),p('Explain the problems you help solve.')]),section([h('Analysis','h3'),p('Describe your analytical methods and deliverables.')]),section([h('Training','h3'),p('Outline workshops or knowledge-sharing activities.')])],'three'),
        h('How we work'),{...newBlock('list'),items:['Understand the question and goals','Choose the right approach','Deliver clear, actionable outcomes']},
        section([h('Let us talk about your project'),p('Share your goals and find out how we could collaborate.'),action('Contact','/contact')],'stack','soft')
      ]],
      ['Resources & Knowledge Hub','Curated guides, learning paths, downloads and FAQs',()=>[
        section([h('Explore our resources','h1'),p('A home for guides, methods, practical notes and useful materials.')],'stack','soft'),
        h('Start learning'),
        section([section([h('Getting started','h3'),p('Add an introductory guide and a link to its full page.'),action('Read guide','/about')]),section([h('Methods','h3'),p('Introduce your methodological resources.'),action('Learn more','/about')]),section([h('Tools','h3'),p('Showcase utilities and reusable materials.'),action('Explore tools','/about')])],'three'),
        h('Featured resources'),section([picture(),section([h('Resource spotlight','h3'),p('Highlight an especially useful publication, dataset or learning resource.')])],'two'),
        h('Frequently asked questions'),
        {...newBlock('faq'),items:[{question:'Where should I begin?',answer:'Choose a topic above and follow its introductory guide.'}]},
        action('Ask us','/contact')
      ]]
    ];
    layouts.forEach(([name,description,build],i)=>{
      const item=button('',()=>{},'page-layout-tile');
      item.dataset.layoutIndex=String(i);
      const sketch=el('span','page-layout-sketch sketch-'+i);
      for(let k=0;k<4;k++)sketch.append(el('i'));
      item.append(sketch,el('strong','',name),el('small','',description));
      item.addEventListener('click',()=>{
        if(blocks().length && !window.confirm('Replace the current page blocks with '+name+'? You can undo this change.'))return;
        const next=build();
        if(blockCount(next)>80)return message(t('limit'),true);
        mutate(()=>{blocks().splice(0,blocks().length,...next);selected=-1;});
        document.getElementById('page-layout-notice').textContent=name+' is ready. Edit the blocks below or select Preview.';
        document.querySelector('.builder-workspace')?.scrollIntoView({block:'start',behavior:'smooth'});
      });
      gallery.append(item);
    });
  }
  document.getElementById('builder-starter')?.addEventListener('click',()=>{
    if(blockCount(blocks())>77)return message(t('limit'),true);
    mutate(()=>{blocks().push({...newBlock('heading'),text:t('starter_title'),level:'h1',tone:'soft',align:'center',width:'wide'},{...newBlock('text'),html:el('p','',t('starter_text')).outerHTML,align:'center'},{...newBlock('button'),text:t('starter_button'),url:'/contact',align:'center'});});
  });
  function formData() { const data=new FormData();data.set('editor_token',config.token);data.set('content_language_code',config.languageCode);data.set('homepage_mode','custom');return data; }
  saveDraftButton?.addEventListener('click', () => {
    forcedPostStatus = 'draft';
    saveButton.click();
  });
  saveButton.addEventListener('click',async()=>{
    if(busy) return;
    if (page === 'post' && details) {
      const statusField = details.querySelector('[name="status"]');
      if (statusField) {
        statusField.value = forcedPostStatus || 'published';
        statusField.dispatchEvent(new Event('change', {bubbles: true}));
      }
      forcedPostStatus = null;
    }
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
