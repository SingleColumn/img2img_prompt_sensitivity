from __future__ import annotations

from pydantic import BaseModel


class ModelChoice(BaseModel):
    id: str
    provider: str
    display_name: str
    description: str


class InputImageChoice(BaseModel):
    file_name: str
    url: str

