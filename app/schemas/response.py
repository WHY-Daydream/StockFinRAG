from pydantic import BaseModel
from typing import Optional, List, Dict


class AskResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    compliance: str
    compliance_reason: Optional[str] = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "StockFinRAG"


class IngestResponse(BaseModel):
    status: str
    processed: int


class SeedResponse(BaseModel):
    status: str
    imported: int
    vectorized: int
    message: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[List[Dict]] = None
    traceback: Optional[str] = None