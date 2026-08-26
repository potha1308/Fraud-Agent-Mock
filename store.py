from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT/name).read_text())

CASES=load('cases.json')
TRANSACTIONS=load('transactions.json')
DEVICE=load('device_signals.json')
CONTACTS=load('prior_contacts.json')
POLICIES=load('policies.json')
EXISTING_ACTIONS=load('existing_actions.json')
CONTROLS=load('scenario_controls.json')
