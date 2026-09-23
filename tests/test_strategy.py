import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import advisor, config, strategy
from agent_os.state import State
from agent_os.worker import Worker
from test_goal_progress import item, watcher, diagnostic
from test_worker import FakeGitHub, success


def record(action='research', **updates):
    value = {k: '' for k, v in strategy.SCHEMA['properties'].items() if v['type'] == 'string'}
    value.update(work_key='verify', blocker_key='parser', situation='Contract mismatch',
                 diagnosis='Observed response conflicts with documented schema', uncertainty='Encoding or transport?',
                 alternatives='Test another permitted endpoint; local fixture cannot pass required live validation',
                 independent_work='Documentation and fixture preparation can proceed independently',
                 constraint='external' if action in ('schedule','watch','backoff') else 'operator' if action=='needs_input' else 'technical',
                 action=action, reason='Resolve the evidence gap', next_action='Inspect the authoritative contract',
                 not_before=0, expected_by=0,
                 findings=[dict(key='contract', source='docs/provider-contract.md', finding='UTF-8 is required', evidence='docs/evidence/contract.md')],
                 approaches=[dict(key=str(i), method=method, hypothesis='Isolate '+method, status='failed', result='Mismatch remains', evidence='docs/evidence/'+str(i)+'.md')
                             for i, method in enumerate(('trace', 'minimal reproduction', 'dependency review'))],
                 preparation=[dict(key='fixture', action='Prepare deterministic contract fixture', status='done', evidence='tests/fixtures/contract.json')],
                 advice_outcomes=[], escalation=dict(request_id='request-1', question='Which contract assumption is wrong?',
                    exhaustion='Three distinct experiments and documented alternatives failed', clarity='Input reproduces the mismatch',
                    expected_value='A contract analysis may save repeated full runs; one bounded consultation justifies cost and latency', scope=''))
    value.update(updates)
    return value


def seed(state, goal):
    state.save_work_plan(goal['id'], [item(status='actionable')])
    for i in range(3):
        state.note(goal['id'], 'base-'+str(i), 'attempt', dict(blocker_key='parser', blocker_kind='technical', approach_key=str(i)))


class StrategyFixture:

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = Worker(self.root)
        self.addCleanup(self.worker.watchers.close)
        self.state = self.worker.state
        self.goal = self.state.add_goal('Service', 'Build a service', 'Live health and documented access')
        self.gid = self.goal['id']
        seed(self.state, self.goal)

    def save(self, value):
        strategy.save(self.state, self.gid, [value])



class StrategyTests(StrategyFixture, unittest.TestCase):
    def test_known_time_and_bounded_window_outlive_generic_backoff(self):
        now = time.time()
        self.save(record('schedule', not_before=now+86400, expected_by=now+90000, timing_source='docs/provider-contract.md'))
        self.state.register_watcher(self.gid, watcher(), now)
        self.save(record('schedule', not_before=now+86400, expected_by=now+90000, timing_source='docs/provider-contract.md'))
        self.assertEqual(self.state.watchers(self.gid)[0]['status'], 'cancelled')
        self.assertAlmostEqual(self.state.schedule_external(self.gid, diagnostic(), config.DEFAULTS, now), 86400)
        self.assertIn('Documented', self.state.wait_state(self.gid)['reason'])
        self.state.save_work_plan(self.gid, [item('documentation', 'actionable')])
        self.assertIsNone(strategy.scheduled_delay(self.state, self.gid, now))

    def test_wait_requires_research_alternatives_and_preparation_assessment(self):
        for field in ('findings', 'diagnosis', 'alternatives', 'independent_work'):
            r = record('watch');r[field] = [] if field == 'findings' else ''
            with self.assertRaises(ValueError):
                self.save(r)
        self.save(record('watch'))
        strategy.validate_watchers(self.state, self.gid, [watcher()])
        with self.assertRaises(ValueError):
            self.save(record('watch', not_before=time.time()+900))
        self.save(record('research'))
        with self.assertRaises(ValueError):
            strategy.validate_watchers(self.state, self.gid, [watcher()])
        self.assertEqual(self.state.actionable_work(self.gid)[0]['key'], 'verify')

    def test_strategy_survives_restart_and_recovery_with_preparation_evidence(self):
        self.save(record())
        original = strategy.all_records(self.state, self.gid)
        fresh = State(self.root);fresh.recover()
        self.assertEqual(strategy.all_records(fresh, self.gid), original)
        exported = self.state.export_progress()
        with fresh.db() as db:
            db.execute('DELETE FROM strategies')
        fresh.restore_progress(exported)
        self.assertEqual(strategy.all_records(fresh, self.gid), original)
        self.assertEqual(fresh.progress_snapshot()[self.gid]['strategies'][0]['preparation'][0]['status'], 'done')
        self.assertEqual(fresh.goal(self.gid)['acceptance'], self.goal['acceptance'])

    def test_rejected_method_cannot_return_under_a_new_key_without_new_evidence(self):
        r = record();self.save(r)
        retry = copy.deepcopy(r['approaches'][0]);retry.update(key='renamed', status='selected')
        with self.assertRaises(ValueError):
            self.save(record('experiment', approaches=[retry], chosen_approach='renamed'))
        self.save(record('experiment', approaches=[retry], chosen_approach='renamed', change_evidence='New input captured in docs/evidence/new.md'))
        self.assertEqual(len(strategy.all_records(self.state, self.gid)[0]['approaches']), 4)

    def test_relabelled_equivalent_methods_do_not_qualify_for_advice(self):
        r = record('consult_model')
        for a in r['approaches']:
            a['method']='same probe';a['hypothesis']='same claim'
        self.save(r)
        self.assertIsNone(strategy.request(self.state, self.goal, config.DEFAULTS, ('consult_model',)))

    def test_attempt_counts_never_override_no_escalation_or_missing_dossier(self):
        self.save(record('research'))
        self.assertIsNone(strategy.request(self.state, self.goal, config.DEFAULTS, ('consult_model',)))
        for field in ('exhaustion', 'clarity', 'expected_value', 'question'):
            r=record('consult_model');r['escalation'][field]='';self.save(r)
            self.assertIsNone(strategy.request(self.state, self.goal, config.DEFAULTS, ('consult_model',)))
        self.save(record('consult_model'))
        self.assertIsNotNone(strategy.request(self.state, self.goal, config.DEFAULTS, ('consult_model',)))
        dossier=strategy.dossier(self.state, self.goal, strategy.all_records(self.state, self.gid)[0])
        self.assertEqual(dossier['goal']['acceptance'], self.goal['acceptance'])
        self.assertEqual(len(dossier['recent_attempts']),3)
        self.assertIn('findings', dossier['strategy'])

    def test_external_constraints_never_escalate_even_with_historical_technical_attempts(self):
        for constraint in ('external','information','scheduled','operator','authentication','configuration','quota'):
            self.save(record('consult_model',constraint=constraint))
            self.assertIsNone(strategy.request(self.state,self.goal,config.DEFAULTS,('consult_model',)))

    def test_known_schedule_and_unknown_watcher_use_earliest_useful_reassessment(self):
        now=time.time()
        self.save(record('schedule',not_before=now+86400,timing_source='docs/provider-contract.md'))
        self.state.save_work_plan(self.gid,[item('other','waiting')])
        self.state.register_watcher(self.gid,watcher(key='other-ready',work_key='other'),now)
        self.assertEqual(strategy.scheduled_delay(self.state,self.gid,now),3600)

    def test_operator_input_requires_human_dependency_not_uncertainty(self):
        with self.assertRaises(ValueError):
            self.save(record('needs_input'))
        self.save(record('needs_input', human_dependency='Owner must complete interactive MFA locally'))
        self.assertEqual(self.state.work_plan(self.gid)[0]['status'], 'needs_input')

    def test_refining_an_aggregate_preserves_criteria_and_pending_live_evidence(self):
        self.state.save_work_plan(self.gid,[item('aggregate','actionable',['verify','prepare']),item('prepare','verified')])
        self.save(record('schedule',not_before=time.time()+36000,timing_source='docs/provider-contract.md'))
        self.assertEqual(self.state.actionable_work(self.gid),[])
        self.assertFalse(self.state.plan_complete(self.gid))
        self.state.save_work_plan(self.gid,[item('verify','verified')])
        self.assertEqual(self.state.actionable_work(self.gid)[0]['key'],'aggregate')
        self.assertFalse(self.state.plan_complete(self.gid))
        self.assertEqual(self.state.goal(self.gid)['acceptance'],self.goal['acceptance'])

    def test_schema_is_strict_and_rejected_hypothesis_is_archived_on_reopening(self):
        from agent_os.codex import SCHEMA, validate_result
        self.assertIn('strategies',SCHEMA['required'])
        value=success('continue')['result'];value['strategies']=[record()]
        validate_result(value)
        value['strategies'][0]['private_reasoning']='Never store this'
        with self.assertRaises(ValueError):validate_result(value)
        original=record();self.save(original)
        changed=record();changed['approaches'][0]['status']='selected';changed['change_evidence']='docs/evidence/new-input.md'
        self.save(changed)
        findings=strategy.all_records(self.state,self.gid)[0]['findings']
        self.assertTrue(any('Mismatch remains' in f['finding'] for f in findings))

    def test_old_runtime_config_files_have_no_new_settings(self):
        settings=config.save(self.root, {'strategic_delegation': True})
        self.assertTrue(settings['strategic_delegation'])
        for filename in ('config.json','features.json','progress-settings.json'):
            self.assertNotIn('strategic_delegation', json.loads((self.root/'.agent-os'/filename).read_text()))

    def test_reasoning_and_model_escalation_are_separate_catalog_resources(self):
        settings=dict(config.DEFAULTS, diagnostic_models=[dict(model='gpt-6-sol',reasoning='high')])
        catalog=[dict(id=settings['model'],reasoning=['medium','high']),dict(id='gpt-6-sol',reasoning=['high'])]
        with patch('agent_os.advisor.config.available_models', return_value=catalog):
            self.assertEqual(advisor.selection(settings,'consult_reasoning'),dict(model=settings['model'],reasoning='high'))
            self.assertEqual(advisor.selection(settings,'consult_model'),dict(model='gpt-6-sol',reasoning='high'))

    def test_worker_executes_preparation_before_external_recheck(self):
        self.worker.github=FakeGitHub(self.state);self.worker.heartbeat=lambda:None;self.worker.promote_and_deploy=lambda:None
        r=record('prepare');work=success('continue')
        work['result'].update(work_plan=[item()], strategies=[r], watchers=[], diagnostic=diagnostic())
        with patch('agent_os.worker.Codex.run', return_value=work),patch('agent_os.worker.checks.verify', return_value=([{'passed':True}],'')):
            self.worker.tick()
        self.assertLess(self.state.goal(self.gid)['next_run'], time.time()+5)
        self.assertEqual(self.state.actionable_work(self.gid)[0]['key'],'verify')
        self.assertIn('Prepare deterministic contract fixture', self.worker.prompt(self.goal))


class EscalationTests(StrategyFixture, unittest.TestCase):
    # Reuse a temporary controller, but keep escalation cases separate from scheduling assertions.
    def setUp(self):
        super().setUp()
        self.settings=config.save(self.root, {'diagnostic_escalation':True,'strategic_delegation':True,
                                    'diagnostic_models':[dict(model='gpt-6-sol',reasoning='high')]})
        self.catalog=[dict(id='gpt-6-sol',reasoning=['high'])]

    def prior_advice(self):
        self.state.note(self.gid,'advice-1','advisor_advice',dict(blocker_key='parser',next_action='Test a byte boundary'),at=time.time()-5000)
        return [dict(key='trial-1',advice_id='advice-1',action='Test a byte boundary',result='Still fails with the minimal input',evidence='docs/evidence/byte-boundary.md')]

    def test_second_consultation_requires_trials_new_evidence_and_a_new_request(self):
        first=record('consult_model');self.save(first)
        fingerprint=strategy.evidence_fingerprint(first)
        self.state.note(self.gid,'old-call','advisor_started',dict(blocker_key='parser',request_id='request-1',evidence_fingerprint=fingerprint),at=time.time()-5000)
        outcomes=self.prior_advice()
        with patch('agent_os.advisor.config.available_models',return_value=self.catalog),patch('agent_os.advisor.Codex') as cli:
            advisor.consult(self.worker,self.goal,self.settings);cli.assert_not_called()
            new=record('consult_model');new['escalation']['request_id']='request-2';self.save(new)
            advisor.consult(self.worker,self.goal,self.settings);cli.assert_not_called()
            new['advice_outcomes']=outcomes;new['diagnosis']='The mismatch persists at the byte boundary';self.save(new)
            cli.return_value.run.return_value={'ok':True,'result':{'summary':'No expert execution needed','next_action':'Inspect the documented field delimiter with the base model'}}
            advisor.consult(self.worker,self.goal,self.settings)
            prompt=cli.return_value.run.call_args.args[0]
            self.assertIn('byte-boundary.md',prompt)
            self.assertIn('Test a byte boundary',prompt)
            self.assertIn('Live health and documented access',prompt)
            self.assertTrue(cli.return_value.run.call_args.kwargs['readonly'])
            advisor.consult(self.worker,self.goal,self.settings)
            self.assertEqual(cli.return_value.run.call_count,1)
        self.assertIn('No expert execution needed',self.worker.prompt(self.goal))

    def test_direct_execution_requires_useful_advice_and_trials_not_legacy_flags(self):
        value=record('delegate');value['escalation']['scope']='Repair only the parser byte-boundary function and its regression test';self.save(value)
        with patch('agent_os.advisor.config.available_models',return_value=self.catalog):
            self.assertIsNone(advisor.delegation(self.worker,self.goal,self.settings))
            value['advice_outcomes']=self.prior_advice();self.save(value)
            self.assertIsNotNone(advisor.delegation(self.worker,self.goal,dict(self.settings,strategic_delegation=False,diagnostic_escalation=False)))
            scoped=advisor.delegation(self.worker,self.goal,self.settings)
            self.assertIn(value['escalation']['scope'],scoped['prompt'])
            self.assertEqual(config.load(self.root),self.settings)

    def test_scoped_turn_cannot_complete_goal_and_base_resumes(self):
        value=record('delegate',advice_outcomes=self.prior_advice())
        value['escalation']['scope']='Repair parser boundary only';self.save(value)
        self.worker.github=FakeGitHub(self.state);self.worker.heartbeat=lambda:None;self.worker.promote_and_deploy=lambda:None
        with patch('agent_os.advisor.config.available_models',return_value=self.catalog),patch('agent_os.worker.Codex') as cli,patch('agent_os.worker.checks.verify',return_value=([{'passed':True}],'')):
            cli.return_value.run.return_value=success()  # A helper completion claim is never overall completion.
            self.worker.tick()
            self.assertEqual(cli.call_args.args[1]['model'],'gpt-6-sol')
            self.assertEqual(cli.call_args.args[1]['step_timeout_seconds'],600)
            self.assertEqual(self.state.goal(self.gid)['status'],'queued')
            self.assertFalse(self.state.get('pending_completion'))
            self.assertEqual(cli.return_value.run.call_count,1)
            cli.return_value.run.return_value=success('continue')
            self.worker.tick()
            self.assertEqual(cli.call_args.args[1]['model'],self.settings['model'])
            self.assertIn('Base model must inspect',cli.return_value.run.call_args.args[0])
        self.assertEqual(config.load(self.root),self.settings)

    def test_failed_scoped_turn_returns_to_base_and_reservation_survives_restart(self):
        value=record('delegate',advice_outcomes=self.prior_advice());value['escalation']['scope']='Parser only';self.save(value)
        self.worker.github=FakeGitHub(self.state);self.worker.heartbeat=lambda:None
        with patch('agent_os.advisor.config.available_models',return_value=self.catalog),patch('agent_os.worker.Codex') as cli:
            cli.return_value.run.return_value={'ok':False,'error_kind':'execution','error':'Helper failed'}
            self.worker.tick()
            self.assertEqual(self.state.goal(self.gid)['status'],'queued')
            fresh=Worker(self.root);self.addCleanup(fresh.watchers.close);fresh.state.recover()
            self.assertIsNone(advisor.delegation(fresh,self.goal,self.settings))
            self.worker.tick()
            self.assertEqual(cli.call_args.args[1]['model'],self.settings['model'])

    def test_failed_advice_never_enables_direct_execution(self):
        self.state.note(self.gid,'failed','advisor_failed',dict(blocker_key='parser',summary='Unavailable'))
        value=record('delegate');value['escalation']['scope']='Parser only';self.save(value)
        with patch('agent_os.advisor.config.available_models',return_value=self.catalog):
            self.assertIsNone(advisor.delegation(self.worker,self.goal,self.settings))

    def test_recovered_history_keeps_advice_outcomes_linked_by_stable_id(self):
        self.state.note(self.gid,'restored:history:1','advisor_advice',
                        dict(blocker_key='parser',advice_id='original-advice',next_action='Test boundary'),at=time.time()-5000)
        value=record('delegate',advice_outcomes=[dict(key='trial',advice_id='original-advice',action='Test boundary',
                    result='Mismatch remains',evidence='docs/evidence/trial.md')])
        value['escalation']['scope']='Repair boundary only';self.save(value)
        with patch('agent_os.advisor.config.available_models',return_value=self.catalog):
            self.assertIsNotNone(advisor.delegation(self.worker,self.goal,self.settings))

    def test_pause_and_context_change_discard_advisor_output(self):
        self.save(record('consult_model'))
        with patch('agent_os.advisor.config.available_models',return_value=self.catalog),patch('agent_os.advisor.Codex') as cli:
            self.state.set('paused',True);advisor.consult(self.worker,self.goal,self.settings);cli.assert_not_called()
            self.state.set('paused',False)
            def changed(*args,**kwargs):
                self.state.set_guidance(self.gid,'source','Use the revised contract')
                return {'ok':True,'result':{'summary':'Stale','next_action':'Old contract'}}
            cli.return_value.run.side_effect=changed
            advisor.consult(self.worker,self.goal,self.settings)
            self.assertEqual(self.state.history(self.gid)[-1]['kind'],'advisor_failed')
