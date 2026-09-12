/* All user/model text is rendered through textContent, never HTML injection. */
'use strict';
const $ = id => document.getElementById(id);
let access = localStorage.getItem('agent-os-access') || '';
let snapshot = null;
let settingsLoaded = false;
let busy = false;
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('token')) {
  access = fragment.get('token');
  localStorage.setItem('agent-os-access', access);
  history.replaceState(null, '', location.pathname);
}
const friendly = {queued:'Na fila',running:'Trabalhando',waiting:'Nova tentativa',completed:'Concluído',cancelled:'Cancelado'};
function node(tag, text, className) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = text;
  if (className) el.className = className; return el;
}
function time(value) { return value ? new Date(value*1000).toLocaleString('pt-BR') : 'Pendente'; }
function notice(message) { $('notice').textContent = message; $('notice').hidden = !message; }
async function api(path, data) {
  const response = await fetch(path, {method:data===undefined?'GET':'POST',headers:{'Authorization':'Bearer '+access,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
  let result; try {result = await response.json();} catch {throw Error('Resposta inválida do serviço');}
  if (!response.ok) {if(response.status===401) lock(false); throw Error(result.error || 'Falha na solicitação');}
  return result;
}
function lock(clear=true) {
  if(clear){access='';localStorage.removeItem('agent-os-access');}
  $('app').hidden=true; $('unlock').hidden=false; settingsLoaded=false;
}
function paint(data) {
  snapshot=data; $('unlock').hidden=true; $('app').hidden=false;
  $('instance').textContent=data.instance; $('release').textContent='Versão '+data.release;
  const alive=data.worker_heartbeat && Date.now()/1000-data.worker_heartbeat<90;
  $('readiness').textContent=data.paused?'Pausado':!alive?'Serviço offline':data.ready?'Pronto':'Preparando';
  $('worker-status').textContent=data.active_run?'Tentativa em execução':alive?'Supervisor ativo':'Verifique os serviços WSL2';
  const active=data.active_run||data.settings;
  $('current-model').textContent=active.model.replace('gpt-','');
  $('current-reasoning').textContent=active.reasoning+' · '+(active.fast?'Fast':'Padrão');
  const users=data.goals.filter(g=>g.kind==='user');
  $('goal-count').textContent=users.filter(g=>g.status==='completed').length+' / '+users.length;
  $('next-wake').textContent=data.next_maintenance?'Manutenção: '+time(data.next_maintenance):'Após a preparação inicial';
  $('sync-status').textContent=data.github.synced?'Sincronizado':data.github.error?'Pendente':'Aguardando';
  $('sync-time').textContent=data.github.last_push?time(data.github.last_push):'Primeiro checkpoint pendente';
  const link=data.github.live_url || (data.github.repository?'https://github.com/'+data.github.repository:null);
  if(link && /^https:\/\/github\.com\/[A-Za-z0-9_.\/-]+$/.test(link)){$('github-link').href=link;$('github-link').hidden=false;}
  $('pause').textContent=data.paused?'Retomar':'Pausar';
  const error=data.github.error||data.github.live_error||data.last_error;
  notice(error||(!data.ready?'O sistema está preparando e testando esta instância. Seus goals aguardam a conclusão dessa etapa.':''));
  $('goals').replaceChildren();
  const visible=data.goals.filter(g=>g.kind!=='maintenance'||g.status!=='completed').slice(-30).reverse();
  if(!visible.length)$('goals').append(node('p','Nenhum goal na fila. Adicione seu próximo objetivo.','empty'));
  for(const g of visible){
    const row=node('article',undefined,'goal'), content=node('div'), side=node('div',undefined,'goal-side');
    content.append(node('h3',g.title),node('p',g.summary||g.description,'goal-summary'));
    const meta=node('div',undefined,'goal-meta');meta.append(node('span',friendly[g.status]||g.status,'badge '+g.status),node('span','Tentativa '+g.attempts),node('span',g.kind==='bootstrap'?'Preparação':g.kind==='maintenance'?'Manutenção':'Goal'));
    if(g.status==='waiting'&&g.next_run>Date.now()/1000)meta.append(node('span','Retoma: '+time(g.next_run)));
    content.append(meta);side.append(node('strong',g.progress+'%'));
    const bar=node('div',undefined,'bar'), progress=document.createElement('progress');progress.max=100;progress.value=g.progress;progress.setAttribute('aria-label','Progresso estimado');bar.append(progress);side.append(bar);
    if(g.kind!=='bootstrap'&&!['completed','cancelled'].includes(g.status)){const cancel=node('button','Cancelar','cancel');cancel.onclick=()=>action('/api/control',{action:'cancel',goal_id:g.id});side.append(cancel);}
    row.append(content,side);$('goals').append(row);
  }
  $('checks').replaceChildren(...data.last_checks.map(c=>node('span',(c.passed?'✓ ':'× ')+c.name,'check'+(c.passed?'':' fail'))));
  $('events').replaceChildren();
  for(const e of data.events.slice(0,24)){const row=node('div',undefined,'event');row.append(node('time',new Date(e.at*1000).toLocaleTimeString('pt-BR')),node('span',e.message));$('events').append(row);}
  if(!settingsLoaded){$('model').value=data.settings.model;$('reasoning').value=data.settings.reasoning;$('fast').checked=data.settings.fast;settingsLoaded=true;
    const ids=new Set([...$('model-options').options].map(o=>o.value));for(const m of data.models){if(!ids.has(m.id)){const o=node('option');o.value=m.id;$('model-options').append(o);ids.add(m.id);}}
  }
  $('usage').textContent=((data.usage.input_tokens||0)+(data.usage.output_tokens||0)).toLocaleString('pt-BR');
  $('last-refresh').textContent='Atualizado '+new Date().toLocaleTimeString('pt-BR');
}
async function refresh(){if(!access||busy)return;busy=true;try{paint(await api('/api/state'));}catch(err){if(!$('app').hidden)notice(err.message);else $('unlock-error').textContent=err.message;}finally{busy=false;}}
async function action(path,data){try{await api(path,data);await refresh();return true;}catch(err){notice(err.message);return false;}}
$('unlock-form').onsubmit=async e=>{e.preventDefault();access=$('access-token').value.trim();localStorage.setItem('agent-os-access',access);await refresh();$('access-token').value='';};
$('lock').onclick=()=>lock();
$('pause').onclick=()=>action('/api/control',{action:snapshot?.paused?'resume':'pause'});
$('wake').onclick=()=>action('/api/control',{action:'wake'});
$('goal-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button[type="submit"]');button.disabled=true;
  try {if(await action('/api/goals',{title:$('goal-title').value,description:$('goal-description').value,acceptance:$('goal-acceptance').value,commands:$('goal-commands').value.split('\n').map(x=>x.trim()).filter(Boolean)}))e.target.reset();}finally{button.disabled=false;}};
$('settings-form').onsubmit=async e=>{e.preventDefault();if(await action('/api/settings',{model:$('model').value.trim(),reasoning:$('reasoning').value.trim(),fast:$('fast').checked}))notice('Configuração salva. Será usada na próxima tentativa.');};
refresh();setInterval(refresh,3000);
