"""Concise evidence and decisions, never private reasoning traces or model rankings."""
import json
import math
import time

from .history import text
from .redact import redact
from .progress import key, observation_digest

ACTIONS = ('execute', 'research', 'experiment', 'prepare', 'schedule', 'watch', 'backoff',
           'needs_input', 'consult_reasoning', 'consult_model', 'delegate')


def obj(fields):
    return {'type': 'object', 'additionalProperties': False, 'properties': fields, 'required': list(fields)}


def strings(*names):
    return {name: {'type': 'string'} for name in names}


def records(*names):
    return {'type': 'array', 'items': obj(strings(*names))}


SCHEMA = obj(dict(strings('work_key', 'blocker_key', 'situation', 'diagnosis', 'uncertainty',
                         'alternatives', 'independent_work', 'reason', 'next_action', 'chosen_approach',
                         'change_evidence', 'timing_source', 'human_dependency'),
    action={'type': 'string', 'enum': list(ACTIONS)},
    constraint={'type': 'string', 'enum': ['none', 'technical', 'information', 'scheduled', 'external', 'operator', 'authentication', 'configuration', 'quota']},
    not_before={'type': 'number'}, expected_by={'type': 'number'},
    findings=records('key', 'source', 'finding', 'evidence'),
    approaches=records('key', 'method', 'hypothesis', 'status', 'result', 'evidence'),
    preparation=records('key', 'action', 'status', 'evidence'),
    advice_outcomes=records('key', 'advice_id', 'action', 'result', 'evidence'),
    escalation=obj(strings('request_id', 'question', 'exhaustion', 'clarity', 'expected_value', 'scope'))))


def validate(value, schema=SCHEMA):
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['properties']):
            raise ValueError('Invalid strategic record fields')
        for k, v in value.items():
            validate(v, schema['properties'][k])
    elif kind == 'array':
        if not isinstance(value, list) or len(value) > 40:
            raise ValueError('Strategic lists allow up to 40 concise records')
        for item in value:
            validate(item, schema['items'])
        if len({v['key'] for v in value}) != len(value):
            raise ValueError('Duplicate strategic record keys')
    elif kind == 'number':
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid strategic time')
    elif not isinstance(value, str) or len(value) > 2000 or ('enum' in schema and value not in schema['enum']):
        raise ValueError('Invalid strategic text')
    if schema is SCHEMA:
        key(value['work_key'])
        if not value['reason'].strip() or not value['next_action'].strip():
            raise ValueError('A strategic decision requires a reason and next action')
        for approach in value['approaches']:
            if approach['status'] not in ('untried', 'failed', 'rejected', 'selected', 'succeeded'):
                raise ValueError('Invalid approach status')
            if approach['status'] in ('failed', 'rejected', 'succeeded') and not (approach['result'] and approach['evidence']):
                raise ValueError('An approach conclusion requires a result and evidence')
        for prep in value['preparation']:
            if prep['status'] not in ('planned', 'done') or (prep['status'] == 'done' and not prep['evidence']):
                raise ValueError('Preparation requires a valid status and completion evidence')
        if value['action'] in ('schedule', 'watch', 'backoff', 'needs_input'):
            if not all(value[k].strip() for k in ('diagnosis', 'alternatives', 'independent_work')):
                raise ValueError('Investigate the cause, alternatives and independent work before waiting')
            if not value['findings'] or any(not f['source'] or not f['finding'] for f in value['findings']):
                raise ValueError('Waiting requires source-backed findings, including unavailable research if applicable')
        if value['action'] == 'schedule':
            if not value['not_before'] or not value['timing_source'] or not any(
                    f['source'] == value['timing_source'] and f['evidence'] for f in value['findings']):
                raise ValueError('Scheduled waiting requires an evidenced timing source and UTC time')
            if value['expected_by'] and value['expected_by'] < value['not_before']:
                raise ValueError('The reassessment window must not precede its start')
        if value['action'] == 'watch' and value['not_before']:
            raise ValueError('Prefer the known future schedule over a watcher')
        if value['action'] == 'needs_input' and not value['human_dependency'].strip():
            raise ValueError('Needs input requires a concrete human-only dependency')
    return value


def clean(value):
    if isinstance(value, str):
        return text(value, 2000)
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    return value


def all_records(state, goal_id):
    with state.db() as db:
        return [json.loads(r[0]) for r in db.execute(
            'SELECT data FROM strategies WHERE goal_id=? ORDER BY updated,key', (goal_id,))]


def save(state, goal_id, updates):
    if not isinstance(updates, list) or len(updates) > 40:
        raise ValueError('Invalid strategy updates')
    current = {s['work_key']: s for s in all_records(state, goal_id)}
    plan = {i['key']: i for i in state.work_plan(goal_id)}
    pending = []
    for update in updates:
        validate(update)
        new = clean(update)
        if new['work_key'] not in plan:
            raise ValueError('Strategy must reference an existing acceptance work item')
        old = current.get(new['work_key'], {})
        prior = {a['key']: a for a in old.get('approaches', [])}
        for a in new['approaches']:
            p = prior.get(a['key'])
            if p and p != a and p['status'] in ('failed', 'rejected'):
                new['findings'].append({'key': 'prior-' + signature(p)[:20], 'source': p['evidence'],
                                        'finding': text(p['method'] + ': ' + p['hypothesis'] + ' — ' + p['result'], 2000),
                                        'evidence': p['evidence']})
        for field in ('findings', 'approaches', 'preparation', 'advice_outcomes'):
            merged = {v['key']: v for v in old.get(field, [])}
            if field == 'approaches':
                for a in new[field]:
                    abandoned = [p for p in merged.values() if p['status'] in ('failed', 'rejected') and
                                 (p['key'] == a['key'] or signature(p) == signature(a))]
                    reopening = a['status'] in ('selected', 'untried') or new['chosen_approach'] == a['key']
                    if abandoned and reopening and (not new['change_evidence'] or new['change_evidence'] == old.get('change_evidence')):
                        raise ValueError('Reopening an abandoned approach requires new change evidence')
            merged.update({v['key']: v for v in new[field]})
            if len(merged) > 120:
                raise ValueError('Consolidate strategic evidence in repository files before adding more records')
            new[field] = list(merged.values())
        chosen = next((a for a in new['approaches'] if a['key'] == new['chosen_approach']), None)
        if chosen and chosen['status'] in ('failed', 'rejected') and (not new['change_evidence'] or new['change_evidence'] == old.get('change_evidence')):
            raise ValueError('A rejected approach needs new evidence before retrying')
        item = dict(plan[new['work_key']])
        if item['status'] != 'verified':
            if new['action'] in ('execute', 'research', 'experiment', 'prepare', 'consult_reasoning', 'consult_model', 'delegate'):
                item['status'] = 'actionable'
            elif new['action'] == 'needs_input':
                item['status'] = 'needs_input'
                item['blocker_key'] = new['blocker_key']
            else:
                item['status'] = 'waiting'
                item['blocker_key'] = new['blocker_key']
        from .progress import validate_plan
        validate_plan([item])
        pending.append((new, item))
    with state.db() as db:
        goal = db.execute('SELECT status FROM goals WHERE id=?', (goal_id,)).fetchone()
        if not goal or goal[0] in ('completed', 'cancelled'):
            raise ValueError('Strategy requires an active goal')
        for new, item in pending:
            db.execute("INSERT OR REPLACE INTO work_items VALUES (?,?,?)", (goal_id, item["key"], json.dumps(item)))
            db.execute('INSERT OR REPLACE INTO strategies VALUES (?,?,?,?)',
                       (goal_id, new['work_key'], json.dumps(new), time.time()))
            if new['action'] != 'watch':
                for w in db.execute("SELECT key,spec FROM watchers WHERE goal_id=? AND status='active'", (goal_id,)).fetchall():
                    if json.loads(w['spec'])['work_key'] == new['work_key']:
                        db.execute("UPDATE watchers SET status='cancelled' WHERE goal_id=? AND key=?", (goal_id, w['key']))
        if pending:
            state._dirty(db)


def signature(approach):
    # Keys and result prose alone cannot manufacture methodological diversity.
    return observation_digest([{'key': 'method', 'value': approach['method']},
                               {'key': 'hypothesis', 'value': approach['hypothesis']}])


def evidence_fingerprint(record):
    facts = [{'key': f['source'], 'value': f['finding'] + ' ' + f['evidence']} for f in record['findings']]
    facts += [{'key': signature(a), 'value': a['result'] + ' ' + a['evidence']} for a in record['approaches'] if a['evidence']]
    facts += [{'key': a['advice_id'], 'value': a['result'] + ' ' + a['evidence']} for a in record['advice_outcomes']]
    return observation_digest(facts)


def request(state, goal, settings, actions):
    """Evidence floors are necessary, never sufficient: the worker must explicitly choose."""
    plan = {i['key']: i for i in state.work_plan(goal['id'])}
    for s in reversed(all_records(state, goal['id'])):
        item = plan.get(s['work_key'], {})
        if s['action'] not in actions or s['constraint'] != 'technical' or item.get('status') != 'actionable':
            continue
        if s['work_key'] not in {i['key'] for i in state.actionable_work(goal['id'])}:
            continue
        e = s['escalation']
        if not all(e[k].strip() for k in ('request_id', 'question', 'exhaustion', 'clarity', 'expected_value')):
            continue
        attempted = {signature(a) for a in s['approaches'] if a['status'] in ('failed', 'rejected') and a['evidence'] and a['result']}
        history = state.history(goal['id'], None, ('attempt',))
        efforts = [h for h in history if h['data'].get('model', settings['model']) == settings['model'] and
                   h['data'].get('blocker_key') == s['blocker_key'] and h['data'].get('blocker_kind') == 'technical']
        if (len(efforts) < settings['diagnostic_min_attempts'] or len(attempted) < 3 or
                not s['findings'] or not all(f['source'] and f['evidence'] for f in s['findings']) or
                not all(s[k].strip() for k in ('diagnosis', 'uncertainty', 'alternatives', 'independent_work'))):
            continue
        return s
    return None


def dossier(state, goal, record):
    return {'goal': {k: redact(goal[k]) for k in ('title', 'description', 'acceptance')},
            'affected_work': next(i for i in state.work_plan(goal['id']) if i['key'] == record['work_key']),
            'verified': [i for i in state.work_plan(goal['id']) if i['status'] == 'verified'],
            'guidance': state.guidance(goal['id']), 'strategy': record,
            'prior_advice': state.history(goal['id'], None, ('advisor_advice', 'advisor_failed', 'delegation_result')),
            'recent_attempts': state.history(goal['id'], 12, ('attempt',))}


def scheduled_delay(state, goal_id, now=None):
    """Use documented time without the generic backoff cap; never suppress independent work."""
    now = time.time() if now is None else now
    if state.actionable_work(goal_id):
        return None
    waiting = [i for i in state.work_plan(goal_id) if i['status'] == 'waiting']
    records_by_key = {s['work_key']: s for s in all_records(state, goal_id)}
    times = []
    watching = {}
    for watcher in state.watchers(goal_id):
        if watcher['status'] == 'active' and watcher['expires'] > now:
            work_key = watcher['spec']['work_key']
            watching[work_key] = min(watching.get(work_key, watcher['expires']), watcher['expires'])
    has_schedule = False
    for item in waiting:
        s = records_by_key.get(item['key'], {})
        if s.get('action') == 'schedule' and s.get('not_before', 0) > now:
            times.append(s['not_before'])
            has_schedule = True
        elif item['key'] in watching:
            times.append(watching[item['key']])
        else:
            return None  # Another unresolved stream still needs its own reassessment policy.
    return min(times)-now if times and has_schedule else None


def validate_watchers(state, goal_id, specs):
    by_key = {s['work_key']: s for s in all_records(state, goal_id)}
    for spec in specs:
        s = by_key.get(spec['work_key'])
        if not s or s['action'] != 'watch':
            raise ValueError('Research, schedules and alternatives must justify a watcher decision first')


PROMPT = """Choose the most useful next action from evidence, not an attempt-number rotation.
Read docs/STRATEGY.md. Python is a tool, not a strategy: do not remain inside a polling script
when understanding the problem, documentation, another tool or another approach is needed.
Decompose all immutable criteria into verified, actionable, external, human-only and evidence gaps.
Separate anticipatory preparation from later real validation. Refine an old aggregate item by
making it actionable with child prerequisites; retain its criterion and verify it after its children.
Investigate causes: logs, API semantics, authoritative documentation/status/metadata, calendars,
maintenance/reset times, configuration and authorized access. Record sources and sanitized findings.
Seek equivalent capabilities and permitted alternatives; fixtures never replace required live evidence.
Do independent and useful preparatory work first; record preparation with evidence, avoid busywork.
Known time/window -> schedule a UTC not_before with an evidenced timing_source (expected_by for a
bounded window). Unknown but observable -> watcher only after research/alternatives/preparation.
Unknown and unobservable -> backoff. Needs input requires a concrete human-only dependency, not doubt.
Return strategies updates keyed to work_plan. Preserve findings, rejected hypotheses and advice trials.
Reopening a failed/rejected approach requires genuinely new change_evidence, not rewording or time.
Choose research/experiment/prepare/execute while productive work remains. Do not loop unchanged probes.
Escalation is your explicit decision: assess exhaustion, clarity and expected value versus cost/latency.
Missing information calls for research; schedules for waiting; complex conceptual conflicts may warrant
consult_reasoning (same model, higher effort); narrowed exhausted technical problems may warrant
consult_model (read-only advice). Counts are only safety floors, never reasons to escalate.
Supply a focused escalation question and concise operational evidence, never private reasoning traces.
Apply advice with judgment and record advice_outcomes using advisor_advice data.advice_id (or legacy event_key) as advice_id.
A later consultation needs a new request_id, recommendation trials and new evidence. An advisor may
recommend no further escalation. Only after useful advice and attempted recommendations, consider
an explicitly justified delegate request with a narrow scope, if scoped execution is operator-enabled.
You remain goal owner. No model can change acceptance, permissions, approvals or operator settings.
Return empty strategies for read-only review or when no strategic update is needed.
"""
