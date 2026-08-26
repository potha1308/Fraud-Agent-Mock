from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from agent import FraudAgent

app=FastAPI(title='Fraud Assist Agent API',version='2.1')
agent=FraudAgent()

class InvestigateRequest(BaseModel):
    case_id:str

class ApproveRequest(BaseModel):
    case_id:str
    action_id:str
    approved_by:str

class RejectRequest(BaseModel):
    case_id:str
    action_id:str
    rejected_by:str
    reason:str='associate_rejected'

@app.get('/')
def root():
    index=Path(__file__).resolve().parent/'index.html'
    return FileResponse(index)

@app.get('/api-info')
def api_info():
    return {
        'name':'Fraud Assist Agent API',
        'version':'2.1',
        'status':'ready',
        'provider':agent.provider.__class__.__name__,
        'docs':'/docs',
        'cases':'/cases'
    }

@app.get('/cases')
def list_cases():
    from store import CASES
    return {'count':len(CASES),'cases':list(CASES.values())}

@app.get('/health')
def health():
    return {'status':'ok','provider':agent.provider.__class__.__name__}

@app.post('/investigate')
def investigate(r:InvestigateRequest):
    return agent.investigate(r.case_id).model_dump()

@app.post('/approve')
def approve(r:ApproveRequest):
    try:
        return agent.approve(r.case_id,r.action_id,r.approved_by)
    except Exception as e:
        raise HTTPException(400,str(e))

@app.post('/reject')
def reject(r:RejectRequest):
    try:
        return agent.reject(r.case_id,r.action_id,r.rejected_by,r.reason)
    except Exception as e:
        raise HTTPException(400,str(e))

@app.get('/trace/{case_id}')
def trace(case_id:str):
    return agent.trace(case_id)
