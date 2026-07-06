# models/user.py

from pydantic import BaseModel
from typing import Optional
from datetime import date, time

class ProfileData(BaseModel):
    birth_date: Optional[str] = None
    birth_time: Optional[str] = None
    birth_city: Optional[str] = None
    current_city: Optional[str] = None
    profession: Optional[str] = None

class ProfileRequest(BaseModel):
    request: dict
    profile: ProfileData

class AuthRequest(BaseModel):
    platform: str
    platform_user_id: str
    password: Optional[str] = None