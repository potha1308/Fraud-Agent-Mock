import os,unittest,json
from pathlib import Path
os.environ['LLM_PROVIDER']='offline'
from agent import FraudAgent
import tools

class AgentTests(unittest.TestCase):
    def test_dataset_size(self):
        d=json.loads((Path(__file__).resolve().parent/'eval_cases.json').read_text())
        self.assertEqual(len(d),144)

    def test_happy_path(self):
        a=FraudAgent(); r=a.investigate('FR-00001')
        self.assertEqual(r.action,'temporary_protection')
        self.assertTrue(r.requires_human_approval)

    def test_no_action_has_no_approval(self):
        a=FraudAgent(); r=a.investigate('FR-00031')
        self.assertEqual(r.action,'no_action_monitor')
        self.assertFalse(r.requires_human_approval)

    def test_write_requires_token(self):
        with self.assertRaises(tools.ToolError):
            tools.execute_action('FR-00001','temporary_protection',None)

    def test_trace_contains_agent_and_tools(self):
        a=FraudAgent(); a.investigate('FR-00001')
        names=[x['name'] for x in a.trace('FR-00001')]
        self.assertIn('next_step',names)
        self.assertIn('get_transaction',names)
        self.assertIn('human_approval_gate',names)

if __name__=='__main__': unittest.main()
