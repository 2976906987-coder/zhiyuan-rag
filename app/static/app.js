const $=id=>document.getElementById(id);
function node(tag,text,className){const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;return el}
async function api(url,options){const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'请求参数无效');return data}
async function refresh(){const docs=await api('/api/documents');$('count').textContent=docs.length+' 份';$('documents').replaceChildren();const selected=$('filter').value;$('filter').replaceChildren(new Option('全部版本',''));[...new Set(docs.filter(d=>d.status==='ready').map(d=>d.version))].forEach(v=>$('filter').add(new Option(v,v)));$('filter').value=selected;for(const d of docs){const card=node('div','', 'doc');card.append(node('strong',d.filename),node('small',`${d.version} · ${d.chunks} 个片段 · ${d.status}`));if(d.error)card.append(node('small',d.error));const b=node('button','删除');b.disabled=d.status==='indexing';b.onclick=async()=>{if(!confirm('删除文档及其检索索引？'))return;b.disabled=true;try{await api('/api/documents/'+d.id,{method:'DELETE'});await refresh()}catch(e){$('upload-status').textContent=e.message;b.disabled=false}};card.append(b);$('documents').append(card)}}
$('upload').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;const form=new FormData();form.append('file',$('file').files[0]);form.append('version',$('version').value);$('upload-status').textContent='正在解析并创建索引…';try{const d=await api('/api/documents',{method:'POST',body:form});$('upload-status').textContent=d.duplicate?'相同文档已存在，无需重复导入。':'导入完成，可以开始提问。'}catch(err){$('upload-status').textContent=err.message}finally{button.disabled=false;await refresh()}};
$('ask').onsubmit=async e=>{e.preventDefault();if(!$('question').value.trim())return;$('send').disabled=true;$('answer').textContent='正在检索资料并核对引用…';$('sources').replaceChildren();$('metrics').textContent='';try{const r=await streamChat('/api/chat/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('question').value,mode:$('mode').value,version:$('filter').value||''})});renderAnswer(r.answer);$('metrics').textContent=`${r.latency_ms} ms · ${r.refused?'资料不足 / 已拒答':'已生成回答'} · ${r.model_mode==='demo'?'离线演示，非真实模型':'LLM API'} · ${r.usage.total_tokens??'—'} tokens`;for(const s of r.sources){const card=node('div','','source');card.append(node('h4',`[${s.citation}] ${s.filename}`),node('small',`${s.version} · 第 ${s.page} 页 · ${s.cited?'已引用':'检索候选'}`),node('p',s.text));$('sources').append(card)}}catch(err){$('answer').textContent=err.message}finally{$('send').disabled=false}};
async function init(){try{const h=await api('/api/health');$('status').textContent=h.model_mode==='demo'?'离线演示 · 未连接 LLM':'API 模式 · 需配置密钥';$('mode').querySelector('[value=rerank]').disabled=!h.rerank_available;await refresh()}catch(e){$('status').textContent='连接失败';$('upload-status').textContent=e.message}}init();

async function streamChat(url,options){
 const response=await fetch(url,options);
 if(!response.ok)throw Error('问答请求失败');
 const reader=response.body.getReader(),decoder=new TextDecoder();
 let buffer='',draft='',result=null;
 while(true){
  const {done,value}=await reader.read();if(done)break;
  buffer+=decoder.decode(value,{stream:true});
  let boundary;
  while((boundary=buffer.indexOf('\n\n'))>=0){
   const frame=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);
   const type=frame.split('\n').find(x=>x.startsWith('event:'))?.slice(6).trim();
   const line=frame.split('\n').find(x=>x.startsWith('data:'));
   if(!line)continue;
   const payload=JSON.parse(line.slice(5));
   if(type==='token'){draft+=payload.text;renderAnswer(draft);$('metrics').textContent='生成中 · 引用尚待校验';}
   if(type==='error')throw Error(payload.detail);
   if(type==='result')result=payload;
  }
 }
 if(!result)throw Error('连接中断，请重试。');
 return result;
}
