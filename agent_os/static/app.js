/* All user/model text is rendered through textContent, never HTML injection. */
'use strict';
const $ = id => document.getElementById(id);
let access = localStorage.getItem('agent-os-access') || '';
let snapshot = null;
let settingsLoaded = false;
let busy = false;
const expandedHistory = new Set();
const expandedStrategies = new Set();
const historyCache = new Map();
let historyOffset = 0;
let historyLoading = false;
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('token')) {
  access = fragment.get('token');
  localStorage.setItem('agent-os-access', access);
  history.replaceState(null, '', location.pathname);
}
const friendly = {queued:'Queued',running:'Working',waiting:'Waiting',blocked:'Needs input',completed:'Completed',cancelled:'Cancelled'};
function node(tag, text, className) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = text;
  if (className) el.className = className; return el;
}
function time(value) { return value ? new Date(value*1000).toLocaleString('en-GB') : 'Pending'; }
function notice(message) { $('notice').textContent = message; $('notice').hidden = !message; }
async function api(path, data) {
  const response = await fetch(path, {method:data===undefined?'GET':'POST',headers:{'Authorization':'Bearer '+access,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
  let result; try {result = await response.json();} catch {throw Error('Invalid response from the service');}
  if (!response.ok) {if(response.status===401) lock(false); throw Error(result.error || 'Request failed');}
  return result;
}
function lock(clear=true) {
  if(clear){access='';localStorage.removeItem('agent-os-access');}
  $('app').hidden=true; $('unlock').hidden=false; settingsLoaded=false;
}
function paint(data) {
  snapshot=data; $('unlock').hidden=true; $('app').hidden=false;
  $('instance').textContent=data.instance; $('release').textContent='Version '+data.release;
  const alive=data.worker_heartbeat && Date.now()/1000-data.worker_heartbeat<90;
  $('readiness').textContent=data.paused?'Paused':!alive?'Service offline':data.ready?'Ready':'Preparing';
  $('worker-status').textContent=data.active_run?.role==='diagnostic'?'Diagnostic consultation':data.active_run?.role==='scoped'?'Scoped expert execution':data.active_run?'Attempt in progress':alive?'Supervisor active':'Check the WSL2 services';
  const active=data.active_run||data.settings;
  $('current-model').textContent=active.model.replace('gpt-','');
  $('current-reasoning').textContent=active.reasoning+' · '+(active.fast?'Fast':'Standard');
  const counts=data.goal_counts||{};
  $('goal-count').textContent=(counts.user_completed||0)+' / '+(counts.user_total||0);
  $('goal-history-summary').textContent='History · '+(counts.completed||0)+' completed · '+(counts.cancelled||0)+' cancelled · View history';
  $('next-wake').textContent=data.next_maintenance?'Maintenance: '+time(data.next_maintenance):'After initial setup';
  $('sync-status').textContent=data.github.synced?'Synced':data.github.error?'Pending':'Waiting';
  $('sync-time').textContent=data.github.last_push?time(data.github.last_push):'First checkpoint pending';
  const link=data.github.live_url || (data.github.repository?'https://github.com/'+data.github.repository:null);
  if(link && /^https:\/\/github\.com\/[A-Za-z0-9_.\/-]+$/.test(link)){$('github-link').href=link;$('github-link').hidden=false;}
  $('pause').textContent=data.paused?'Resume':'Pause';
  const error=data.github.error||data.github.live_error||data.operator_channel?.error||data.last_error;
  notice(error||(!data.ready?'The system is preparing and testing this instance. Your goals will run once this step is complete.':''));
  $('goals').replaceChildren();
  const rank={running:0,blocked:1,queued:2,waiting:3};
  const visible=data.goals.filter(g=>!['completed','cancelled'].includes(g.status)).sort((a,b)=>(rank[a.status]??4)-(rank[b.status]??4)||b.updated-a.updated);
  if(!visible.length)$('goals').append(node('p','No goals in the queue. Add your next objective.','empty'));
  for(const g of visible){
    const row=node('article',undefined,'goal'), content=node('div'), side=node('div',undefined,'goal-side');
    content.append(node('h3',g.title),node('p',g.summary||g.description,'goal-summary'));
    const meta=node('div',undefined,'goal-meta');meta.append(node('span',friendly[g.status]||g.status,'badge '+g.status),node('span','Attempt '+g.attempts),node('span',g.kind==='bootstrap'?'Setup':g.kind==='maintenance'?'Maintenance':'Goal'));
    if(g.status==='waiting'&&g.next_run>Date.now()/1000)meta.append(node('span','Resumes: '+time(g.next_run)));
    const tracking=data.goal_progress?.[g.id]||{};
    if(tracking.partial)meta.append(node('span','Partially blocked','badge'));
    content.append(meta);side.append(node('strong',g.progress+'%'));
    if(tracking.wait?.reason)content.append(node('p',tracking.wait.reason+'. '+tracking.wait.wake_on,'goal-summary'));
    for(const item of tracking.work_plan||[])content.append(node('p',item.key+' · '+item.status+' · '+item.title+(item.evidence?' · '+item.evidence:''),'work-item'));
    for(const item of tracking.guidance||[]){const line=node('div',undefined,'guidance-item');line.append(node('p','Guidance '+item.key+' (v'+item.version+'): '+item.body));
      const edit=node('button','Edit guidance','secondary');edit.onclick=()=>{$('guidance-goal').value=g.id;$('guidance-key').value=item.key;$('guidance-body').value=item.body;$('guidance-body').focus();};
      const clear=node('button','Clear guidance','secondary');clear.onclick=()=>action('/api/guidance',{action:'clear',goal_id:g.id,key:item.key});line.append(edit,clear);content.append(line);}
    for(const watcher of tracking.watchers||[]){const line=node('div',undefined,'watcher-item');line.append(node('p','Watcher '+watcher.key+' · '+watcher.status+' · Last check: '+time(watcher.last_check)+' · State: '+(watcher.observation??'unobserved')+(watcher.error?' · '+watcher.error:'')));
      if(watcher.status==='active'){const cancel=node('button','Cancel watcher','secondary');cancel.onclick=()=>action('/api/watchers/cancel',{goal_id:g.id,key:watcher.key});line.append(cancel);}content.append(line);}
    for(const s of tracking.strategies||[]){const detail=node('details',undefined,'strategy-detail');const strategyKey=g.id+':'+s.work_key;detail.open=expandedStrategies.has(strategyKey);detail.addEventListener('toggle',()=>{if(detail.open)expandedStrategies.add(strategyKey);else expandedStrategies.delete(strategyKey);});detail.append(node('summary','Strategy · '+s.work_key+' · '+s.action),node('p',s.reason+' Next: '+s.next_action),node('p','Diagnosis: '+s.diagnosis+' · Uncertainty: '+s.uncertainty),node('p','Alternatives: '+s.alternatives),node('p','Independent work: '+s.independent_work));
      if(s.not_before)detail.append(node('p','Useful check: '+time(s.not_before)+(s.expected_by?' · Window ends: '+time(s.expected_by):'')+' · Source: '+s.timing_source));
      for(const f of s.findings||[])detail.append(node('p',f.source+' · '+f.finding+' · '+f.evidence));
      for(const p of s.preparation||[])detail.append(node('p','Preparation · '+p.status+' · '+p.action+' · '+p.evidence));
      if(s.escalation?.expected_value)detail.append(node('p','Escalation assessment: '+s.escalation.expected_value));content.append(detail);}
    row.dataset.goalId=g.id;
    const latest=data.diagnostics?.[g.id]?.[0]?.data;
    if(latest)content.append(node('p',[latest.phase,latest.blocker||latest.completed,latest.next_action].filter(Boolean).join(' · '),'goal-summary'));
    const details=node('details');details.append(node('summary','Diagnostic history'));
    const historyBody=node('div',undefined,'diagnostic-history');details.append(historyBody);
    const renderHistory=entries=>historyBody.replaceChildren(...(entries.length?entries.map(e=>node('p',time(e.at)+' · '+(e.attempt?'Attempt '+e.attempt+' · ':'')+e.kind+' · '+[e.data.phase,e.data.approach,e.data.summary,e.data.blocker,e.data.next_action,e.data.verification].filter(Boolean).join(' · '))):[node('p','No attempt summaries recorded yet.')]));
    renderHistory(historyCache.get(g.id)||[]);
    const loadHistory=async()=>{try{const entries=await api('/api/history/'+encodeURIComponent(g.id));historyCache.set(g.id,entries);if(historyBody.isConnected)renderHistory(entries);}catch(error){historyBody.textContent=error.message;}};
    details.open=expandedHistory.has(g.id);
    details.addEventListener('toggle',()=>{if(details.open){expandedHistory.add(g.id);loadHistory();}else expandedHistory.delete(g.id);});
    content.append(details);
    if(g.status==='blocked'||g.status==='waiting'){const retry=node('button','Retry goal','secondary');retry.onclick=()=>action('/api/control',{action:'retry',goal_id:g.id});side.append(retry);}
    const bar=node('div',undefined,'bar'), progress=document.createElement('progress');progress.max=100;progress.value=g.progress;progress.setAttribute('aria-label','Estimated progress');bar.append(progress);side.append(bar);
    if(g.kind!=='bootstrap'&&!['completed','cancelled'].includes(g.status)){const cancel=node('button','Cancel','cancel');cancel.onclick=()=>action('/api/control',{action:'cancel',goal_id:g.id});side.append(cancel);}
    row.append(content,side);$('goals').append(row);
  }
  const eligible=data.goals.filter(g=>!['completed','cancelled'].includes(g.status));
  const selector=$('guidance-goal'), previous=selector.value;
  const optionState=JSON.stringify(eligible.map(g=>[g.id,g.title]));
  if(selector.dataset.options!==optionState){selector.replaceChildren(...eligible.map(g=>{const option=node('option',g.title);option.value=g.id;return option;}));selector.dataset.options=optionState;if(eligible.some(g=>g.id===previous))selector.value=previous;}
  $('guidance-form').querySelector('button').disabled=!eligible.length;
  $('projects').replaceChildren();
  for(const project of data.projects||[]){const card=node('article',undefined,'project-card');card.append(node('h3',project.name),node('p',project.description||project.path),node('small',project.status||'building'));
    if(project.url){const link=node('a','Open project ↗','button secondary');link.href=project.url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}else card.append(node('code',project.path));$('projects').append(card);}
  if(!data.projects?.length)$('projects').append(node('p','Project links appear here when the agent registers an output.','empty'));
  const framework=data.framework||{};
  $('framework-status').textContent=[framework.status||'Not checked',framework.target_commit?'Target '+framework.target_commit.slice(0,12):'',framework.message||''].filter(Boolean).join(' · ');
  $('framework-apply').disabled=framework.status!=='available'||!data.paused||!!data.active_run;
  $('checks').replaceChildren(...data.last_checks.map(c=>node('span',(c.passed?'✓ ':'× ')+c.name,'check'+(c.passed?'':' fail'))));
  $('events').replaceChildren();
  for(const e of data.events.slice(0,24)){const row=node('div',undefined,'event');row.append(node('time',new Date(e.at*1000).toLocaleTimeString('en-GB')),node('span',e.message));$('events').append(row);}
  if(!settingsLoaded){$('model').value=data.settings.model;$('reasoning').value=data.settings.reasoning;$('fast').checked=data.settings.fast;
    settingsLoaded=true;
    const ids=new Set([...$('model-options').options].map(o=>o.value));for(const m of data.models){if(!ids.has(m.id)){const o=node('option');o.value=m.id;$('model-options').append(o);ids.add(m.id);}}
  }
  $('usage').textContent=((data.usage.input_tokens||0)+(data.usage.output_tokens||0)).toLocaleString('en-GB');
  $('last-refresh').textContent='Updated '+new Date().toLocaleTimeString('en-GB');
}
async function refresh(){if(!access||busy)return;busy=true;try{paint(await api('/api/state'));}catch(err){if(!$('app').hidden)notice(err.message);else $('unlock-error').textContent=err.message;}finally{busy=false;}}
async function action(path,data){try{await api(path,data);await refresh();return true;}catch(err){notice(err.message);return false;}}
$('unlock-form').onsubmit=async e=>{e.preventDefault();access=$('access-token').value.trim();localStorage.setItem('agent-os-access',access);await refresh();$('access-token').value='';};
$('lock').onclick=()=>lock();
$('pause').onclick=()=>action('/api/control',{action:snapshot?.paused?'resume':'pause'});
$('wake').onclick=()=>action('/api/control',{action:'wake'});
$('goal-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button[type="submit"]');button.disabled=true;
  try {if(await action('/api/goals',{title:$('goal-title').value,description:$('goal-description').value,acceptance:$('goal-acceptance').value,commands:$('goal-commands').value.split('\n').map(x=>x.trim()).filter(Boolean)}))e.target.reset();}finally{button.disabled=false;}};
$('guidance-form').onsubmit=async e=>{e.preventDefault();if(await action('/api/guidance',{action:'set',goal_id:$('guidance-goal').value,key:$('guidance-key').value.trim(),body:$('guidance-body').value})){$('guidance-key').value='';$('guidance-body').value='';}};
$('settings-form').onsubmit=async e=>{e.preventDefault();if(await action('/api/settings',{model:$('model').value.trim(),reasoning:$('reasoning').value.trim(),fast:$('fast').checked}))notice('Settings saved. They will apply to the next attempt.');};
async function loadGoalHistory(reset=false){
  if(historyLoading)return;
  historyLoading=true;
  try{
    const page=await api('/api/goals/history?offset='+(reset?0:historyOffset)+'&limit=20');
    if(reset)$('historical-goals').replaceChildren();
    for(const g of page.goals){
      const row=node('details',undefined,'historical-goal');row.dataset.goalId=g.id;
      row.append(node('summary',g.title+' · '+(friendly[g.status]||g.status)+' · '+time(g.updated)),node('p',g.attempts+' attempts · '+(g.summary||'No final summary recorded.')));
      const body=node('div');row.append(body);let loaded=false;
      row.addEventListener('toggle',async()=>{if(!row.open||loaded)return;loaded=true;
        try{const detail=await api('/api/goals/'+encodeURIComponent(g.id));
          body.append(node('p','Acceptance: '+detail.goal.acceptance));
          for(const item of detail.progress.work_plan||[])body.append(node('p',item.title+' · '+item.status+' · '+item.evidence));
          body.append(node('h3','Diagnostic history'));
          for(const entry of detail.history)body.append(node('p',time(entry.at)+' · '+entry.kind+' · '+[entry.data.summary,entry.data.next_action].filter(Boolean).join(' · ')));
        }catch(error){loaded=false;body.textContent=error.message;}
      });$('historical-goals').append(row);
    }
    if(reset&&!page.goals.length)$('historical-goals').append(node('p','No completed or cancelled goals yet.','empty'));
    historyOffset=page.next_offset;$('history-more').hidden=historyOffset===null;
  }catch(error){notice(error.message);}finally{historyLoading=false;}
}
$('goal-history').addEventListener('toggle',()=>{if($('goal-history').open)loadGoalHistory(true);});
$('history-more').onclick=()=>loadGoalHistory();
$('framework-check').onclick=()=>action('/api/framework',{action:'check'});
$('framework-apply').onclick=()=>action('/api/framework',{action:'apply',commit:snapshot?.framework?.target_commit});
refresh();setInterval(refresh,3000);
