"use strict";
(()=>{
const choices={"ratio":["original","square","four_three","three_two","wide","portrait","cinema"],"fit":["cover","contain","fill","scale-down"],"position":["center","top","bottom","left","right","top_left","top_right","bottom_left","bottom_right"],"shadow":["none","soft","medium","strong"],"hover":["none","zoom","lift"],"action":["none","lightbox","link"],"loading":["lazy","eager"],"captionAlign":["left","center","right"]},numbers={"radius":[0,120,12],"border":[0,16,0],"padding":[0,80,0],"customWidth":[0,1920,0],"height":[0,1200,0]},colors={"borderColor":"#dbe3ec","frameColor":"#ffffff"};
const fields=[...Object.keys(choices),...Object.keys(numbers),...Object.keys(colors),'link','caption'];
const dataName=key=>'data-rich-'+key.replace(/[A-Z]/g,c=>'-'+c.toLowerCase());
const read=(image,key)=>image.getAttribute(dataName(key));
const safeLink=value=>/^https:\/\/[^\s<>"'\\]+$/i.test(value)?value:'';
const norm=(key,value)=>{
 if(key in choices)return choices[key].includes(value)?value:choices[key][0];
 if(key in numbers){const [min,max,def]=numbers[key];const number=Number(value);return String(Number.isFinite(number)?Math.max(min,Math.min(max,Math.round(number))):def);}
 if(key in colors)return /^#[a-f0-9]{6}$/i.test(value)?value:colors[key];
 if(key==='link')return safeLink(value);
 if(key==='caption')return String(value).slice(0,500);
 return '';
};
function sync(image){
 if(!image?.matches('img.rich-image'))return;
 const value=key=>norm(key,read(image,key)??'');
 const ratios={original:'auto',square:'1/1',four_three:'4/3',three_two:'3/2',wide:'16/9',portrait:'3/4',cinema:'21/9'};
 const positions={center:'center',top:'center top',bottom:'center bottom',left:'left center',right:'right center',top_left:'left top',top_right:'right top',bottom_left:'left bottom',bottom_right:'right bottom'};
 const shadows={none:'none',soft:'0 8px 22px #152d4720',medium:'0 16px 38px #152d4733',strong:'0 24px 65px #152d4745'};
 image.style.aspectRatio=ratios[value('ratio')];
 image.style.objectFit=value('fit');image.style.objectPosition=positions[value('position')];
 image.style.borderRadius=value('radius')+'px';image.style.border=value('border')+'px solid '+value('borderColor');
 image.style.backgroundColor=value('frameColor');image.style.padding=value('padding')+'px';
 image.style.boxSizing='border-box';image.style.boxShadow=shadows[value('shadow')];
 const customWidth=Number(value('customWidth')),height=Number(value('height'));
 if(customWidth)image.style.width=customWidth+'px';else image.style.removeProperty('width');
 image.style.height=height?height+'px':'auto';image.loading=value('loading');
 image.dataset.richHover=value('hover');
 if(read(image,'caption'))image.title=value('caption');
 image.style.cursor=value('action')==='none'?'auto':'pointer';
}
function attach(container,getSelected){
 const details=document.createElement('details');details.className='builder-inline-image-advanced';
 const summary=document.createElement('summary');summary.textContent='Image design & interaction';
 const grid=document.createElement('div');grid.className='builder-inline-image-advanced-grid';
 details.append(summary,grid);container.append(details);
 const inputs={},listeners=[];
 const names={ratio:'Aspect ratio',fit:'Image fit',position:'Focal position',
  shadow:'Shadow',hover:'Hover effect',action:'Click action',loading:'Loading mode',
  captionAlign:'Caption alignment',radius:'Corner radius (px)',border:'Border width (px)',
  padding:'Frame padding (px)',customWidth:'Custom width (px; 0 = auto)',
  height:'Height (px; 0 = auto)',borderColor:'Border color',frameColor:'Frame background',
  link:'Link URL (HTTPS)',caption:'Caption / description'};
 for(const key of fields){
  const label=document.createElement('label');label.className='builder-field';
  const span=document.createElement('span');span.textContent=names[key]||key;
  const input=key in choices?document.createElement('select'):document.createElement('input');
  if(key in choices)for(const v of choices[key])input.add(new Option(v.replaceAll('_',' '),v));
  else if(key in numbers){input.type='number';input.min=numbers[key][0];input.max=numbers[key][1];input.step='1';}
  else input.type=key in colors?'color':key==='link'?'url':'text';
  input.value=key in choices?choices[key][0]:key in numbers?numbers[key][2]:key in colors?colors[key]:'';
  input.addEventListener('input',()=>listeners.forEach(fn=>fn()));
  input.addEventListener('change',()=>listeners.forEach(fn=>fn()));
  label.append(span,input);grid.append(label);inputs[key]=input;
 }
 const reset=()=>{for(const key of fields)inputs[key].value=norm(key,'');};
 return {onChange:fn=>listeners.push(fn),values:()=>fields.map(k=>inputs[k].value).join('|'),reset,
  load:image=>{reset();for(const key of fields){const v=read(image,key);if(v!==null)inputs[key].value=norm(key,v);}},
  apply:image=>{
   if(inputs.action.value==='link' && !safeLink(inputs.link.value.trim()))throw Error('A valid HTTPS link is required.');
   for(const key of fields)image.setAttribute(dataName(key),norm(key,inputs[key].value));
   sync(image);
  }};
}
document.addEventListener('DOMContentLoaded',()=>document.querySelectorAll('.custom-rich-text img.rich-image').forEach(sync));
document.addEventListener('click',event=>{
 const img=event.target.closest?.('.custom-rich-text img.rich-image[data-rich-action="link"]');
 if(!img||img.closest('[contenteditable]'))return;
 const url=safeLink(read(img,'link')||'');if(url)window.open(url,'_blank','noopener,noreferrer');
});
window.FriPeriInlineImage={attach,sync};
})();
