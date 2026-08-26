import json,sys
from agent import FraudAgent

def pp(x):
    print(json.dumps(x,indent=2,default=str))

def demo(case_id='FR-00001'):
    agent=FraudAgent()
    print('Provider:',agent.provider.__class__.__name__)
    print('Investigating',case_id)
    rec=agent.investigate(case_id)
    pp(rec.model_dump())
    if rec.outcome=='recommend' and rec.proposed_action_id:
        print('\nHuman approval required.')
        ans=input('Approve [a], reject [r], skip [enter]? ').strip().lower()
        if ans=='a': pp(agent.approve(case_id,rec.proposed_action_id,'demo_associate'))
        elif ans=='r': pp(agent.reject(case_id,rec.proposed_action_id,'demo_associate'))
    print('\nTrace:')
    pp(agent.trace(case_id))

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='demo':
        demo(sys.argv[2] if len(sys.argv)>2 else 'FR-00001')
    else:
        print('python app.py demo FR-00001')
