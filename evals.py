import json,os
from pathlib import Path
os.environ['LLM_PROVIDER']='offline'
from agent import FraudAgent

ROOT=Path(__file__).resolve().parent
cases=json.loads((ROOT/'eval_cases.json').read_text())
agent=FraudAgent(); passed=0; failures=[]

for c in cases:
    rec=agent.investigate(c['case_id'])
    ok=(rec.outcome==c['expected_outcome'])
    if c.get('expected_action') is not None:
        ok=ok and rec.action==c['expected_action']
    if c.get('phase')=='investigate' and c.get('expected_reason') is not None:
        ok=ok and rec.safe_stop_reason==c['expected_reason']
    if c['phase']=='approve':
        if not rec.proposed_action_id:
            ok=False
        else:
            out=agent.approve(c['case_id'],rec.proposed_action_id,'eval_user')
            ok=ok and out.get('status')=='failed' and out.get('reason')==c['expected_reason']
    if c['phase']=='reject':
        if not rec.proposed_action_id:
            ok=False
        else:
            out=agent.reject(c['case_id'],rec.proposed_action_id,'eval_user')
            ok=ok and out.get('status')=='rejected' and out.get('reason')==c['expected_reason']
    passed+=int(ok)
    if not ok:
        failures.append({'case':c,'actual':rec.model_dump()})

print(f'Passed {passed}/{len(cases)} synthetic eval cases')
if failures:
    print(json.dumps(failures[:10],indent=2,default=str))
    raise SystemExit(1)
