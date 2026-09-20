import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_os import advisor, config, strategy
from agent_os.state import State
from agent_os.worker import Worker
from test_strategy import record, seed
from test_operator import FakeGitHub, comment
from agent_os.operator import OperatorChannel


class IntegratedAutonomyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.worker=Worker(self.root);self.addCleanup(self.worker.watchers.close)
        self.state=self.worker.state
        self.goal=self.state.add_goal('Goal','Task','Original evidence');seed(self.state,self.goal)

    def legacy(self):
        config.save(self.root,{'model':'base-model','reasoning':'medium','fast':True})
        folder=self.root/'.agent-os'
        for name,flags in [('features.json',{'diagnostic_escalation':False,'github_followups':False}),
                           ('strategy-settings.json',{'strategic_delegation':False})]:
            data=json.loads((folder/name).read_text());data.update(flags);(folder/name).write_text(json.dumps(data))

    def test_migration_preserves_goals_deadlines_pause_guidance_strategy_and_reservations(self):
        self.legacy()
        strategy.save(self.state,self.goal['id'],[record('research')])
        self.state.set_guidance(self.goal['id'],'contract','Use authoritative contract')
        self.state.note(self.goal['id'],'reservation','advisor_started',{'request_id':'already-used','evidence_fingerprint':'known'})
        self.state.update_goal(self.goal['id'],status='waiting',next_run=time.time()+86400)
        self.state.set('paused',True)
        before=self.state.goal(self.goal['id']);progress=self.state.export_progress()
        settings=config.load(self.root);fresh=State(self.root);fresh.recover()
        self.assertTrue(all(settings[k] for k in config.RETIRED_FLAGS))
        self.assertEqual((settings['model'],settings['reasoning'],settings['fast']),('base-model','medium',True))
        self.assertEqual(fresh.goal(self.goal['id']),before);self.assertEqual(fresh.export_progress(),progress)
        self.assertTrue(fresh.get('paused'));self.assertEqual(fresh.history(self.goal['id'])[-1]['data']['request_id'],'already-used')
        with patch('agent_os.worker.Codex.run') as cli:
            self.worker.tick();cli.assert_not_called()
        self.assertIn('core capabilities, not feature toggles',self.worker.prompt(before))
        self.assertEqual(config.save(self.root,{k:False for k in config.RETIRED_FLAGS})['model'],'base-model')
        self.assertTrue(all(config.load(self.root)[k] for k in config.RETIRED_FLAGS))

    def test_defaults_do_not_escalate_without_explicit_evidence_backed_decision(self):
        settings=config.load(self.root)
        self.assertTrue(all(settings[k] for k in config.RETIRED_FLAGS))
        strategy.save(self.state,self.goal['id'],[record('research')])
        with patch('agent_os.advisor.Codex') as cli:
            advisor.consult(self.worker,self.goal,settings);cli.assert_not_called()
            self.assertIsNone(advisor.delegation(self.worker,self.goal,settings))

    def test_catalog_selects_available_upgrade_without_dashboard_preferences(self):
        settings=config.load(self.root)
        catalog=[{'id':settings['model'],'reasoning':['medium','high'],'upgrade':'expert'},
                 {'id':'expert','reasoning':['high'],'default_reasoning':'high'}]
        with patch('agent_os.advisor.config.available_models',return_value=catalog):
            self.assertEqual(advisor.selection(settings,'consult_model'),{'model':'expert','reasoning':'high'})
            self.assertEqual(advisor.selection(settings,'consult_reasoning'),{'model':settings['model'],'reasoning':'high'})
            self.assertEqual(advisor.selection(dict(settings,diagnostic_models=[{'model':'unavailable','reasoning':'high'}]),'consult_model')['model'],'expert')
        self.assertEqual(config.load(self.root),settings)

    def test_justified_advice_runs_with_automatic_selection_and_no_feature_setup(self):
        settings=config.load(self.root)
        strategy.save(self.state,self.goal['id'],[record('consult_model')])
        catalog=[{'id':settings['model'],'reasoning':['medium','high'],'upgrade':'expert'},
                 {'id':'expert','reasoning':['high'],'default_reasoning':'high'}]
        with patch('agent_os.advisor.config.available_models',return_value=catalog),patch('agent_os.advisor.Codex') as cli:
            cli.return_value.run.return_value={'ok':True,'result':{'summary':'Inspect the boundary','next_action':'Try a documented encoding fixture'}}
            advisor.consult(self.worker,self.goal,settings)
            self.assertTrue(cli.return_value.run.call_args.kwargs['readonly'])
            self.assertEqual(cli.call_args.args[1]['model'],'expert')
            advisor.consult(self.worker,self.goal,settings)
            self.assertEqual(cli.return_value.run.call_count,1)
        self.assertEqual(config.load(self.root),settings)

    def test_owner_intake_is_automatic_including_first_poll_and_preserves_pause(self):
        self.legacy();self.state.set('status_issue',1);self.state.set('paused',True)
        github=FakeGitHub();github.comments=[comment()]
        OperatorChannel(github,self.state).poll()
        self.assertEqual(len(self.state.followups()),1);self.assertTrue(self.state.get('paused'))
        self.assertEqual(self.state.goal(self.goal['id'])['acceptance'],'Original evidence')
        # Additional authorized operators do not remove the personal repository owner.
        self.assertTrue(OperatorChannel(github,self.state).authorized('owner/repo',comment(),dict(config.load(self.root),github_operators=['colleague'])))

    def test_terminal_history_is_paged_while_dashboard_loads_only_active_details(self):
        for i in range(65):
            goal=self.state.add_goal('Archive '+str(i),'Task','Evidence')
            self.state.update_goal(goal['id'],status='completed' if i%2 else 'cancelled',attempts=3,summary='Final summary')
        with patch.object(self.state,'history',wraps=self.state.history) as history:
            data=self.state.snapshot(active_only=True)
            self.assertEqual(history.call_count,1)
        self.assertEqual([g['id'] for g in data['goals']],[self.goal['id']])
        self.assertEqual(len(data['goal_progress']),1)
        self.assertEqual(data['goal_counts']['completed']+data['goal_counts']['cancelled'],65)
        ids=[];offset=0
        while offset is not None:
            page=self.state.goal_history(offset);self.assertLessEqual(len(page['goals']),20)
            ids.extend(g['id'] for g in page['goals']);offset=page['next_offset']
        self.assertEqual(len(set(ids)),65)
        self.assertEqual(len(self.state.snapshot()['goals']),66)  # Recovery still includes the full record.
        self.assertEqual(State(self.root).goal_history(),self.state.goal_history())
        for offset,limit in [(-1,20),(0,0),(0,100)]:
            with self.assertRaises(ValueError):self.state.goal_history(offset,limit)
