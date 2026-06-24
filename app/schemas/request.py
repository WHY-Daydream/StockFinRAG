from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    session_id: str = Field(default="")
    history: Optional[List[Dict[str, Any]]] = Field(default=None)


class IngestRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class SeedRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


class CrawlRequest(BaseModel):
    config: Optional[str] = Field(default=None)