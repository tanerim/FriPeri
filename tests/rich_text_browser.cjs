// Run with: node tests/rich_text_browser.cjs (requires Chromium).
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const source = fs.readFileSync(path.join(__dirname, '../static/home-builder.js'), 'utf8');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'friperi-rich-'));
const helpers = source.slice(source.indexOf('  function cleanRichPaste('), source.indexOf('  function media('));
const url = source.slice(source.indexOf('  function safeURL('), source.indexOf('  function videoURL('));
const appearance = source.slice(source.indexOf('  const appearanceFields ='),source.indexOf('  function render()'));
const test = `
const t = key => key, checkpoint = () => {}, change = () => {};
const el = (tag, cls, text) => { const node=document.createElement(tag); node.className=cls||''; if(text!==undefined)node.textContent=text; return node; };
const button = (label,action) => {const node=el('button','',label);node.addEventListener('click',action);return node;};
const message = text => {throw Error(text);};
${url}
${helpers}
${appearance}
const mutate = action => action();
const assert = (value, label) => {if(!value) throw Error(label);};
const editor=el('div');editor.contentEditable=true;editor.innerHTML='<p>Hello world</p>';document.body.append(editor);
const block={html:editor.innerHTML};const toolbar=richToolbar(editor,block);document.body.append(toolbar);
function select(node) {const range=document.createRange();range.selectNodeContents(node);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);editor.dispatchEvent(new Event('mouseup'));}
function click(label) {[...toolbar.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')===label).click();}
select(editor.firstChild);click('bold');assert(/bold|700|<b>|<strong>/.test(block.html),'bold selection');
select(editor.firstChild);const format=toolbar.querySelector('select');format.value='h2';format.dispatchEvent(new Event('change'));assert(editor.querySelector('h2'),'heading');
select(editor.firstChild);click('bullet_list');assert(editor.querySelector('ul li'),'list');
let answers=['2','2'];window.prompt=()=>answers.shift();select(editor);getSelection().collapseToEnd();editor.dispatchEvent(new Event('mouseup'));click('table');assert(editor.querySelectorAll('tr').length===2,'table insertion');
select(editor.querySelector('th'));click('add_column');assert([...editor.querySelectorAll('tr')].every(row=>row.cells.length===3),'add column');
select(editor.querySelector('td'));click('add_row');assert(editor.querySelectorAll('tr').length===3,'add row');
select(editor.querySelector('th'));click('remove_column');assert([...editor.querySelectorAll('tr')].every(row=>row.cells.length===2),'remove column');
select(editor.querySelector('td'));click('remove_row');assert(editor.querySelectorAll('tr').length===2,'remove row');
const pasted=cleanRichPaste('<h3 onclick="bad()">Title</h3><script>bad()</script><a href="javascript:bad()">bad</a><img src="https://example.com/a.png" onerror="bad()"><p style="color:rgb(255, 0, 0);position:fixed;background-image:url(https://example.com/x)">text</p><ul><li>item</li></ul>');
assert(pasted.includes('<h3>Title</h3>') && pasted.includes('<ul>'),'paste structures');
assert(!/onclick|onerror|javascript:|<script|position|background-image/.test(pasted),'paste security');
assert(pasted.includes('color:') && pasted.includes('rich-image'),'paste presentation');
assert([...toolbar.querySelectorAll('.builder-icon-tool')].every(node=>node.querySelector('svg') && node.title && node.getAttribute('aria-label')), 'accessible icon tools');
const imagePanel=inlineImages(editor,block); document.body.append(imagePanel);
const inputs=imagePanel.querySelectorAll('input');const imageURL=inputs[0],imageAlt=inputs[1];
const apply=imagePanel.querySelector('.builder-image-apply');
assert(apply.disabled,'image action initially inactive');
imageURL.value='/static/uploads/test.png';imageURL.dispatchEvent(new Event('input'));
assert(imagePanel.classList.contains('has-pending-image') && !apply.disabled,'pending insertion visible');
assert(!editor.querySelector('img'),'draft image not inserted yet');apply.click();
const inserted=editor.querySelector('img');assert(inserted && apply.disabled,'image inserted explicitly');
inserted.click();imageAlt.value='Updated image';imageAlt.dispatchEvent(new Event('input'));
assert(inserted.alt!==imageAlt.value && !imagePanel.querySelector('.builder-image-pending-badge').hidden,'image change stays pending');
assert(apply.textContent==='image_update_action','specific image update action');apply.click();
assert(inserted.alt==='Updated image' && imagePanel.querySelector('.builder-image-pending-badge').hidden,'image update committed');
assert(imagePanel.querySelector('[role=status]').textContent==='image_applied_help','applied confirmation');
const canvas=el('div','builder-canvas'),card=el('section','builder-block'),settings=el('div','builder-style-controls');
const body=el('div','custom-block custom-text width-normal');body.append(editor);card.append(settings,toolbar,body,imagePanel);canvas.append(card);document.body.append(canvas);document.body.className='hyperui-admin';
for(const width of [1000,360]) {
  canvas.style.width=width+'px';canvas.style.boxSizing='border-box';
  const toolbarRect=toolbar.getBoundingClientRect(), settingsRect=settings.getBoundingClientRect();
  assert(Math.abs(toolbarRect.width-settingsRect.width)<1 && Math.abs(toolbarRect.left-settingsRect.left)<1,'toolbar matches block settings width');
  assert(toolbar.scrollWidth<=toolbar.clientWidth+1,'toolbar fits narrow widths');
}
const listBlock={type:'list',appearance:{font_size:32,item_gap:20}};
const listBody=el('div','custom-block custom-list');listBody.innerHTML='<ul><li>One</li><li>Two</li></ul>';document.body.append(listBody);applyAppearance(listBlock,listBody);
assert(getComputedStyle(listBody.querySelector('ul')).fontSize==='32px','list size');
assert(getComputedStyle(listBody.querySelectorAll('li')[1]).marginTop==='20px','list spacing');
const buttonBlock={type:'button',appearance:{button_background:'#123456',button_text:'#ffffff',width_mode:'full',height:90,radius:12}};
const buttonBody=el('div','custom-block custom-button');buttonBody.innerHTML='<a class="custom-button" href="#">Button</a>';document.body.append(buttonBody);applyAppearance(buttonBlock,buttonBody);
const buttonStyle=getComputedStyle(buttonBody.firstChild);assert(buttonStyle.backgroundColor==='rgb(18, 52, 86)' && buttonStyle.minHeight==='90px','button appearance');
assert(buttonBody.firstChild.getBoundingClientRect().width>200,'full width button');
const options=appearanceControls(buttonBlock,buttonBody);document.body.append(options);
const heightInput=[...options.querySelectorAll('input[type=number]')].find(input=>input.min==='24');heightInput.value='110';heightInput.dispatchEvent(new Event('input'));assert(buttonBlock.appearance.height===110 && getComputedStyle(buttonBody.firstChild).minHeight==='110px','live appearance input');
heightInput.value='999';heightInput.dispatchEvent(new Event('input'));assert(buttonBlock.appearance.height===110,'invalid size rejected');
const tableBlock={type:'table',rows:[['Head','Head'],['A','B']]};
const cellTable=el('table');cellTable.innerHTML='<tr><th tabindex="0">Head</th><th>Head</th></tr><tr><td>A</td><td>B</td></tr>';document.body.append(cellTable);
const cellTools=tableCellControls(tableBlock,cellTable);document.body.append(cellTools);cellTable.querySelector('th').focus();const cellColor=cellTools.querySelector('input');cellColor.value='#abcdef';cellColor.dispatchEvent(new Event('input'));
assert(tableBlock.cell_styles[0][0].background==='#abcdef' && !tableBlock.cell_styles[0][1].background,'independent cell color');
tableBlock.rows.push(['C','D']);syncCellStyles(tableBlock);assert(tableBlock.cell_styles.length===3 && tableBlock.cell_styles[0][0].background==='#abcdef','cell colors survive resize');
tableBlock.rows.forEach(row=>row.pop());syncCellStyles(tableBlock);assert(tableBlock.cell_styles.every(row=>row.length===1),'cell style dimensions follow table');
const quoteBody=el('div','custom-block custom-quote');quoteBody.innerHTML='<blockquote>Quote</blockquote><figcaption>Author</figcaption>';document.body.append(quoteBody);applyAppearance({type:'quote',appearance:{font_size:40,border_width:0,font_style:'normal',attribution_size:20}},quoteBody);
assert(getComputedStyle(quoteBody.firstChild).fontSize==='40px' && getComputedStyle(quoteBody.firstChild).borderLeftWidth==='0px','quote appearance');
const statsBody=el('div','custom-block custom-stats');statsBody.innerHTML='<dl class="custom-stats-grid"><div><dt>Label</dt><dd>42</dd></div></dl>';document.body.append(statsBody);applyAppearance({type:'stats',appearance:{value_size:64,label_size:24,value_color:'#123456',padding:20,columns:4}},statsBody);
assert(getComputedStyle(statsBody.querySelector('dd')).fontSize==='64px' && getComputedStyle(statsBody.querySelector('dt')).fontSize==='24px','statistics sizes');
assert(getComputedStyle(statsBody.querySelector('.custom-stats-grid > div')).padding==='20px','statistics card padding');
if(matchMedia('(max-width:600px)').matches) assert(getComputedStyle(statsBody.querySelector('.custom-stats-grid')).gridTemplateColumns.split(' ').length===1,'statistics mobile stacking');
document.body.innerHTML='<pre>PASS rich text browser checks</pre>';
`;
try {
  fs.writeFileSync(path.join(dir,'test.html'), '<!doctype html><html><head><style>'+fs.readFileSync(path.join(__dirname,'../static/admin.css'),'utf8')+fs.readFileSync(path.join(__dirname,'../static/custom-home.css'),'utf8')+fs.readFileSync(path.join(__dirname,'../static/home-builder.css'),'utf8')+'</style></head><body><script>try {'+test.replaceAll('</script', '<\\/script')+'} catch(error) {document.body.innerHTML="<pre>FAIL "+error.stack+"</pre>";}</script></body></html>');
  const result=spawnSync(process.env.CHROMIUM || 'chromium',['--headless','--no-sandbox','--disable-gpu','--window-size='+(process.env.TEST_VIEWPORT || '1200,900'),'--disable-dev-shm-usage','--no-proxy-server','--user-data-dir='+path.join(dir,'profile'),'--dump-dom','file://'+path.join(dir,'test.html')],{encoding:'utf8',timeout:30000});
  if (!result.stdout?.includes('<pre>PASS rich text browser checks</pre>')) { console.error(result.stdout || result.stderr || result.error); process.exitCode=1; }
  else console.log('PASS: formatting, tables, paste filtering, accessible icons, image apply feedback, responsive toolbar widths, block appearance and cell colors');
} finally { fs.rmSync(dir,{recursive:true,force:true}); }
