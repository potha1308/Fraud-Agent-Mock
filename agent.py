import tools
from models import EvidenceItem,Recommendation,TraceEvent,ActionRecord
from providers import get_provider,ProviderError,MalformedProviderOutput
import uuid

SYSTEM_PROMPT="""
You are an enterprise fraud-assistance agent. You may choose tools iteratively and then return a final recommendation.
Use only tool evidence. Never invent facts.
Available tools: get_transaction, get_device_signals, get_prior_contacts, get_policy, get_existing_actions.
Critical rules:
- transaction and device risk are required for a fraud recommendation.
- policy must exist and have status=active.
- never recommend an already-active action.
- do not propose actions outside the allow-list or policy.
- customer-impacting write actions require human approval.
- prefer reversible actions.
- if uncertainty is high, recommend specialist_review rather than over-automating.
Return one JSON agent step at a time: either a tool request or a final recommendation.
"""

ALLOWED_ACTIONS={
    'temporary_protection','manual_verification','temporary_card_lock',
    'request_identity_verification','specialist_review','no_action_monitor'
}
APPROVAL_ACTIONS=ALLOWED_ACTIONS-{'no_action_monitor'}
MIN_CONFIDENCE=.70

class FraudAgent:
    def __init__(self):
        self.provider=get_provider()
        self.traces={}
        self.pending={}
        self.executed=[]
        self.rejected=[]

    def _trace(self,cid,event_type,name,detail=None):
        self.traces.setdefault(cid,[]).append(
            TraceEvent(type=event_type,name=name,detail=detail or {})
        )

    def _evidence(self,tool,result):
        if isinstance(result,dict):
            ref=str(result.get('transaction_id') or result.get('customer_id') or result.get('policy_id') or 'case')
            payload=result
        else:
            ref='case'; payload={'value':result}
        return EvidenceItem(source=tool,ref=ref,summary=str(result)[:180],payload=payload)

    def investigate(self,case_id):
        try:
            case=tools.get_case(case_id)
        except tools.ToolError as e:
            return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Case could not be loaded.',safe_stop_reason=str(e))

        self._trace(case_id,'tool','get_case',{'ok':True})
        state={'case':case,'evidence':{},'tools_called':[],'tool_errors':[]}
        evidence=[]
        warnings=[]

        for step_num in range(10):
            try:
                self._trace(case_id,'model','next_step',{'step':step_num,'provider':self.provider.__class__.__name__})
                step=self.provider.next_step(SYSTEM_PROMPT,state)
            except ProviderError as e:
                self._trace(case_id,'model_error','provider',{'error':str(e)})
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Model provider unavailable; return control to associate.',evidence=evidence,warnings=warnings,safe_stop_reason='provider_error')
            except MalformedProviderOutput as e:
                self._trace(case_id,'model_error','malformed_output',{'error':str(e)})
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Model output could not be validated.',evidence=evidence,warnings=warnings,safe_stop_reason='malformed_model_output')

            if not isinstance(step,dict) or step.get('type') not in ('tool','final'):
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Model output failed schema validation.',evidence=evidence,warnings=warnings,safe_stop_reason='malformed_model_output')

            if step['type']=='tool':
                name=step.get('tool')
                args=step.get('args') or {}
                if name not in tools.TOOL_SCHEMAS:
                    return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Agent requested an unsupported tool.',evidence=evidence,warnings=warnings,safe_stop_reason='unsupported_tool')
                try:
                    result=getattr(tools,name)(**args)
                    state['evidence'][name]=result
                    state['tools_called'].append(name)
                    evidence.append(self._evidence(name,result))
                    self._trace(case_id,'tool',name,{'ok':True})
                except tools.ToolError as e:
                    err=str(e)
                    state['tools_called'].append(name)
                    state['tool_errors'].append({'tool':name,'error':err})
                    self._trace(case_id,'tool_error',name,{'error':err})
                    if name=='get_prior_contacts':
                        warnings.append('Prior-contact history unavailable; continuing with core evidence.')
                        state['evidence'][name]={'unavailable':True}
                        continue
                    reason={
                        'get_transaction':'transaction_tool_timeout' if 'timeout' in err else 'critical_transaction_missing',
                        'get_device_signals':'device_tool_timeout' if 'timeout' in err else 'critical_device_missing',
                        'get_policy':'policy_tool_timeout' if 'timeout' in err else 'unsupported_issue',
                    }.get(name,'critical_tool_failure')
                    return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale=f'Critical tool failed: {name}.',evidence=evidence,warnings=warnings,safe_stop_reason=reason)
                continue

            # Apply deterministic safety checks before returning a recommendation.
            tx=state['evidence'].get('get_transaction')
            device=state['evidence'].get('get_device_signals')
            policy=state['evidence'].get('get_policy')
            existing=state['evidence'].get('get_existing_actions',[])

            if not tx:
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Transaction evidence missing.',evidence=evidence,warnings=warnings,safe_stop_reason='critical_transaction_missing')
            if not device or device.get('risk_score') is None:
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Device risk evidence missing.',evidence=evidence,warnings=warnings,safe_stop_reason='critical_device_missing')
            if not policy:
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Policy missing.',evidence=evidence,warnings=warnings,safe_stop_reason='unsupported_issue')
            if policy.get('status')=='conflict':
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Policy sources conflict.',evidence=evidence,warnings=warnings,safe_stop_reason='policy_conflict')
            if policy.get('status')=='stale':
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Policy is stale.',evidence=evidence,warnings=warnings,safe_stop_reason='policy_stale')
            if policy.get('status')=='inactive':
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Policy is inactive.',evidence=evidence,warnings=warnings,safe_stop_reason='policy_inactive')

            action=step.get('action')
            confidence=float(step.get('confidence') or 0)
            if confidence<MIN_CONFIDENCE:
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=confidence,rationale='Recommendation confidence is below release threshold.',evidence=evidence,warnings=warnings,safe_stop_reason='low_confidence')
            if action not in ALLOWED_ACTIONS:
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=confidence,rationale='Unsupported action proposed.',evidence=evidence,warnings=warnings,safe_stop_reason='unsupported_action')
            if action not in set(policy.get('allowed_actions',[])):
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=confidence,rationale='Action is not allowed by current policy.',evidence=evidence,warnings=warnings,safe_stop_reason='action_not_allowed')
            if any(x.get('type')==action and x.get('status')=='active' for x in existing):
                return Recommendation(case_id=case_id,outcome='safe_stop',confidence=confidence,rationale='Action is already active; duplicate blocked.',evidence=evidence,warnings=warnings,safe_stop_reason='duplicate_action')

            if action=='no_action_monitor':
                return Recommendation(case_id=case_id,outcome='recommend',action=action,confidence=confidence,rationale=step.get('rationale') or '',evidence=evidence,warnings=warnings,requires_human_approval=False)

            record=ActionRecord(case_id=case_id,action=action)
            self.pending[record.action_id]=record
            self._trace(case_id,'gate','human_approval_gate',{'action_id':record.action_id,'action':action})
            return Recommendation(case_id=case_id,outcome='recommend',action=action,confidence=confidence,rationale=step.get('rationale') or '',evidence=evidence,warnings=warnings,requires_human_approval=True,proposed_action_id=record.action_id)

        return Recommendation(case_id=case_id,outcome='safe_stop',confidence=1,rationale='Agent exceeded maximum steps.',evidence=evidence,warnings=warnings,safe_stop_reason='max_steps_exceeded')

    def approve(self,case_id,action_id,approved_by):
        if action_id not in self.pending:
            raise ValueError('unknown_action_id')
        rec=self.pending[action_id]
        if rec.case_id!=case_id:
            raise ValueError('case_action_mismatch')
        token=f'approval:{approved_by}:{uuid.uuid4()}'
        self._trace(case_id,'human','approval',{'approved_by':approved_by,'action':rec.action})
        try:
            result=tools.execute_action(case_id,rec.action,token)
        except tools.ToolError as e:
            self._trace(case_id,'tool_error','execute_action',{'error':str(e)})
            return {'case_id':case_id,'action':rec.action,'status':'failed','reason':'execution_service_failure'}
        rec.status='executed'; rec.approved_by=approved_by
        self.executed.append(result)
        self._trace(case_id,'tool','execute_action',{'ok':True,'action':rec.action})
        return result

    def reject(self,case_id,action_id,rejected_by,reason='associate_rejected'):
        if action_id not in self.pending:
            raise ValueError('unknown_action_id')
        rec=self.pending[action_id]
        if rec.case_id!=case_id:
            raise ValueError('case_action_mismatch')
        rec.status='rejected'; rec.rejected_by=rejected_by
        self.rejected.append(rec.model_dump())
        self._trace(case_id,'human','rejection',{'rejected_by':rejected_by,'reason':reason})
        return {'case_id':case_id,'action':rec.action,'status':'rejected','reason':'human_rejected'}

    def trace(self,case_id):
        return [x.model_dump() for x in self.traces.get(case_id,[])]
