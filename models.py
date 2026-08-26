from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

class TraceEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: str
    name: str
    detail: Dict[str, Any] = Field(default_factory=dict)

class EvidenceItem(BaseModel):
    source: str
    ref: str
    summary: str
    payload: Dict[str, Any]

class Recommendation(BaseModel):
    case_id: str
    outcome: str
    action: Optional[str] = None
    confidence: float = 0.0
    rationale: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    safe_stop_reason: Optional[str] = None
    proposed_action_id: Optional[str] = None

class ActionRecord(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str
    action: str
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    status: str = 'proposed'
