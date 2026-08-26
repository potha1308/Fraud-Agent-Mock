import os, json, requests
from store import CONTROLS

class ProviderError(Exception):
    pass

class MalformedProviderOutput(Exception):
    pass

class BaseProvider:
    def next_step(self, system_prompt, state):
        raise NotImplementedError

class OfflineProvider(BaseProvider):
    """Deterministic provider used for local development and evaluation."""
    def next_step(self, system_prompt, state):
        cid=state['case']['case_id']
        c=CONTROLS[cid]
        behavior=c.get('provider_behavior')
        if behavior=='error':
            raise ProviderError('simulated_provider_error')
        if behavior=='malformed':
            return {'banana':'not a valid agent step'}

        called=set(state['tools_called'])
        case=state['case']
        if 'get_transaction' not in called:
            return {'type':'tool','tool':'get_transaction','args':{'case_id':cid,'transaction_id':case['disputed_transaction_id']}}
        if 'get_device_signals' not in called:
            return {'type':'tool','tool':'get_device_signals','args':{'case_id':cid,'customer_id':case['customer_id']}}
        if 'get_prior_contacts' not in called:
            return {'type':'tool','tool':'get_prior_contacts','args':{'case_id':cid,'customer_id':case['customer_id']}}
        if 'get_policy' not in called:
            return {'type':'tool','tool':'get_policy','args':{'case_id':cid,'issue':case['issue']}}
        if 'get_existing_actions' not in called:
            return {'type':'tool','tool':'get_existing_actions','args':{'case_id':cid}}

        scenario=c['scenario']
        action=c.get('forced_action')
        confidence=c.get('forced_confidence')
        if not action:
            action={
                'recommend_temporary_protection':'temporary_protection',
                'recommend_manual_verification':'manual_verification',
                'recommend_temporary_card_lock':'temporary_card_lock',
                'recommend_identity_verification':'request_identity_verification',
                'recommend_specialist_review':'specialist_review',
                'recommend_no_action':'no_action_monitor',
                'contacts_timeout_degraded':'temporary_protection',
                'execution_service_failure':'temporary_protection',
                'human_rejection':'temporary_protection',
                'low_confidence':'temporary_protection',
            }.get(scenario,'temporary_protection')
        if confidence is None:
            confidence={
                'recommend_no_action':.96,
                'recommend_specialist_review':.82,
                'recommend_manual_verification':.88,
            }.get(scenario,.94)
        return {
            'type':'final','outcome':'recommend','action':action,
            'confidence':confidence,
            'rationale':f'Recommendation generated for scenario: {scenario}.',
            'safe_stop_reason':None
        }

class OpenAIProvider(BaseProvider):
    def __init__(self):
        self.key=os.environ['OPENAI_API_KEY']
        self.model=os.getenv('OPENAI_MODEL','gpt-5-mini')

    def next_step(self, system_prompt, state):
        schema={
            'type':'object',
            'properties':{
                'type':{'type':'string','enum':['tool','final']},
                'tool':{'type':['string','null']},
                'args':{'type':'object'},
                'outcome':{'type':['string','null']},
                'action':{'type':['string','null']},
                'confidence':{'type':['number','null']},
                'rationale':{'type':['string','null']},
                'safe_stop_reason':{'type':['string','null']},
            },
            'required':['type','tool','args','outcome','action','confidence','rationale','safe_stop_reason'],
            'additionalProperties':False
        }
        body={
            'model':self.model,
            'input':[
                {'role':'system','content':[{'type':'input_text','text':system_prompt}]},
                {'role':'user','content':[{'type':'input_text','text':json.dumps(state)}]}
            ],
            'text':{'format':{'type':'json_schema','name':'agent_step','schema':schema,'strict':True}}
        }
        r=requests.post(
            'https://api.openai.com/v1/responses',
            headers={'Authorization':f'Bearer {self.key}','Content-Type':'application/json'},
            json=body, timeout=60
        )
        if r.status_code>=300:
            raise ProviderError(f'openai_error:{r.status_code}')
        data=r.json()
        text=data.get('output_text')
        if not text:
            for item in data.get('output',[]):
                for part in item.get('content',[]):
                    if part.get('text'):
                        text=part['text']; break
                if text: break
        try:
            return json.loads(text)
        except Exception as e:
            raise MalformedProviderOutput(str(e))

class AnthropicProvider(BaseProvider):
    def __init__(self):
        self.key=os.environ['ANTHROPIC_API_KEY']
        self.model=os.getenv('ANTHROPIC_MODEL','claude-sonnet-4-5')

    def next_step(self, system_prompt, state):
        body={
            'model':self.model,'max_tokens':800,
            'system':system_prompt+' Return exactly one JSON object.',
            'messages':[{'role':'user','content':json.dumps(state)}]
        }
        r=requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key':self.key,'anthropic-version':'2023-06-01','content-type':'application/json'},
            json=body, timeout=60
        )
        if r.status_code>=300:
            raise ProviderError(f'anthropic_error:{r.status_code}')
        text=''.join(x.get('text','') for x in r.json().get('content',[]) if x.get('type')=='text').strip()
        if text.startswith('```'):
            text=text.split('\n',1)[1].rsplit('```',1)[0]
        try:
            return json.loads(text)
        except Exception as e:
            raise MalformedProviderOutput(str(e))

class BedrockProvider(BaseProvider):
    def __init__(self):
        import boto3
        self.model=os.environ['BEDROCK_MODEL_ID']
        self.client=boto3.client('bedrock-runtime',region_name=os.getenv('AWS_REGION','us-east-1'))

    def next_step(self, system_prompt, state):
        response=self.client.converse(
            modelId=self.model,
            system=[{'text':system_prompt}],
            messages=[{'role':'user','content':[{'text':json.dumps(state)}]}],
            inferenceConfig={'maxTokens':800,'temperature':0}
        )
        text=''.join(x.get('text','') for x in response['output']['message']['content'] if 'text' in x).strip()
        if text.startswith('```'):
            text=text.split('\n',1)[1].rsplit('```',1)[0]
        try:
            return json.loads(text)
        except Exception as e:
            raise MalformedProviderOutput(str(e))

def get_provider():
    p=os.getenv('LLM_PROVIDER','offline').lower()
    if p=='openai': return OpenAIProvider()
    if p=='anthropic': return AnthropicProvider()
    if p=='bedrock': return BedrockProvider()
    return OfflineProvider()
