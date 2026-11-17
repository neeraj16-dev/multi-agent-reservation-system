from pydantic import BaseModel, Field
from typing import Literal

class UserPreferences(BaseModel):

    preferred_seating: Literal[
        "window",
        "outdoor",
        "indoor",
        "center"
    ] | None = None

    preferred_party_size: int | None = Field(
        default=None,
        ge=1,
        le=20
    )

class MemoryExtraction(BaseModel):

    should_update: bool = Field(
        description="Whether the conversation contains an explicitly stated, useful long-term preference."
    )

    preferences: UserPreferences