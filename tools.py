from store import CASES,TRANSACTIONS,DEVICE,CONTACTS,POLICIES,EXISTING_ACTIONS,CONTROLS

class ToolError(Exception):
    pass

def _fault(case_id, tool):
    f=CONTROLS.get(case_id,{}).get('tool_faults',{}).get(tool)
    if f=='timeout':
        raise ToolError(f'{tool}_timeout')
    if f=='unavailable':
        raise ToolError(f'{tool}_unavailable')

def get_case(case_id):
    if case_id not in CASES:
        raise ToolError('case_not_found')
    return CASES[case_id]

def get_transaction(case_id, transaction_id):
    _fault(case_id,'get_transaction')
    if transaction_id not in TRANSACTIONS:
        raise ToolError('transaction_not_found')
    return TRANSACTIONS[transaction_id]

def get_device_signals(case_id, customer_id):
    _fault(case_id,'get_device_signals')
    if customer_id not in DEVICE:
        raise ToolError('device_signals_not_found')
    return DEVICE[customer_id]

def get_prior_contacts(case_id, customer_id):
    _fault(case_id,'get_prior_contacts')
    return CONTACTS.get(customer_id,{'similar_disputes_12m':None,'notes':[]})

def get_policy(case_id, issue):
    _fault(case_id,'get_policy')
    if issue not in POLICIES:
        raise ToolError('unsupported_issue')
    p=dict(POLICIES[issue])
    override=CONTROLS.get(case_id,{}).get('policy_override')
    if override:
        p.update(override)
    return p

def get_existing_actions(case_id):
    return EXISTING_ACTIONS.get(case_id,[])

def execute_action(case_id, action, approval_token):
    if not approval_token:
        raise ToolError('human_approval_required')
    if CONTROLS.get(case_id,{}).get('execution_fault')=='timeout':
        raise ToolError('execution_service_timeout')
    existing=get_existing_actions(case_id)
    if any(x['type']==action and x['status']=='active' for x in existing):
        raise ToolError('duplicate_action_blocked')
    return {'case_id':case_id,'action':action,'status':'executed','approval_token':approval_token}

TOOL_SCHEMAS={
    'get_transaction':{'description':'Retrieve the disputed transaction','args':['case_id','transaction_id']},
    'get_device_signals':{'description':'Retrieve fraud device/login risk signals','args':['case_id','customer_id']},
    'get_prior_contacts':{'description':'Retrieve prior customer fraud contacts','args':['case_id','customer_id']},
    'get_policy':{'description':'Retrieve current policy for the case issue','args':['case_id','issue']},
    'get_existing_actions':{'description':'Check actions already active on the case','args':['case_id']},
}
