from pydantic import BaseModel, Field
from typing import Optional

class UserPreferences(BaseModel):
    # Dining preferences
    dietary_restrictions: Optional[str] = Field(default=None, description="Allergies or dietary rules (e.g., vegan, gluten-free).")
    preferred_dining_time: Optional[str] = Field(default=None, description="Usual preferred time for dinner or lunch.")
    
    # Hotel/Room preferences
    preferred_bed_size: Optional[str] = Field(default=None, description="Preferred bed type (e.g., King, Queen, Twin).")
    room_preference: Optional[str] = Field(default=None, description="General room preferences (e.g., high floor, ocean view, quiet room).")

class MemoryExtraction(BaseModel):
    should_update: bool = Field(description="True if the conversation contains new, stable preferences to remember.")
    preferences: UserPreferences = Field(description="The extracted preferences.")