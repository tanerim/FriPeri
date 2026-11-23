"use strict";
document.addEventListener("DOMContentLoaded",()=>{
 const file=document.getElementById('navbar-logo-upload');
 if(!file)return;
 const url=document.getElementById('navbar-logo-url');
 const feedback=document.getElementById('navbar-logo-feedback');
 file.addEventListener('change',async()=>{
  if(!file.files?.[0])return;
  const data=new FormData();
  data.set('file',file.files[0]);
  data.set('editor_token',document.getElementById('navbar-upload-token').value);
  feedback.textContent='Uploading logo…';
  try{
   const res=await fetch('/admin/design/navbar-logo',{method:'POST',body:data});
   const result=await res.json();
   if(!res.ok || !result.url)throw Error(result.error||'Upload failed');
   url.value=result.url;
   feedback.textContent='Logo uploaded. Select Save changes to publish.';
  }catch(error){feedback.textContent=error.message||'Upload failed';}
 });
});
