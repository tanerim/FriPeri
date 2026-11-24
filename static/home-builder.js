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
    const starterButton=document.getElementById('builder-starter');
    if(starterButton)starterButton.disabled=busy>0;
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
      section:{width:'wide',children:[],image:'',anchor:'',appearance:{surface:'full',height_mode:'viewport',vertical_align:'center',layout:'stack',content_width:1240}},
      category:{category:config.categories[0]?.slug || '',count:4},
      heading:{text:t('heading_hint'),level:'h2'}, text:{html:'',foreground:''},
      list:{items:[t('item')],ordered:false}, table:{rows:[[t('heading'),t('heading')],[t('item'),t('item')]],caption:''},
      image:{url:'',alt:'',caption:'',link_url:'',link_target:'same_tab'},video:{url:'',alt:'',caption:''},button:{text:t('starter_button'),url:'',appearance:{icon:'none',variant:'plain',hover_effect:'none'}},icon:{icon_name:'star',icon_label:'',appearance:{icon_size:48,background_mode:'none'}},brand_logo:{width:'wide'},icon_button:{text:'Home',url:'/',icon_name:'house',appearance:{variant:'solid'}},divider:{line_width:1,line_style:'single',line_color:'#a5b3be',appearance:{padding_top:36,padding_bottom:36}},
      quote:{text:t('quote_hint'),attribution:''},callout:{title:t('callout'),text:t('text_hint'),image_url:'',image_alt:''},
      stats:{items:[{value:'100+',label:t('stat_label')}]},team:{width:'wide',appearance:{direction:'vertical',style:'classic',columns:3,photo_width:180,gap:24},items:[{photo:'',name:'',title:'',bio:'',shape:'rectangle',orientation:'portrait',fit:'cover',zoom:1,focal_x:50,focal_y:50}]},faq:{items:[{question:t('question'),answer:t('answer')}]},legacy_html:{html:''}
    }[type]);
  }
  function add(type) {
    if (blockCount(blocks()) >= 80) return message(t('limit'), true);
    mutate(() => { const index = selected < 0 ? blocks().length : selected + 1; blocks().splice(index,0,newBlock(type)); selected = index; });
    canvas.children[selected]?.scrollIntoView({block:'nearest',behavior:'smooth'});
    canvas.children[selected]?.querySelector('[contenteditable],input')?.focus({preventScroll:true});
  }
  // Ready-to-edit section presets; all use the regular, validated block schema.
  const presetHeading=(title,level='h2')=>({
    ...newBlock('heading'),level,text:title,appearance:{font_weight:'heavy'}
  });
  const presetText=value=>({...newBlock('text'),html:el('p','',value).outerHTML});
  const presetButton=(text,url,variant='solid')=>({
    ...newBlock('button'),text,url,
    appearance:{variant,icon:'none',radius:12}
  });
  const presetSection=(children,layout='stack',tone='plain',appearance={})=>({
    ...newBlock('section'),tone,
    appearance:{layout,surface:'standard',gap:24,padding_y:20,...appearance},children
  });
  const insertSectionPreset=section=>{
    if(blockCount(blocks())+blockCount([section])>80)return message(t('limit'),true);
    mutate(()=>{
      selected=selected<0?blocks().length:selected+1;
      blocks().splice(selected,0,section);
    });
    canvas.children[selected]?.scrollIntoView({block:'nearest',behavior:'smooth'});
  };
  function makeHeroPreset(kind) {
    if(kind==='friperi') {
      const introduction=presetSection([
        {...presetHeading('Make space for your next idea.','h1'),
          accent:'Built with FriPeri.',
          appearance:{font_size:88,font_weight:'heavy',accent_color:'#6dd2d0',accent_style:'color_only'}},
        presetText('A beautiful home for your writing, projects and stories. Create, personalize and publish with FriPeri.'),
        presetSection([presetButton('Discover FriPeri','/about'),presetButton('Get in touch','/contact','outline')],'actions')
      ]);
      return {
        ...presetSection([introduction,newBlock('brand_logo')],'two','custom',{
          surface:'full',content_width:1280,padding_y:110,padding_x:30,gap:38,
          min_height:640,edge:'wave',edge_color:'#ffffff',
          landing_style:'hero',svg_pattern:'ribbons',svg_primary:'#7161bd',
          svg_secondary:'#6dd2d0',svg_opacity:72
        }),background:'#142e52',foreground:'#ffffff'
      };
    }
    if(kind==='designed') {
      const feature=(title,copy)=>presetSection([
        presetHeading(title,'h3'),presetText(copy)
      ],'stack','white',{padding_y:28,padding_x:24,gap:12,radius:22});
      return {
        ...presetSection([
          presetHeading('Designed for the way you create.'),
          presetText('Everything you need to turn a great idea into a distinctive website.'),
          presetSection([
            feature('Visual Page Builder','Bring your ideas to life with flexible sections and content blocks.'),
            feature('Color Templates','Build a consistent visual identity with curated palettes.'),
            feature('Organized Publishing','Keep pages, categories and posts organized in one place.'),
            feature('Media First','Make your content memorable with images and visual storytelling.'),
            feature('Flexible Layouts','Begin with a layout and adapt it to your project.'),
            feature('Publish Confidently','Preview your page and publish when it looks right.')
          ],'three','plain',{gap:20,padding_y:22})
        ],'stack','custom',{
          surface:'full',content_width:1280,padding_y:90,padding_x:30,
          gap:30,edge:'wave',edge_color:'#ffffff',landing_style:'features'
        }),background:'#f7f5ff',foreground:'#142e52'
      };
    }
    return {
      ...presetSection([
        presetHeading('For the curious. For the creative.'),
        presetText('Publish articles, research updates, portfolios, project pages and personal stories. Your content should shape the site — not the other way around.'),
        presetSection([presetButton('Start with an idea','/contact')],'actions')
      ],'stack','custom',{
        surface:'full',content_width:1100,padding_y:115,padding_x:30,
        gap:30,edge:'wave',edge_color:'#ffffff',
        landing_style:'contrast',svg_pattern:'waves',svg_primary:'#b5ecdd',
        svg_secondary:'#ffffff',svg_opacity:58
      }),background:'#6dd2d0',foreground:'#142e52'
    };
  }
  function makeTwoColumnPreset(kind) {
    const content=presetSection([
      presetHeading('Your story starts here'),
      presetText('Introduce your project, research or publication with a focused, readable paragraph.'),
      presetButton('Explore more','/about')
    ],'stack','plain',{padding_y:20,padding_x:20,gap:18});
    const secondary=presetSection([
      presetHeading('A second perspective'),
      presetText('Add another idea, a complementary description or useful background information.'),
      presetButton('Get in touch','/contact','outline')
    ],'stack','plain',{padding_y:20,padding_x:20,gap:18});
    const image={...newBlock('image'),alt:'Add a descriptive image'};
    const children=kind==='text-text'?[content,secondary]:
      kind==='image-text'?[image,content]:[content,image];
    return presetSection(children,'two','soft',{
      surface:'full',content_width:1280,padding_y:76,padding_x:30,
      gap:44,vertical_align:'center',edge:'flat'
    });
  }
  const symbols = {icon_button:'◎',icon:'✧',section:'▥',heading:'H',text:'¶',list:'☷',table:'▦',image:'▧',video:'▷',button:'↗',quote:'❝',callout:'!',stats:'№',team:'♙',faq:'?',divider:'―',category:'▤',legacy_html:'<>',brand_logo:'✦'};
  Object.keys(symbols).forEach(type => {
    const node = button('', () => add(type), 'builder-add-button');
    node.dataset.blockType = type;
    node.append(el('span','builder-block-symbol',symbols[type]),el('span','',type==='brand_logo'?'FriPeri Logo':type==='icon_button'?'Icon Button':type==='icon'?'Icon':t(type)));
    document.getElementById('builder-add-blocks').append(node);
  });
  const presets = document.getElementById('builder-section-presets');
  const sectionPresetOptions = [
    {id:'hero-friperi',title:'FriPeri Hero',hint:'Branded split hero with logo',create:()=>makeHeroPreset('friperi')},
    {id:'hero-features',title:'Feature Cards Hero',hint:'Designed for the way you create',create:()=>makeHeroPreset('designed')},
    {id:'hero-creative',title:'Creative Hero',hint:'For the curious. For the creative',create:()=>makeHeroPreset('curious')},
    {id:'two-text',title:'Two Column Text',hint:'Two balanced text columns',create:()=>makeTwoColumnPreset('text-text')},
    {id:'two-image-text',title:'Two Column Image + Text',hint:'Image on left, copy on right',create:()=>makeTwoColumnPreset('image-text')},
    {id:'two-text-image',title:'Two Column Text + Image',hint:'Copy on left, image on right',create:()=>makeTwoColumnPreset('text-image')}
  ];
  for(const option of sectionPresetOptions){
    const preset=button('',()=>insertSectionPreset(option.create()),'builder-preset');
    preset.dataset.theme=option.id;
    preset.title=option.hint;
    const thumbnail=el('span','builder-preset-thumbnail');
    thumbnail.setAttribute('aria-hidden','true');
    thumbnail.append(el('span','builder-preset-copy'),el('span','builder-preset-visual'));
    const copy=el('span','builder-preset-info');
    copy.append(el('span','builder-preset-label',option.title),el('small','builder-preset-hint',option.hint));
    preset.append(thumbnail,copy,el('span','builder-preset-add','+'));
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
      // A select must not retain a one-time formatting action as its permanent state.
      input.addEventListener('change', () => {
        if (!input.value) return;
        action(input.value);
        if (key === 'semantic') input.value = '';
      });
      label.append(input); settings.append(label);
      return input;
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
    const semanticTags = new Set(['code','mark','small','kbd','abbr','cite']);
    const clearSemantic = () => {
      checkpoint(); restore();
      const active = range.startContainer.nodeType === Node.ELEMENT_NODE
        ? range.startContainer : range.startContainer.parentElement;
      const semantic = active?.closest?.('code,mark,small,kbd,abbr,cite');
      if (semantic && editor.contains(semantic)) {
        const parent=semantic.parentNode, next=semantic.nextSibling;
        while (semantic.firstChild) parent.insertBefore(semantic.firstChild,semantic);
        semantic.remove();
        range=document.createRange();
        if (next && parent.contains(next))range.setStartBefore(next);
        else {range.selectNodeContents(parent);range.collapse(false);}
        range.collapse(true);
        commit(); restore();
      } else {
        document.execCommand('removeFormat',false,null);
        commit();
      }
    };
    choice('semantic', [
      ['','Select semantic format…'], ['remove','Normal text / Remove semantic'],
      ['code',t('inline_code')],['mark',t('highlight')],['small',t('small_text')],
      ['kbd',t('keyboard')],['abbr',t('abbreviation')],['cite',t('citation')]
    ], value => {
      if (value === 'remove') return clearSemantic();
      if (!semanticTags.has(value)) return;
      wrap(value);
      if (value === 'abbr') {
        const semantic = range.startContainer.nodeType === Node.ELEMENT_NODE
          ? range.startContainer.closest('abbr') : range.startContainer.parentElement?.closest('abbr');
        const title=prompt(t('abbreviation'));
        if(title && semantic){semantic.title=title;commit();}
      }
    });
    add('definition_list', () => command('insertHTML', '<dl><dt>'+escaped('heading')+'</dt><dd>'+escaped('item')+'</dd></dl><p><br></p>'));
    // HTML details defaults to COLLAPSED; "open" is intentionally absent.
    add('disclosure', () => command('insertHTML',
      '<details><summary>'+escaped('heading')+'</summary><p>'+escaped('item')+'</p></details><p><br></p>'));
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
    const panel = el('details','builder-inline-images');
    const summary=el('summary','',t('inline_image'));
    const badge=el('span','builder-image-pending-badge',t('image_pending_short'));
    badge.hidden=true;summary.append(badge);panel.append(summary);
    const feedback=el('p','builder-image-feedback',t('image_apply_help'));
    feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');
    const controls=el('div','builder-inline-image-controls');
    let selectedImage=null, insertionRange=null, insertionBlock=null, appliedValues='';
    const rangeInsideEditor=(candidate)=>candidate && editor.contains(candidate.commonAncestorContainer);
    const rememberRange=()=>{
      const selection=window.getSelection();
      if(!selection?.rangeCount || !editor.contains(selection.anchorNode)
          || !editor.contains(selection.focusNode))return;
      const next=selection.getRangeAt(0);
      // Do not replace a carefully saved caret when leaving text for the settings panel.
      if(!rangeInsideEditor(next))return;
      insertionRange=next.cloneRange();
      const node=next.startContainer.nodeType===Node.ELEMENT_NODE
        ? next.startContainer : next.startContainer.parentElement;
      insertionBlock=node.closest('p,div,li,blockquote,h1,h2,h3,h4,h5,h6,pre');
      if(!insertionBlock || !editor.contains(insertionBlock))insertionBlock=null;
    };
    ['keyup','mouseup','pointerup','input','focusout'].forEach(type=>editor.addEventListener(type,rememberRange));
    const observeSelection=()=>{
      if(!editor.isConnected){
        document.removeEventListener('selectionchange',observeSelection);
        return;
      }
      const selection=window.getSelection();
      if(selection?.anchorNode && editor.contains(selection.anchorNode))rememberRange();
    };
    document.addEventListener('selectionchange',observeSelection);
    const inputField=(label,type='text')=>{
      const wrapper=el('label','builder-field'),input=el('input');
      input.type=type;wrapper.append(el('span','',label),input);controls.append(wrapper);return input;
    };
    const url=inputField(t('url'));url.placeholder='https://… /static/uploads/…';
    const alt=inputField(t('alt'));alt.maxLength=500;
    const choose=(label,options,initial)=>{
      const wrapper=el('label','builder-field'),input=el('select');
      options.forEach(([key,text])=>input.add(new Option(text,key)));
      input.value=initial;wrapper.append(el('span','',label),input);controls.append(wrapper);return input;
    };
    const flow=choose(t('image_flow'),[
      ['left',t('image_left')],['right',t('image_right')],['none',t('image_none')]
    ],'right');
    const width=choose(t('image_width'),['25','40','50','100'].map(x=>[x,x+'%']),'25');
    const advanced=window.FriPeriInlineImage?.attach(controls,()=>selectedImage);
    const placement=choose('Insert image',[
      ['caret','At selected cursor position'],
      ['before','Before selected paragraph'],
      ['after','After selected paragraph'],
      ['start','Beginning of text'],
      ['end','End of text']
    ],'caret');
    const placementHelp=el('p','builder-help builder-inline-placement-help',
      'Click inside the text to position the cursor, then choose the image. '+
      'For text wrapping, select Left or Right and place the image before the relevant paragraph.');
    controls.append(placementHelp);
    const capture=button('Use current text cursor',()=>{
      const selection=window.getSelection();
      if(selection?.rangeCount && editor.contains(selection.anchorNode))rememberRange();
      if(!insertionRange){
        feedback.textContent='Click in your text first to choose where the image should appear.';
        return;
      }
      selectedImage=null;
      remove.disabled=true;
      feedback.textContent='Cursor saved. Apply or upload an image to insert it here.';
      panel.open=true;
    },'builder-inline-position-button');
    controls.append(capture);
    const values=()=>JSON.stringify([url.value.trim(),alt.value,flow.value,width.value,placement.value,advanced?.values()]);
    appliedValues=values();
    const updatePending=(applied=false)=>{
      const pending=values()!==appliedValues;
      panel.classList.toggle('has-pending-image',pending);badge.hidden=!pending;
      apply.disabled=!pending && !!selectedImage;
      apply.textContent=t(selectedImage?'image_update_action':'image_insert_action');
      feedback.textContent=t(pending?'image_pending_help':applied?'image_applied_help':'image_apply_help');
    };
    [url,alt,flow,width,placement].forEach(input=>{
      input.addEventListener('input',()=>updatePending());
      input.addEventListener('change',()=>updatePending());
    });
    advanced?.onChange(()=>updatePending());
    const commit=action=>{
      checkpoint();action();block.html=editor.innerHTML;checkpoint();
    };
    function positionRange(){
      const candidate=insertionRange && rangeInsideEditor(insertionRange)
        ? insertionRange.cloneRange():null;
      const range=document.createRange();
      if(placement.value==='start'){
        range.selectNodeContents(editor);range.collapse(true);return range;
      }
      if(placement.value==='end'){
        range.selectNodeContents(editor);range.collapse(false);return range;
      }
      if(placement.value==='before' || placement.value==='after'){
        const element=insertionBlock && editor.contains(insertionBlock)?insertionBlock:null;
        if(element){
          if(placement.value==='before')range.setStart(element,0);
          else range.selectNodeContents(element),range.collapse(false);
          range.collapse(true);return range;
        }
      }
      if(candidate){
        candidate.collapse(true);return candidate;
      }
      // No caret was selected: insert at the beginning, not silently at the end.
      range.selectNodeContents(editor);range.collapse(true);return range;
    }
    function insertImage(src){
      if(!safeURL(src,true))return message(t('invalid'),true);
      commit(()=>{
        const existing=selectedImage && editor.contains(selectedImage)?selectedImage:null;
        const image=existing || el('img');
        image.src=src;image.alt=alt.value;
        image.className='rich-image rich-image-'+flow.value+' rich-image-width-'+width.value;
        image.loading='lazy';image.decoding='async';
        advanced?.apply(image);
        if(!existing){
          const range=positionRange();
          // A collapsed caret is never allowed to delete selected user text.
          range.collapse(true);range.insertNode(image);
        }
        selectedImage=image;
        insertionRange=document.createRange();
        insertionRange.setStartAfter(image);insertionRange.collapse(true);
        insertionBlock=image.closest('p,div,li,blockquote,h1,h2,h3,h4,h5,h6,pre');
        editor.focus();
        const selection=window.getSelection();
        selection.removeAllRanges();selection.addRange(insertionRange);
      });
      remove.disabled=false;appliedValues=values();updatePending(true);message('');
    }
    const apply=button(t('image_apply'),()=>{
      const src=safeURL(url.value.trim(),true);
      if(!src){message(t('invalid'),true);url.focus();return;}
      try{insertImage(src);}catch(error){message(error.message,true);}
    });
    apply.classList.add('builder-image-apply');
    const remove=button(t('image_remove'),()=>{
      if(selectedImage && editor.contains(selectedImage))commit(()=>selectedImage.remove());
      selectedImage=null;remove.disabled=true;url.value='';alt.value='';advanced?.reset();
      appliedValues=values();updatePending();
    });
    const file=inputField(t('upload'),'file');
    file.accept='image/png,image/jpeg,image/webp';
    file.addEventListener('change',()=>upload(file.files[0],{type:'image'},value=>{
      if(!editor.isConnected)return;
      if(safeURL(value,true)){url.value=value;try{insertImage(value);}catch(error){message(error.message,true);}}
      else message(t('invalid'),true);
    }));
    editor.addEventListener('click',event=>{
      const image=event.target.closest('img');
      if(image && editor.contains(image)){
        selectedImage=image;remove.disabled=false;
        url.value=image.getAttribute('src') || '';alt.value=image.alt;
        flow.value=['left','right','none'].find(v=>image.classList.contains('rich-image-'+v))||'none';
        width.value=['25','40','50','100'].find(v=>image.classList.contains('rich-image-width-'+v))||'40';
        advanced?.load(image);
        appliedValues=values();updatePending();panel.open=true;
      } else {
        // Returning to text means the next image is a NEW insertion.
        selectedImage=null;remove.disabled=true;rememberRange();advanced?.reset();updatePending();
      }
    });
    const actions=el('div','builder-actions');
    actions.append(apply,remove);
    panel.append(controls,feedback,actions,el('p','builder-help',
      'Place the cursor in the paragraph where the image belongs. '+
      'Upload or apply the image; choose Left or Right to wrap text around it. '+
      'Click an existing image in the text to update it.'));
    updatePending();return panel;
  }
  function media(block, body) {
    if (block.type === 'image' && safeURL(block.url,true)) {
      const figure=el('figure','friperi-image-figure');
      const frame=el('span','friperi-image-frame');
      const image=el('img');image.src=block.url;image.alt=block.alt;
      image.loading=block.appearance?.loading || 'lazy';
      image.decoding=block.appearance?.decoding || 'async';
      image.fetchPriority=block.appearance?.fetch_priority || 'auto';
      frame.append(image);figure.append(frame);
      if(block.caption)figure.append(el('figcaption','',block.caption));
      body.append(figure);
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
    if(block.type==='image'){
      const link=el('div','builder-image-link-settings');
      link.append(field('Image link (optional)',block.link_url || '',value=>{block.link_url=value.trim();}));
      link.append(select('Open link',block.link_target || 'same_tab',
        [['same_tab','Same tab'],['new_tab','New tab']],value=>{block.link_target=value;}));
      controls.append(link);
      controls.append(el('p','builder-help','Alternative text describes meaningful images for accessibility. Leave it empty only for purely decorative images. Link URLs are checked on publish.'));
    }
    body.append(controls);if(block.type==='video')body.append(el('p','builder-help',t('video_help')));
  }
  const sectionControls = [
    ['section_layout', [
      ['layout',['stack','two','split','reverse_split','three','six','actions']],['surface',['standard','full']],
       ['height_mode',['viewport','auto','custom']],
      ['vertical_align',['start','center','end']],['content_width',360,1920,1240],['min_height',0,1200,0],
      ['padding_y',0,200,68],['padding_x',0,120,42],['gap',0,100,24],['radius',0,120,20]
    ]],
    ['section_background', [
      ['background_fit',['cover','contain']],['background_position',['center','left','right','top','bottom']],
      ['overlay_color','color','#131c32'],['overlay_opacity',0,100,0],
      ['edge',['flat','wave']],['landing_style',['none','hero','intro','features','showcase','steps','contrast','closing']],
      ['edge_color','color','#f7f8f5']
    ]]
  ];
  const appearanceFields = {
    section: [...sectionControls.flatMap(([, fields]) => fields),
      ['svg_pattern'],['svg_primary'],['svg_secondary'],['svg_opacity']],
    heading: [['font_size',18,160,48],['font_weight',['normal','bold','heavy']],['accent_color','color','#2563eb'],['accent_opacity',0,100,100],['accent_style',['color_only','underline']],['accent_new_line',['no','yes']]],
    list: [['font_size',10,72,18],['item_gap',0,48,8]],
    table: [['cell_background','color','#ffffff'],['cell_color','color','#17243b'],['header_background','color','#eef2ff'],['header_color','color','#17243b']],
    divider: [['padding_top',0,240,36],['padding_bottom',0,240,36]],
    icon: [['icon_size',12,160,48],['icon_color','color',config.design?.accent||'#286e7a'],
      ['background_mode',['none','circle','rounded','square']],['frame_size',24,220,84],
      ['frame_color','color','#e6f2f0'],['radius',0,80,16],['shadow',['none','soft','medium']]],
    icon_button: [['button_background','color',config.design?.accent || '#286e7a'],['button_hover','color',config.design?.navHover || '#20435b'],['button_text','color','#ffffff'],['button_hover_text','color','#ffffff'],['font_size',10,48,20],['variant',['solid','outline','ghost','text_link','underlined']],['width_mode',['auto','full','custom']],['width_px',40,1200,64],['height',24,240,52],['radius',0,120,12],['target',['same_tab','new_tab']]],
    button: [['button_background','color',config.design?.accent || '#286e7a'],['button_hover','color',config.design?.navHover || '#20435b'],['button_text','color','#ffffff'],['button_hover_text','color','#ffffff'],['font_size',10,48,16],['width_mode',['auto','full','custom']],['width_px',40,1200,240],['height',24,240,56],['radius',0,120,100],
      ['variant',['plain','solid','outline','ghost','text_link','underlined']],
      ['icon',['none','arrow','external',
       'arrow-up-light','arrow-up-heavy','arrow-down-light','arrow-down-heavy',
       'arrow-left-light','arrow-left-heavy','arrow-right-light','arrow-right-heavy']],
      ['hover_effect',['none','color','lift']],
      ['border_width',0,8,0],['border_color','color','#2563eb'],['padding_x',0,96,24],['padding_y',0,48,16],['target',['same_tab','new_tab']]],
    image: [
      ['ratio',['original','square','four_three','three_two','wide','portrait','cinema']],
      ['fit',['cover','contain','fill','scale-down']],
      ['position',['center','top','bottom','left','right','top_left','top_right','bottom_left','bottom_right']],
      ['width_mode',['auto','full','custom']],['width_px',100,1920,640],
      ['height_px',0,1200,0],['radius',0,120,14],
      ['border_width',0,16,0],['border_color','color','#dae3ec'],
      ['frame_background','color','#ffffff'],['padding',0,80,0],
      ['shadow',['none','soft','medium','strong']],['hover',['none','zoom','lift']],
      ['image_action',['auto','none','link','lightbox']],['caption_align',['left','center','right']],['caption_size',10,32,14],
      ['loading',['lazy','eager']],['decoding',['async','auto','sync']],
      ['fetch_priority',['auto','high','low']]
    ],
    callout: [
      ['accent_side',['left','right','top','bottom','none']],
      ['accent_color','color',config.design?.accent || '#286e7a'],['accent_width',0,24,5],
      ['shadow',['none','soft','medium','strong']],['background_color','color','#ffffff'],
      ['border_color','color','#dbe3ec'],['border_width',0,10,1],['radius',0,80,20],
      ['padding',8,96,28],['title_color','color','#17243b'],['title_size',14,90,32],
      ['title_weight',['normal','medium','semibold','bold','heavy']],
      ['title_style',['normal','italic']],['title_decoration',['none','underline']],
      ['body_color','color','#17243b'],['body_size',10,48,16],
      ['body_weight',['normal','medium','semibold','bold']],
      ['body_style',['normal','italic']],['body_decoration',['none','underline']],
      ['image_position',['none','left','right','top','bottom']],['image_width',15,65,35],
      ['image_fit',['cover','contain']],['image_ratio',['original','square','four_three','wide','portrait']],
      ['image_radius',0,60,12],['gap',0,80,20]
    ],
    team: [
      ['direction',['vertical','horizontal']],
      ['style',['classic','cards','alternating','checkerboard']],
      ['columns',1,4,3],['photo_width',72,360,180],['gap',8,80,24],
      ['card_padding',0,64,20],['radius',0,60,16],
      ['accent_color','color',config.design?.accent || '#286e7a'],
      ['card_background','color','#ffffff'],
      ['shadow',['none','soft','medium']],
      ['title_size',11,36,14],['title_color','color','#65738a'],
      ['title_weight',['normal','medium','semibold','bold','heavy']],
      ['title_style',['normal','italic']],
      ['title_font',['inherit','sans','serif','monospace']]
    ],
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
    if (block.type === 'image') {
      const a=block.appearance || {};
      Object.assign(body.dataset, {
        imageRatio:a.ratio || 'original',imageFit:a.fit || 'cover',
        imagePosition:a.position || 'center',imageWidth:a.width_mode || 'auto',
        imageShadow:a.shadow || 'none',imageHover:a.hover || 'none',
        captionAlign:a.caption_align || 'left'
      });
      if (a.height_px > 0) body.dataset.imageHeight='custom';
      else delete body.dataset.imageHeight;
    }
    if(block.type==='callout'){
      const a=block.appearance||{};
      Object.assign(body.dataset,{
        accentSide:a.accent_side||'left',calloutShadow:a.shadow||'none',
        titleWeight:a.title_weight||'bold',bodyWeight:a.body_weight||'normal',
        imageRatio:a.image_ratio||'four_three'
      });
      const content=body.querySelector('.friperi-callout-inner');
      if(content){
        content.dataset.imagePosition=a.image_position||'none';
        const oldFrame=content.querySelector('.friperi-callout-media');
        if((a.image_position||'none')==='none' || !block.image_url)oldFrame?.remove();
        else if(!oldFrame){
          const frame=el('figure','friperi-callout-media');
          const img=el('img');img.src=block.image_url;img.alt=block.image_alt||'';
          img.loading='lazy';frame.append(img);content.prepend(frame);
        }
      }
    }
    body.dataset.buttonWidth = block.appearance?.width_mode || 'auto';
    body.dataset.statsColumns = block.appearance?.columns ?? '';
    if(block.type==='team'){
      const settings=block.appearance||{};
      body.dataset.teamDirection=settings.direction||'vertical';
      body.dataset.teamStyle=settings.style||'classic';
      body.dataset.teamColumns=settings.columns||3;
      const preview=body.querySelector('.builder-team-preview');
      if(preview){
        Object.assign(preview.dataset,{
          teamDirection:settings.direction||'vertical',
          teamStyle:settings.style||'classic',
          teamColumns:settings.columns||3
        });
        preview.dataset.titleWeight=settings.title_weight||'normal';
        preview.dataset.titleStyle=settings.title_style||'normal';
        preview.dataset.titleFont=settings.title_font||'inherit';
        for(const [key,value,unit] of [
          ['title-size',settings.title_size||14,'px'],
          ['title-color',settings.title_color||'#65738a',''],
          ['photo-width',settings.photo_width||180,'px'],
          ['gap',settings.gap||24,'px'],
          ['card-padding',settings.card_padding??20,'px'],
          ['radius',settings.radius??16,'px'],
          ['card-background',settings.card_background||'#ffffff',''],
          ['accent-color',settings.accent_color||'#286e7a','']
        ])preview.style.setProperty('--block-'+key,value+unit);
      }
    }
    const appearance = block.appearance || {};
    if (block.type === 'heading') {
      body.dataset.headingWeight = appearance.font_weight || '';
      body.dataset.accent = appearance.accent_style || '';
      body.dataset.accentNewLine = appearance.accent_new_line || 'no';
      body.toggleAttribute('data-heading-size', appearance.font_size !== undefined);
    }
    if (block.type === 'button' || block.type === 'icon_button') {
      body.dataset.variant = appearance.variant || 'solid';
      body.dataset.hoverEffect = appearance.hover_effect || (appearance.variant === 'plain' ? 'none' : 'color');
      const icon = body.querySelector('.builder-button-icon');
      if (icon) {
        const glyphs={arrow:'arrow-right',external:'box-arrow-up-right',
          'arrow-up-light':'arrow-up','arrow-up-heavy':'arrow-up-circle-fill',
          'arrow-down-light':'arrow-down','arrow-down-heavy':'arrow-down-circle-fill',
          'arrow-left-light':'arrow-left','arrow-left-heavy':'arrow-left-circle-fill',
          'arrow-right-light':'arrow-right','arrow-right-heavy':'arrow-right-circle-fill'};
        const name=glyphs[appearance.icon];
        icon.replaceChildren();icon.hidden=!name;
        if(name)icon.append(el('i','bi bi-'+name));
      }
    }
    if(block.type==='icon'){
      const glyph=body.querySelector('.friperi-standalone-icon i');
      if(glyph)glyph.className='bi bi-'+(block.icon_name||'star');
      body.dataset.iconBackground=appearance.background_mode||'none';
      body.dataset.iconShadow=appearance.shadow||'none';
    }
    if (block.type === 'section') {
      Object.assign(body.dataset, {
        layout:appearance.layout || 'stack', surface:appearance.surface || 'standard',
        heightMode:appearance.height_mode || 'auto',
        vertical:appearance.vertical_align || 'center', fit:appearance.background_fit || 'cover',
        position:appearance.background_position || 'center', edge:appearance.edge || 'flat', landingStyle:appearance.landing_style || 'none'
      });
      const currentArt = body.querySelector(':scope > .section-art');
      const pattern = appearance.svg_pattern || 'none';
      const artKey = block.svg_url || pattern;
      if (currentArt?.dataset.pattern !== artKey) {
        currentArt?.remove();
        let art=null;
        if(pattern!=='none' && block.svg_url){
          art=el('img','section-art section-art-saved');
          art.src=block.svg_url;art.alt='';
        }else if(pattern!=='none'){
          art=document.getElementById('builder-art-'+pattern)?.content.firstElementChild.cloneNode(true);
        }
        if(art){art.dataset.pattern=artKey;body.prepend(art);}
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
      const imageLabels={
        ratio:'Aspect ratio',fit:'Image fitting',position:'Focal position',
        width_mode:'Image width',width_px:'Custom width',height_px:'Fixed height (0 = auto)',
        radius:'Corner radius',border_width:'Border width',border_color:'Border color',
        frame_background:'Frame background',padding:'Frame padding',shadow:'Shadow',
        hover:'Hover effect',image_action:'Click action',caption_align:'Caption alignment',
        caption_size:'Caption font size',loading:'Loading mode',decoding:'Decoding',
        fetch_priority:'Fetch priority'
      };
      const teamLabels={title_size:'Title font size',title_color:'Title text color',title_weight:'Title font weight',title_style:'Title font style',title_font:'Title font family',direction:'Team direction',style:'Team style',columns:'Team columns',photo_width:'Photo width',gap:'Card gap',card_padding:'Card padding',radius:'Card corner radius',accent_color:'Accent color',card_background:'Card background',shadow:'Card shadow'};
      const iconLabels={icon_size:'Icon size',icon_color:'Icon color',background_mode:'Icon background',
        frame_size:'Frame size',frame_color:'Frame color',radius:'Corner radius',shadow:'Shadow',hover_effect:'Hover effect'};
      const labelText=block.type==='team'?(teamLabels[key]||t(key)):
        ['icon','button'].includes(block.type)?(iconLabels[key]||t(key)):
        block.type==='image'?(imageLabels[key]||key):(key==='landing_style'?'Landing appearance':t(key));
      label.append(el('span','',labelText+(typeof kind === 'number' && key !== 'columns' ? (key.endsWith('_opacity') ? ' (%)' : ' (px)') : '')));
      let input;
      if(Array.isArray(kind)) {
        input=el('select'); input.add(new Option(t('theme_default'),''));
        const imageOptionLabels={
          original:'Original proportions',square:'Square (1:1)',four_three:'Landscape (4:3)',
          three_two:'Photo (3:2)',wide:'Widescreen (16:9)',portrait:'Portrait (3:4)',
          cinema:'Cinematic (21:9)',scale_down:'Scale down',top_left:'Top left',
          top_right:'Top right',bottom_left:'Bottom left',bottom_right:'Bottom right',
          auto:'Automatic',custom:'Custom pixels',link:'Open URL',
          lightbox:'Open image lightbox',eager:'Eager (above the fold)',
          lazy:'Lazy (recommended)',high:'High',low:'Low'
        };
        const arrowLabels={
          'arrow-up-light':'Up Arrow — Light','arrow-up-heavy':'Up Arrow — Heavy',
          'arrow-down-light':'Down Arrow — Light','arrow-down-heavy':'Down Arrow — Heavy',
          'arrow-left-light':'Left Arrow — Light','arrow-left-heavy':'Left Arrow — Heavy',
          'arrow-right-light':'Right Arrow — Light','arrow-right-heavy':'Right Arrow — Heavy'
        };
        kind.forEach(value=>input.add(new Option(
          key==='icon' && arrowLabels[value] ? arrowLabels[value]
          : key==='variant' && value==='plain' ? 'Plain / No background'
          : key==='hover_effect' ? ({none:'None (static)',color:'Color change',lift:'Lift'}[value]||value)
          : block.type==='image'
            ? (imageOptionLabels[value] || value.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()))
            : key==='landing_style'
              ? ({none:'Standard',hero:'Branded Hero',intro:'Editorial Intro',features:'Feature Cards',showcase:'Product Showcase',steps:'Step Cards',contrast:'Highlight',closing:'Closing CTA'}[value]||value)
              : t('option_'+value),value)));
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
  const imagePanelOpen=new WeakMap();
  function imageAppearanceControls(block,body) {
    const groups=[
      ['Size & crop', ['ratio','fit','position','width_mode','width_px','height_px']],
      ['Frame & effects', ['radius','border_width','border_color','frame_background','padding','shadow','hover']],
      ['Interaction & performance', ['image_action','caption_align','caption_size','loading','decoding','fetch_priority']]
    ];
    const wrapper=el('div','builder-image-appearance');
    const opened=imagePanelOpen.get(block) || new Set(['Size & crop']);
    for(const [title,names] of groups){
      const details=el('details','builder-image-panel');
      details.open=opened.has(title);
      details.addEventListener('toggle',()=>{
        const next=new Set(imagePanelOpen.get(block) || opened);
        if(details.open)next.add(title);else next.delete(title);
        imagePanelOpen.set(block,next);
      });
      const heading=el('summary','',title);
      const controls=appearanceControls(block,body,appearanceFields.image.filter(([name])=>names.includes(name)));
      details.append(heading,controls);wrapper.append(details);
    }
    return wrapper;
  }
  const calloutPanelOpen=new WeakMap();
  function calloutAppearanceControls(block,body) {
    const groups=[
      ['Accent & frame',['accent_side','accent_color','accent_width','shadow','background_color','border_color','border_width','radius','padding']],
      ['Heading typography',['title_color','title_size','title_weight','title_style','title_decoration']],
      ['Body typography',['body_color','body_size','body_weight','body_style','body_decoration']],
      ['Image layout',['image_position','image_width','image_fit','image_ratio','image_radius','gap']]
    ];
    const opened=calloutPanelOpen.get(block) || new Set(['Accent & frame','Heading typography','Body typography','Image layout']);
    const root=el('div','builder-callout-appearance');
    for(const [name,keys] of groups){
      const panel=el('details','builder-image-panel');panel.open=opened.has(name);
      panel.addEventListener('toggle',()=>{
        const next=new Set(calloutPanelOpen.get(block)||opened);
        if(panel.open)next.add(name);else next.delete(name);
        calloutPanelOpen.set(block,next);
      });
      panel.append(el('summary','',name),appearanceControls(block,body,appearanceFields.callout.filter(([key])=>keys.includes(key))));
      root.append(panel);
    }
    return root;
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
    const panel=el('details','builder-section-panel builder-svg-generator');
    panel.open=true;
    panel.append(el('summary','','SVG background designer'));
    const preview=el('div','builder-svg-preview');
    const settings=el('div','builder-svg-controls builder-svg-controls-v2');
    const note=el('p','builder-help');
    note.setAttribute('role','status');
    const actions=el('div','builder-actions');
    const defaults={
      svg_pattern:'ribbons',svg_primary:config.design?.accent||'#7466ef',
      svg_secondary:config.design?.secondary||'#5ed8ce',
      svg_tertiary:'#f2c14e',svg_quaternary:'#a28bdd',
      svg_colors:2,svg_opacity:100,svg_placement:'full',
      svg_rotation:0,svg_scale:100,svg_frequency:3,
      svg_amplitude:45,svg_density:8,svg_stroke:3
    };
    const draft={...defaults,...block.appearance};
    if(draft.svg_pattern==='none')draft.svg_pattern='ribbons';
    const keys=Object.keys(defaults);
    const patternOptions=[
      ['ribbons','Abstract ribbons'],['waves','Layered waves'],['grid','Geometric grid'],
      ['dots','Dot field'],['orbits','Orbital geometry'],['topography','Topographic contours'],
      ['diagonals','Diagonal panels'],['mesh','Flowing mesh']
    ];
    let previewTimer=null,requestCounter=0,previousURL=null;
    const send=async(previewOnly)=>{
      const data=new FormData();
      data.set('editor_token',config.token);
      for(const key of keys)data.set(key,String(draft[key]));
      if(previewOnly)data.set('preview','1');
      const response=await fetch('/admin/section-svg',{method:'POST',body:data});
      if(previewOnly){
        if(!response.ok)throw Error('Preview unavailable');
        return URL.createObjectURL(await response.blob());
      }
      const result=await responseJSON(response);
      if(!response.ok||!result.url)throw Error(result.error||t('section_svg_error'));
      return result.url;
    };
    const redraw=()=>{
      const revision=++requestCounter;
      clearTimeout(previewTimer);
      note.textContent='Preview updates automatically. Generate & save to publish this design.';
      previewTimer=setTimeout(async()=>{
        try{
          const url=await send(true);
          if(revision!==requestCounter){URL.revokeObjectURL(url);return;}
          const img=el('img','builder-svg-preview-image');
          img.src=url;img.alt='Generated section background preview';
          preview.replaceChildren(img);
          if(previousURL)URL.revokeObjectURL(previousURL);
          previousURL=url;
        }catch(error){
          if(revision===requestCounter)note.textContent=error.message||'Preview failed';
        }
      },180);
    };
    const chooser=(label,key,items)=>{
      const wrap=el('label','builder-select'),input=el('select');
      wrap.append(el('span','',label));
      for(const [value,title] of items)input.add(new Option(title,String(value)));
      input.value=String(draft[key]);
      input.addEventListener('change',()=>{draft[key]=typeof defaults[key]==='number'?Number(input.value):input.value;refreshColors();redraw();});
      wrap.append(input);settings.append(wrap);return input;
    };
    const slider=(label,key,min,max,step=1)=>{
      const wrap=el('label','builder-select builder-svg-range');
      const title=el('span','',label),value=el('output','',String(draft[key]));
      const input=el('input');input.type='range';input.min=min;input.max=max;input.step=step;input.value=draft[key];
      input.addEventListener('input',()=>{draft[key]=Number(input.value);value.textContent=String(draft[key]);redraw();});
      wrap.append(title,value,input);settings.append(wrap);
    };
    chooser('Pattern','svg_pattern',patternOptions);
    chooser('Number of colors','svg_colors',[[2,'Two colors'],[3,'Three colors'],[4,'Four colors']]);
    chooser('Placement','svg_placement',[
      ['full','Full background'],['center','Center'],['left','Left'],['right','Right'],
      ['top','Top'],['bottom','Bottom'],['top_left','Top left'],['top_right','Top right'],
      ['bottom_left','Bottom left'],['bottom_right','Bottom right']
    ]);
    const colorRow=el('div','builder-svg-colors');
    const colorInputs=[];
    for(const [key,label] of [
      ['svg_primary','Color 1'],['svg_secondary','Color 2'],
      ['svg_tertiary','Color 3'],['svg_quaternary','Color 4']]){
      const wrap=el('label','builder-select'),input=el('input');
      input.type='color';input.value=draft[key];
      wrap.append(el('span','',label),input);
      input.addEventListener('input',()=>{draft[key]=input.value;redraw();});
      colorRow.append(wrap);colorInputs.push(wrap);
    }
    settings.append(colorRow);
    function refreshColors(){colorInputs.forEach((control,index)=>{control.hidden=index>=draft.svg_colors;});}
    slider('Opacity (%)','svg_opacity',0,100);
    slider('Scale (%)','svg_scale',25,220);
    slider('Rotation (degrees)','svg_rotation',-180,180);
    slider('Wave frequency / repetitions','svg_frequency',1,12);
    slider('Wave amplitude','svg_amplitude',5,120);
    slider('Grid / pattern density','svg_density',2,24);
    slider('Line / dot thickness','svg_stroke',1,12);
    const save=button(t('section_svg_save'),async()=>{
      busy++;updateStatus();note.textContent=t('section_svg_saving');
      try{
        const url=await send(false);
        checkpoint();
        block.svg_url=url;
        block.appearance={...block.appearance,...Object.fromEntries(keys.map(key=>[key,draft[key]]))};
        applyAppearance(block,body);checkpoint();
        remove.disabled=false;
        note.textContent='SVG saved. Publish the page to make it visible.';
      }catch(error){note.textContent=error.message||t('section_svg_error');}
      finally{busy--;updateStatus();}
    },'settings-primary');
    const remove=button(t('section_svg_remove'),()=>{
      checkpoint();delete block.svg_url;
      block.appearance={...block.appearance,svg_pattern:'none'};
      applyAppearance(block,body);checkpoint();remove.disabled=true;redraw();
    },'settings-secondary');
    remove.disabled=!block.appearance?.svg_pattern||block.appearance.svg_pattern==='none';
    actions.append(save,remove);
    panel.append(preview,settings,actions,note);
    refreshColors();redraw();
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
      const blockType=block.type==='icon'?'Icon':block.type==='icon_button'?'Icon Button':block.type==='brand_logo'?'FriPeri Logo':t(hero?'hero_section':block.type);
      const blockNumber=String(index+1).padStart(2,'0');
      const defaultLabel=blockNumber+' / '+blockType;
      const label=defaultLabel+(block.editor_name?' — '+block.editor_name:'');
      const header=el('header','builder-block-header');
      const toggle=button('',event=>{
        // Clicking the name selects it, while double-clicking begins renaming.
        if(event?.target?.closest('.builder-block-name'))return;
        if (collapsedBlocks.has(block)) collapsedBlocks.delete(block);
        else collapsedBlocks.add(block);
        showBlockState();
      },'builder-block-toggle');
      const chevron=el('span','builder-block-chevron');
      chevron.setAttribute('aria-hidden','true');
      const name=el('strong','builder-block-name',label);
      name.title='Double-click to rename this block';
      name.addEventListener('click',event=>event.stopPropagation());
      name.addEventListener('dblclick',event=>{
        event.preventDefault();event.stopPropagation();
        if(name.querySelector('input'))return;
        const input=el('input','builder-block-rename-input');
        input.type='text';input.maxLength=100;
        input.value=block.editor_name||'';
        input.placeholder=blockType;
        input.setAttribute('aria-label','Block name');
        const previous=block.editor_name||'';
        const finish=commit=>{
          if(!name.contains(input))return;
          if(commit){
            const value=input.value.trim().replace(/\s+/g,' ').slice(0,100);
            if(value!==previous){checkpoint();block.editor_name=value;checkpoint();}
          }
          name.textContent=defaultLabel+(block.editor_name?' — '+block.editor_name:'');
          name.title='Double-click to rename this block';
        };
        input.addEventListener('click',e=>e.stopPropagation());
        input.addEventListener('dblclick',e=>e.stopPropagation());
        input.addEventListener('keydown',e=>{
          e.stopPropagation();
          if(e.key==='Enter'){e.preventDefault();finish(true);}
          else if(e.key==='Escape'){e.preventDefault();finish(false);}
        });
        input.addEventListener('blur',()=>finish(true));
        name.replaceChildren(el('span','builder-block-rename-prefix',defaultLabel+' — '),input);
        input.focus();input.select();
      });
      toggle.append(chevron,name);
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
      for (const [key,values] of [['tone',['plain','soft','accent','dark','white','page','navigation','secondary','custom']],['align',['left','center','right']],['width',['normal','wide']]]) {
          const label=value=>{
            if(key!=='tone')return t(value);
            return ({
              plain:'Transparent',soft:'Theme accent (soft)',accent:'Theme feature color',
              dark:'Theme navigation (dark)',white:'White',page:'Theme page background',
              navigation:'Theme navigation color',secondary:'Theme secondary accent',custom:'Custom color'
            })[value]||t(value);
          };
          styles.append(select(t(key),block[key],values.map(v=>[v,label(v)]),v=>{
            block[key]=v;
          }));
        }
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
        const appearance=block.type==='image'?imageAppearanceControls(block,body):block.type==='callout'?calloutAppearanceControls(block,body):appearanceControls(block,body);if(appearance)card.append(appearance);
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
      if(block.type==='brand_logo') {
        const feature=el('div','friperi-logo-feature');
        const brand=el('div','friperi-logo-mark');
        const image=el('img');image.src='/static/images/FriPeri_Logo.png';image.alt='FriPeri logo';
        brand.append(image);
        const words=el('div','friperi-logo-feature-copy');words.append(el('strong','','FriPeri'),el('span','','Ideas deserve a home.'));
        const mock=el('div','friperi-product-mock');
        mock.setAttribute('aria-hidden','true');
        const sidebar=el('span','mock-sidebar');for(let i=0;i<4;i++)sidebar.append(el('i'));
        const content=el('span','mock-content');content.append(el('b'),el('i'),el('i'),el('em'));
        mock.append(sidebar,content);
        feature.append(brand,words,mock);body.append(feature);
      }
      if(block.type==='icon_button' || block.type==='icon') {
        const names=["house","arrow-right","arrow-left","arrow-up-right","envelope","telephone","search","download","share","link-45deg","github","linkedin","instagram","youtube","heart","star","plus-lg","chevron-right","geo-alt","calendar","file-earmark-text","book","chat-dots","globe","people","graph-up","gear","play-fill","camera","image","info-circle","question-circle","arrow-down","arrow-down-circle-fill","arrow-up","arrow-up-circle-fill","arrow-left-circle-fill","arrow-right-circle-fill","arrow-left-short","arrow-right-short","arrow-up-short","arrow-down-short","chevron-up","chevron-down","chevron-left","chevron-double-left","chevron-double-right","chevron-double-up","chevron-double-down","arrow-up-left","arrow-down-left","arrow-down-right","box-arrow-up-right","check-lg","check-circle","x-lg","plus-circle","minus-circle","lightning-charge","bar-chart","bar-chart-line","pie-chart","diagram-3","share-fill","cloud-download","person","person-circle","shield-check","mortarboard","journal-text","chat-square-text","database","code-slash","layers","palette","brush","flower1","sun","moon","compass","pin-map","paperclip","clock","bell","flag","eye","lock","unlock"];
        const standalone=block.type==='icon';
        const preview=el('span',standalone?'friperi-standalone-icon':'custom-button custom-icon-button');
        const glyph=el('i','bi bi-'+(block.icon_name || (standalone?'star':'house')));
        glyph.setAttribute('aria-hidden','true');preview.append(glyph);body.append(preview);
        body.append(select('Icon',block.icon_name || (standalone?'star':'house'),
          names.map(name=>[name,({
            'arrow-down':'Down Arrow — Light','arrow-down-circle-fill':'Down Arrow — Heavy',
            'arrow-up':'Up Arrow — Light','arrow-up-circle-fill':'Up Arrow — Heavy',
            'arrow-left':'Left Arrow — Light','arrow-left-circle-fill':'Left Arrow — Heavy',
            'arrow-right':'Right Arrow — Light','arrow-right-circle-fill':'Right Arrow — Heavy'
          })[name]||name.replaceAll('-',' ').replace(/^./,c=>c.toUpperCase())]),
          value=>{block.icon_name=value;glyph.className='bi bi-'+value;}));
        if(standalone){
          body.append(field('Accessible description (optional)',block.icon_label||'',value=>{
            block.icon_label=value.slice(0,160);
            if(block.icon_label){preview.setAttribute('role','img');preview.setAttribute('aria-label',block.icon_label);}
            else{preview.removeAttribute('role');preview.removeAttribute('aria-label');}
          }));
          if(block.icon_label){preview.setAttribute('role','img');preview.setAttribute('aria-label',block.icon_label);}
        }else{
          body.append(field('Accessible label',block.text||'Home',value=>{block.text=value;}));
          body.append(field(t('url'),block.url,value=>{block.url=value;}));
        }
      }
      if(block.type==='quote') {
        const quote=el('blockquote');
        quote.append(editable('p',block.text,t('quote_hint'),v=>{block.text=v;}));
        const figure=el('figure');figure.append(quote,editable('figcaption',block.attribution,t('attribution'),v=>{block.attribution=v;}));body.append(figure);
      }
      if(block.type==='callout') {
        const content=el('div','friperi-callout-inner');
        content.dataset.imagePosition=block.appearance?.image_position||'none';
        const copy=el('div','friperi-callout-copy');
        copy.append(editable('h3',block.title,t('heading_hint'),v=>{block.title=v;}),
                    editable('p',block.text,t('text_hint'),v=>{block.text=v;}));
        const renderCalloutImage=()=>{
          content.querySelector('.friperi-callout-media')?.remove();
          if(block.image_url && (block.appearance?.image_position||'none')!=='none'){
            const frame=el('figure','friperi-callout-media');
            const img=el('img');img.src=block.image_url;img.alt=block.image_alt||'';
            img.loading='lazy';frame.append(img);content.prepend(frame);
          }
          content.dataset.imagePosition=block.appearance?.image_position||'none';
        };
        content.append(copy);body.append(content);renderCalloutImage();
        const fields=el('div','builder-callout-media-fields');
        const url=field('Image URL (optional)',block.image_url||'',v=>{block.image_url=v.trim();renderCalloutImage();});
        fields.append(url);
        const uploadLabel=el('label','builder-field');
        uploadLabel.append(el('span','','Upload image (PNG, JPEG or WebP)'));
        const file=el('input');file.type='file';file.accept='image/png,image/jpeg,image/webp';
        file.addEventListener('change',()=>upload(file.files[0],{type:'image'},value=>{
          block.image_url=value;url.querySelector('input').value=value;
          if((block.appearance?.image_position||'none')==='none')block.appearance={...block.appearance,image_position:'right'};
          renderCalloutImage();change();
        }));
        uploadLabel.append(file);fields.append(uploadLabel);
        fields.append(field('Image alternative text',block.image_alt||'',v=>{
          block.image_alt=v;content.querySelector('.friperi-callout-media img')?.setAttribute('alt',v);
        }));
        fields.append(button('Remove image',()=>{
          block.image_url='';url.querySelector('input').value='';renderCalloutImage();change();
        }));
        body.append(fields);
      }
      if(block.type==='team') {
        const group=el('div','custom-team-grid builder-team-grid');
        const preview=el('div','custom-team-grid builder-team-preview');
        const updateTeamPreview=()=>{
          preview.replaceChildren();
          const settings=block.appearance||{};
          Object.assign(preview.dataset,{
            teamDirection:settings.direction||'vertical',
            teamStyle:settings.style||'classic',
            teamColumns:settings.columns||3
          });
          preview.style.setProperty('--block-photo-width',(settings.photo_width||180)+'px');
          preview.style.setProperty('--block-gap',(settings.gap||24)+'px');
          preview.style.setProperty('--block-card-padding',(settings.card_padding??20)+'px');
          preview.style.setProperty('--block-radius',(settings.radius??16)+'px');
          preview.style.setProperty('--block-card-background',settings.card_background||'#ffffff');
          preview.style.setProperty('--block-accent-color',settings.accent_color||'#286e7a');
          preview.style.setProperty('--block-title-size',(settings.title_size||14)+'px');
          preview.style.setProperty('--block-title-color',settings.title_color||'#65738a');
          preview.dataset.titleWeight=settings.title_weight||'normal';
          preview.dataset.titleStyle=settings.title_style||'normal';
          preview.dataset.titleFont=settings.title_font||'inherit';
          block.items.forEach(item=>{
            const member=el('div','custom-team-member');
            const frame=el('div','custom-team-photo-frame shape-'+(item.shape||'rectangle')+' orientation-'+(item.orientation||'portrait'));
            if(item.photo && safeURL(item.photo,true)){
              const photo=el('img','custom-team-photo');photo.src=item.photo;photo.alt=item.name||'';
              photo.style.objectFit=item.fit||'cover';
              photo.style.objectPosition=(item.focal_x??50)+'% '+(item.focal_y??50)+'%';
              frame.append(photo);
            }else frame.append(el('div','custom-team-photo-empty'));
            const info=el('div','custom-team-info');
            info.append(el('h3','custom-team-name',item.name||'Team member'),
              el('p','custom-team-title',item.title||'Role or specialization'));
            if(item.bio)info.append(el('p','custom-team-bio',item.bio));
            const links=el('div','custom-team-links');
            const accounts=[
              ['twitter','twitter-x','Twitter / X'],
              ['linkedin','linkedin','LinkedIn'],
              ['website','globe','Personal website'],
              ['email','envelope','Email']
            ];
            for(const [key,iconName,label] of accounts){
              const value=(item[key]||'').trim();
              if(!value)continue;
              if(key==='email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value))continue;
              if(key!=='email' && !safeURL(value))continue;
              const href=key==='email'?'mailto:'+value:value;
              const link=el('a','custom-team-social-link');
              link.href=href;link.title=label;link.setAttribute('aria-label',label);
              link.target=key==='email'?'_self':'_blank';
              if(key!=='email')link.rel='noopener noreferrer';
              const symbol=el('i','bi bi-'+iconName);
              symbol.setAttribute('aria-hidden','true');link.append(symbol);links.append(link);
            }
            if(links.childElementCount)info.append(links);
            member.append(frame,info);preview.append(member);
          });
        };
        updateTeamPreview();
        body.append(el('p','builder-help','Published layout preview — change Team design above to update the arrangement.'),preview);

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
            field(t('team_name'),item.name||'',value=>{item.name=value;updateTeamPreview();}),
            field(t('team_title'),item.title||'',value=>{item.title=value;updateTeamPreview();}),
            field('Short biography',item.bio||'',value=>{item.bio=value.slice(0,1500);updateTeamPreview();}),
            field('Twitter / X URL',item.twitter||'',value=>{item.twitter=value.trim();updateTeamPreview();}),
            field('LinkedIn URL',item.linkedin||'',value=>{item.linkedin=value.trim();updateTeamPreview();}),
            field('Personal website URL',item.website||'',value=>{item.website=value.trim();updateTeamPreview();}),
            field('Email address',item.email||'',value=>{item.email=value.trim();updateTeamPreview();}),
            field(t('team_photo'),item.photo||'',value=>{item.photo=value.trim();updateTeamPreview();})
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
          if(block.items.length<8)mutate(()=>block.items.push({photo:'',name:'',title:'',bio:'',twitter:'',linkedin:'',website:'',email:'',shape:'rectangle',orientation:'portrait',fit:'cover',zoom:1,focal_x:50,focal_y:50}));
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
        const paths={
          wave:'M0 24 C150 5 250 5 400 24 S650 43 800 24 S1050 5 1200 24',
          'wave-tight':'M0 24 C65 14 135 14 200 24 S335 34 400 24 S535 14 600 24 S735 34 800 24 S935 14 1000 24 S1135 34 1200 24',
          arc:'M0 32 Q600 -16 1200 32',
          swoosh:'M0 39 C330 38 460 3 690 17 S1020 38 1200 6'
        };
        const draw=()=>{
          visual.replaceChildren();
          visual.style.setProperty('--divider-width',(block.line_width??1)+'px');
          visual.style.setProperty('--divider-color',block.line_color||'#a5b3be');
          visual.className='builder-divider-line style-'+styleName();
          if(['wave','wave-tight','zigzag','arc','swoosh'].includes(styleName())){
            const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
            svg.setAttribute('viewBox','0 0 1200 48');
            svg.setAttribute('preserveAspectRatio','none');
            svg.setAttribute('aria-hidden','true');
            const path=document.createElementNS('http://www.w3.org/2000/svg','path');
            let d=paths[styleName()];
            if(styleName()==='zigzag'){
              const bits=['M0 24'];
              for(let x=0;x<1200;x+=50)bits.push('L'+(x+25)+' 18 L'+(x+50)+' 30');
              d=bits.join(' ');
            }
            path.setAttribute('d',d);
            path.setAttribute('fill','none');
            path.setAttribute('stroke','var(--divider-color)');
            path.setAttribute('stroke-width','var(--divider-width)');
            path.setAttribute('vector-effect','non-scaling-stroke');
            path.setAttribute('stroke-linecap','round');
            path.setAttribute('stroke-linejoin','round');
            svg.append(path);visual.append(svg);
          }else visual.append(el('hr'));
        };
        const makeNumber=(label,value,min,max,update)=>{
          const wrap=el('label','builder-field');
          const input=el('input');input.type='number';
          input.min=String(min);input.max=String(max);input.step='1';input.value=String(value);
          wrap.append(el('span','',label),input);
          input.addEventListener('change',()=>{
            const numeric=Math.max(min,Math.min(max,Math.round(Number(input.value)||0)));
            input.value=String(numeric);update(numeric);change();
          });
          return wrap;
        };
        const widthControl=makeNumber('Line width (px)',block.line_width??1,1,20,value=>{
          block.line_width=value;draw();
        });
        const styleLabel=el('label','builder-select');styleLabel.append(el('span','','Line style'));
        const styleInput=el('select');
        for(const [key,label] of [
          ['single','Fine line'],['double','Double hairline'],['fade','Soft fade'],
          ['dashed','Delicate dashes'],['dotted','Round dots'],
          ['wave','Gentle wave'],['wave-tight','Soft ripple'],['arc','Elegant arc'],
          ['swoosh','Flowing curve'],['zigzag','Subtle zigzag']
        ])styleInput.add(new Option(label,key));
        styleInput.value=styleName();
        styleInput.addEventListener('change',()=>{
          block.line_style=styleInput.value;draw();change();
        });
        styleLabel.append(styleInput);
        const colorLabel=el('label','builder-field');colorLabel.append(el('span','','Line color'));
        const colorInput=el('input');colorInput.type='color';
        colorInput.value=block.line_color||'#a5b3be';
        colorInput.addEventListener('input',()=>{
          block.line_color=colorInput.value;draw();change();
        });colorLabel.append(colorInput);
        settings.append(widthControl,styleLabel,colorLabel);
        const spacing=el('div','builder-divider-spacing');
        const topInput=makeNumber('Padding top (px)',block.appearance?.padding_top??36,0,240,value=>{
          block.appearance={...block.appearance,padding_top:value};
          applyAppearance(block,body);
        });
        const bottomInput=makeNumber('Padding bottom (px)',block.appearance?.padding_bottom??36,0,240,value=>{
          block.appearance={...block.appearance,padding_bottom:value};
          applyAppearance(block,body);
        });
        spacing.append(topInput,bottomInput);
        body.append(settings,spacing,visual);
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
      ['FriPeri — Full Landing','A branded editorial landing with FriPeri logo, product showcase, rich color and flowing sections',()=>{
        const d=config.design || {};
        const navy='#142e52', violet='#50449f', turquoise='#6dd2d0', blush='#f7b1d6', pale='#f7f5ff';
        const branded=(children,style,background,opts={})=>({
          ...section(children,opts.layout || 'stack','custom'),
          background,foreground:opts.foreground || '#ffffff',
          appearance:{
            layout:opts.layout || 'stack',surface:'full',padding_y:opts.padding ?? 90,
            padding_x:30,gap:opts.gap || 32,content_width:1280,
            min_height:opts.height || 0,edge:opts.edge || 'wave',
            edge_color:opts.edgeColor || '#ffffff',landing_style:style,
            svg_pattern:opts.art || 'none',svg_primary:opts.primary || blush,
            svg_secondary:opts.secondary || turquoise,svg_opacity:opts.opacity || 60
          }
        });
        const intro=()=>({...h('Make space for your next idea.','h1'),
          appearance:{font_size:90,font_weight:'heavy',accent_color:turquoise,accent_style:'color_only'},
          accent:'Built with FriPeri.'});
        const card=(title,copy)=>({...section([h(title,'h3'),p(copy)],'stack','white'),
          appearance:{layout:'stack',padding_y:27,padding_x:23,gap:12,radius:22}});
        const logo=()=>({...newBlock('brand_logo'),align:'center',width:'wide'});
        return [
          branded([
            section([
              h('FRIPERI / VISUAL PUBLISHING','h3'),
              intro(),
              p('A beautiful home for your writing, research, projects and the ideas that matter. Build visually. Publish confidently. Make it yours.'),
              section([action('Explore the possibilities','/about'),action('Get in touch','/contact')],'actions')
            ]),
            logo()
          ],'hero',navy,{layout:'two',height:680,padding:110,art:'ribbons',primary:violet,secondary:turquoise,opacity:78,edgeColor:'#ffffff'}),
          branded([
            h('A new way to bring ideas online.','h2'),
            p('FriPeri brings flexible content blocks, thoughtful design controls and publishing tools into one approachable workspace.')
          ],'intro','#ffffff',{foreground:navy,edgeColor:pale,padding:110}),
          branded([
            h('Designed for the way you create.','h2'),
            p('Everything you need to move from an empty page to a distinctive website.'),
            section([
              card('Visual Page Builder','Create expressive pages by combining text, media, columns and responsive sections.'),
              card('Color Templates','Choose a harmonious palette and refine every detail to match your identity.'),
              card('Content Organization','Organize pages, posts and categories without losing control of your site.'),
              card('Media First','Bring your work to life with images, illustrations and multimedia content.'),
              card('Flexible Layouts','Start with ready-to-edit designs, then adapt every section to your needs.'),
              card('Publish with Confidence','Preview your content and adjust it before sharing with the world.')
            ],'three')
          ],'features',pale,{foreground:navy,padding:95,edgeColor:'#17243f'}),
          branded([
            section([
              h('One canvas. Endless possibilities.','h2'),
              p('Begin with a layout. Build your story block by block. Create something that feels unmistakably yours.'),
              action('See how it works','/about')
            ]),
            logo()
          ],'showcase','#17243f',{layout:'two',padding:95,art:'ribbons',primary:violet,secondary:blush,edgeColor:'#ffffff'}),
          branded([
            h('From first thought to published page.','h2'),
            p('A simple creative workflow.'),
            section([
              card('01 — Choose','Pick a starter layout or begin with a blank canvas.'),
              card('02 — Create','Add content blocks, images, actions and meaningful details.'),
              card('03 — Customize','Set the colors, typography and visual rhythm of the page.'),
              card('04 — Publish','Preview on different screens and publish when ready.')
            ],'two')
          ],'steps','#ffffff',{foreground:navy,padding:105,edgeColor:turquoise}),
          branded([
            h('For the curious. For the creative.','h2'),
            p('Publish articles, research updates, portfolios, project pages and personal stories. Your content should shape the site — not the other way around.'),
            section([action('Start with an idea','/contact')],'actions')
          ],'contrast',turquoise,{foreground:navy,padding:100,edgeColor:navy,art:'waves',primary:'#b5ecdd',secondary:'#ffffff'}),
          branded([
            h('Your ideas deserve a home.','h2'),
            p('Make a space that grows with your work, reflects your personality and welcomes your audience.'),
            section([action('Discover FriPeri','/about'),action('Contact us','/contact')],'actions'),
            logo()
          ],'closing',navy,{padding:105,edge:'wave',edgeColor:d.featureBg || '#f8fbf8',art:'ribbons',primary:violet,secondary:blush})
        ];
      }],
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

    // Palette-aware page layouts. Palette colors are local to the new blocks,
    // never changes the site's global Design settings.
    const paletteLibrary={
      'friperi-world':{name:'FriPeri World',dark:'#16263f',deep:'#20435b',primary:'#286e7a',accent:'#68b6b9',highlight:'#f2c14e',light:'#e5f2ee',paper:'#f8fbf8',warm:'#a5d9d5'},
      'scholarly-grove':{name:'Scholarly Grove',dark:'#172c2a',deep:'#294b46',primary:'#416d62',accent:'#729a88',highlight:'#b87657',light:'#e0e9db',paper:'#f8f7f0',warm:'#d6bc93'},
      'tidal-ember':{name:'Tidal Ember',dark:'#001219',deep:'#005f73',primary:'#0a9396',accent:'#94d2bd',highlight:'#ee9b00',light:'#e9d8a6',paper:'#f8faf7',warm:'#ca6702'},
      'ember-after-dark':{name:'Ember After Dark',dark:'#03071e',deep:'#370617',primary:'#9d0208',accent:'#e85d04',highlight:'#ffba08',light:'#fff2df',paper:'#fff9f3',warm:'#f48c06'},
      'sunlit-horizon':{name:'Sunlit Horizon',dark:'#092b49',deep:'#0d3b66',primary:'#0d3b66',accent:'#ee964b',highlight:'#f4d35e',light:'#faf0ca',paper:'#fffaf0',warm:'#f95738'},
      'electric-orchid':{name:'Electric Orchid',dark:'#240d49',deep:'#3a0ca3',primary:'#4361ee',accent:'#b5179e',highlight:'#4cc9f0',light:'#eae7ff',paper:'#f8f7ff',warm:'#f72585'}
    };
    const pagePalettes=[
      'tidal-ember','electric-orchid','scholarly-grove','tidal-ember',
      'sunlit-horizon','scholarly-grove','electric-orchid','sunlit-horizon',
      'friperi-world','ember-after-dark','tidal-ember','scholarly-grove'
    ];
    const decorated=(children,palette,options={})=>{
      const dark=options.dark??false;
      const bg=options.background||(dark?palette.dark:palette.paper);
      const textColor=options.text||(dark?'#ffffff':palette.dark);
      return {
        ...newBlock('section'),tone:'custom',background:bg,foreground:textColor,
        width:'wide',align:options.align||'left',children,
        appearance:{
          layout:options.layout||'stack',surface:'full',
          height_mode:options.hero?'viewport':'auto',
          vertical_align:options.vertical||'center',
          content_width:options.contentWidth||1240,
          padding_y:options.paddingY??(options.hero?98:82),padding_x:32,
          gap:options.gap??30,edge:options.edge||'flat',
          edge_color:options.edgeColor||(dark?palette.light:palette.paper),
          svg_pattern:options.art||'none',
          svg_primary:options.primary||palette.primary,
          svg_secondary:options.secondary||palette.accent,
          svg_opacity:options.opacity??70
        }
      };
    };
    const slogan=(title,level='h2',size=46,color)=>({
      ...h(title,level),width:'wide',
      ...(color?{foreground:color}:{}),
      appearance:{font_size:size,font_weight:'heavy'}
    });
    const copy=(value)=>p(value);
    const themedButton=(text,url,palette,outline=false)=>({
      ...action(text,url),appearance:{
        icon:'none',variant:outline?'outline':'solid',font_size:16,
        button_background:outline?palette.light:palette.primary,
        button_hover:palette.accent,button_text:outline?palette.dark:'#ffffff',
        button_hover_text:palette.dark,radius:11,padding_x:28,padding_y:15,
        border_color:palette.accent,border_width:outline?2:0
      }
    });
    const actions=(palette,primary='Explore more',url='/about')=>({
      ...newBlock('section'),tone:'plain',width:'wide',
      appearance:{layout:'actions',surface:'standard',padding_y:0,padding_x:0,gap:15},
      children:[themedButton(primary,url,palette),themedButton('Get in touch','/contact',palette,true)]
    });
    const textStack=(heading,description,palette,cta)=>decorated([
      slogan(heading,'h2',36),copy(description),...(cta?[themedButton(cta,'/about',palette)]:[])
    ],palette,{background:palette.light,paddingY:34});
    const tile=(heading,description,palette)=>decorated([
      slogan(heading,'h3',24),copy(description)
    ],palette,{background:'#ffffff',paddingY:32,gap:14});
    const threeCards=(title,intro,items,palette)=>decorated([
      slogan(title,'h2',48),copy(intro),
      { ...newBlock('section'),width:'wide',tone:'plain',
        appearance:{layout:'three',surface:'standard',gap:20,padding_y:12,padding_x:0},
        children:items.map(([a,b])=>tile(a,b,palette))}
    ],palette,{background:palette.light,paddingY:90,edge:'wave',edgeColor:palette.paper});
    const twoColumns=(title,left,right,palette,flip=false)=>decorated([
      decorated([slogan(title,'h2',46),copy(left)],palette,{background:palette.paper,paddingY:24}),
      decorated([slogan('A closer look','h3',29),copy(right)],palette,{background:palette.light,paddingY:30})
    ],palette,{layout:flip?'reverse_split':'two',background:palette.paper,paddingY:90,gap:40});
    const closing=(title,subtitle,palette)=>decorated([
      slogan(title,'h2',60),copy(subtitle),actions(palette,'Start a conversation','/contact')
    ],palette,{dark:true,align:'center',paddingY:100,edge:'wave',edgeColor:palette.paper,
      art:'waves',primary:palette.primary,secondary:palette.accent});
    const hero=(title,tagline,palette,other=null,variant='two')=>decorated([
      decorated([
        {...slogan(title,'h1',82),accent:tagline,appearance:{
          font_size:82,font_weight:'heavy',accent_style:'color_only',accent_color:palette.highlight,accent_new_line:'yes'}},
        copy('Explore a distinctive approach to ideas, research and creative work.'),
        actions(palette)
      ],palette,{background:palette.dark,text:'#ffffff',paddingY:18,gap:24}),
      other||decorated([slogan('01 / Discover','h2',40),copy(tagline)],palette,{
        background:palette.deep,text:'#ffffff',paddingY:38})
    ],palette,{hero:true,dark:true,layout:variant,art:'ribbons',
      primary:palette.primary,secondary:palette.accent,edge:'wave',edgeColor:palette.paper,gap:55});
    const story=(name,palette)=>{
      const pattern=(title,tagline,mid,third,closingTitle)=>[
        hero(title,tagline,palette),
        twoColumns('A different perspective',mid,third,palette),
        threeCards('Explore the possibilities','A selection of thoughtful, editable content panels.',[
          ['Discover','Introduce a key idea or research question.'],
          ['Connect','Show relationships across your work.'],
          ['Create','Present findings in a compelling way.']
        ],palette),
        closing(closingTitle,'Bring your ideas together, and make the next step your own.',palette)
      ];
      switch(name){
        case 'Editorial Story': return [
          hero('Stories worth sharing.','Editorial Story',palette,decorated([
            slogan('Thoughtful writing.','h2',44),copy('A visual introduction for a feature article, long read or opinion piece.')
          ],palette,{background:palette.deep,text:'#ffffff',paddingY:45})),
          twoColumns('Context & perspective','Set the scene with a clear lead paragraph and an engaging introduction.',
            'Use the second column for complementary evidence, a pull quote or a featured illustration.',palette),
          threeCards('The story unfolds','Give every part of your story room to breathe.',[
            ['Background','Build the necessary context.'],['Insights','Highlight your most important observations.'],['Further reading','Offer a path for curious readers.']
          ],palette),closing('Every story matters.','Bring your editorial project to life.',palette)
        ];
        case 'Research Project': return [
          hero('Research that connects.','Project Overview',palette),
          twoColumns('Research questions','Describe your research objectives, hypothesis and context.',
            'Outline the methodology, data sources and analytical workflow.',palette,true),
          threeCards('Research framework','Three ways to present your project stages.',[
            ['01 / Collect','Document your sources and research material.'],
            ['02 / Analyze','Show the methods and instruments used.'],
            ['03 / Interpret','Translate findings into broader insights.']
          ],palette),closing('Discover the findings.','Share your research with the community.',palette)
        ];
        case 'Academic Profile': return [
          hero('Ideas shaped by inquiry.','Researcher Profile',palette,
            decorated([slogan('Research • Teaching • Collaboration','h2',34),copy('A space to introduce your academic journey.')],palette,
              {background:palette.deep,text:'#ffffff',paddingY:38})),
          twoColumns('About the researcher','Introduce your academic background, interests and affiliations.',
            'Describe the questions that guide your work and the collaborations that matter.',palette),
          threeCards('Areas of expertise','Use these cards for your main research domains.',[
            ['Research','Present ongoing and completed studies.'],['Publications','Highlight selected academic contributions.'],['Teaching','Introduce your courses and educational work.']
          ],palette),closing('Let us collaborate.','Connect through shared academic interests.',palette)
        ];
        case 'Project Showcase': return [
          hero('Work made visible.','Selected Projects',palette),
          threeCards('Featured work','Three fully editable project cards ready for your content.',[
            ['Project 01','Goals, methods and key outcomes.'],['Project 02','Research collaborations and impact.'],['Project 03','Creative explorations and experiments.']
          ],palette),
          twoColumns('Behind the process','Explain the choices and challenges that shaped your projects.',
            'Share data, visuals or a compelling result in this flexible second column.',palette,true),
          closing('Explore what comes next.','Your portfolio can grow with every new project.',palette)
        ];
        case 'Landing Page': return [
          hero('Build something remarkable.','Your Next Big Idea',palette),
          threeCards('Why choose us?','Explain three benefits clearly and confidently.',[
            ['Clarity','A message your visitors can understand.'],['Flexibility','Design that adapts to your goals.'],['Impact','A purposeful next step for your audience.']
          ],palette),
          twoColumns('Designed to make a difference','Tell people who you are, what you offer and why it matters.',
            'Place a supporting image or a customer story alongside your message.',palette),
          decorated([slogan('Questions, answered.','h2',44),{...newBlock('faq'),items:[
            {question:'How does this work?',answer:'Describe the process here.'},
            {question:'Where should I begin?',answer:'Explain the next step here.'}
          ]}],palette,{background:palette.paper,paddingY:84}),
          closing('Ready for the next step?','Invite visitors to explore, subscribe or get in touch.',palette)
        ];
        case 'Publication': return [
          hero('Knowledge deserves a voice.','Scholarly Publication',palette,
            decorated([slogan('Research article','h2',40),copy('Authors · Year · Journal or Publisher'),copy('DOI / Publication details')],palette,
              {background:palette.deep,text:'#ffffff',paddingY:44})),
          twoColumns('Abstract','Summarize the study, research objective and central argument.',
            'Keywords, context and an introduction to the theoretical contribution.',palette),
          threeCards('Key contributions','A visual summary for quick reading.',[
            ['Research question','Define what the study investigates.'],
            ['Methodology','Describe data and analytical procedures.'],
            ['Principal findings','Explain the main contribution.']
          ],palette),
          twoColumns('Methods & results','Present the sample, materials and procedures.',
            'Discuss evidence, limitations and the implications of the findings.',palette,true),
          decorated([slogan('References and further reading','h2',40),
            copy('Add the bibliography, research materials, supplementary files and related publications.')],
            palette,{background:palette.light,paddingY:85}),
          closing('Make research accessible.','Share your publication with a wider audience.',palette)
        ];
        case 'Team & Lab': return [
          hero('Curiosity is collaborative.','Our Research Team',palette),
          threeCards('Meet the disciplines','Introduce the people and expertise behind your research group.',[
            ['Communication','Understand social and cultural interaction.'],
            ['Computational methods','Explore evidence with transparent analytical tools.'],
            ['Humanities','Interpret the wider meaning of research findings.']
          ],palette),
          twoColumns('Our approach','Tell the story of how your team works across disciplines.',
            'Describe the collaborations, facilities and research directions you are building.',palette),
          closing('Work with our team.','New ideas grow through collaboration.',palette)
        ];
        case 'Minimal Portfolio': return [
          hero('A collection of ideas.','Selected Work',palette),
          twoColumns('Selected projects','Create a focused introduction to your strongest work.',
            'Use the second column for your process, services or a visual gallery.',palette,true),
          threeCards('What I create','Highlight your strengths with a distinctive visual rhythm.',[
            ['Design','Explain your visual approach.'],['Research','Show the questions you investigate.'],['Development','Share what you have built.']
          ],palette),
          closing('Let us make something.','Get in touch about your next collaboration.',palette)
        ];
        case 'Event & Workshop': return [
          hero('Gather. Learn. Connect.','Event & Workshop',palette),
          twoColumns('What to expect','Describe the theme, audience and key event information.',
            'Present schedule, location, admission and accessibility details.',palette),
          threeCards('The program','A clear and editable three-part event agenda.',[
            ['01 / Welcome','Introductions and an opening presentation.'],
            ['02 / Workshop','Hands-on exploration and discussion.'],
            ['03 / Connect','Questions, networking and next steps.']
          ],palette),
          closing('Join the conversation.','Invite visitors to register or ask a question.',palette)
        ];
        case 'Services & Solutions': return [
          hero('Better questions. Better solutions.','What We Offer',palette),
          threeCards('Expertise in action','Present your services as three clear solutions.',[
            ['Consulting','Define needs and identify opportunities.'],['Analysis','Explore data and draw meaningful conclusions.'],['Training','Build skills through hands-on learning.']
          ],palette),
          twoColumns('How we work','We begin by understanding the people and questions involved.',
            'Then we develop a tailored methodology, communicate progress and deliver outcomes.',palette,true),
          closing('Let us work together.','Turn your next challenge into a clear plan.',palette)
        ];
        case 'Resources & Knowledge Hub': return [
          hero('Discover. Learn. Apply.','Knowledge Hub',palette),
          threeCards('Browse the library','Help visitors find the right resource.',[
            ['Guides','A clear path for beginners.'],['Methods','Transparent research and analysis techniques.'],['Tools','Practical resources to support the work.']
          ],palette),
          twoColumns('Featured resource','Introduce a useful publication, dataset or tutorial.',
            'Provide background, prerequisites and suggestions for further study.',palette),
          closing('Keep exploring.','Knowledge grows when it is shared.',palette)
        ];
      }
      return pattern('Explore your ideas.','Welcome','Describe the context.','Develop your perspective.','Stay connected.');
    };
    const originalLayouts=layouts.map(item=>item.slice());
    const themedLayouts=originalLayouts.map(([name,description,build],index)=>{
      const key=pagePalettes[index],palette=paletteLibrary[key];
      if(name==='FriPeri — Full Landing'){
        return [name,description,()=>{
          const result=build();
          // FriPeri World belongs to these SECTION blocks, not global Design.
          const accents=[palette.deep,palette.paper,palette.light,palette.dark,
            palette.paper,palette.accent,palette.deep];
          result.forEach((block,i)=>{
            block.tone='custom';block.background=accents[i];
            block.foreground=[0,3,6].includes(i)?'#ffffff':palette.dark;
            block.width='wide';
            block.appearance={...block.appearance,
              surface:'full',height_mode:i===0?'viewport':'auto',
              svg_primary:palette.primary,svg_secondary:palette.accent,
              edge_color:i===6?palette.paper:(accents[i+1]||palette.paper)};
          });
          return result;
        },key];
      }
      return [name,description,()=>story(name,palette),key];
    });

    themedLayouts.forEach(([name,description,build,paletteId],i)=>{
      const item=button('',()=>{},'page-layout-tile');
      item.dataset.layoutIndex=String(i);
      const sketch=el('span','page-layout-sketch sketch-'+i);
      const palette=paletteLibrary[paletteId];
      item.dataset.palette=paletteId;
      sketch.style.background='linear-gradient(135deg,'+palette.dark+','+palette.deep+')';
      for(let k=0;k<4;k++){const piece=el('i');piece.style.background=[palette.accent,palette.light,palette.highlight,palette.paper][k];sketch.append(piece);}
      item.append(sketch,el('strong','',name),el('small','',description));
      const paletteTag=el('span','page-layout-palette',palette.name);
      item.append(paletteTag);
      item.addEventListener('click',()=>{
        if(blocks().length && !window.confirm('Replace the current page blocks with '+name+'? You can undo this change.'))return;
        const next=build();
        if(blockCount(next)>80)return message(t('limit'),true);
        mutate(()=>{blocks().splice(0,blocks().length,...next);selected=-1;});
        document.getElementById('page-layout-notice').textContent=name+' ('+palette.name+') is ready. All colors belong to page sections; your global Design settings were not changed. Edit blocks below or select Preview.';
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
