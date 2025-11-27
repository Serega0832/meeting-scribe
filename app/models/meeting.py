from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel

class Meeting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    transcription: str = Field(default="")
    summary: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)