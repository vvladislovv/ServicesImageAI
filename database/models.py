from pydantic import BaseModel
from typing import Optional, Dict


class Users(BaseModel):
    chatId: int
    idMessage: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    created_at: str


class UsersAI(BaseModel):
    chatId: int
    typeGpt: str
    in_progress: bool = False
    created_at: str


class UsersPayPass(BaseModel):
    chatId: int
    id_pass: int
    tarif: str
    updated_pass: str
    expiration_date: Optional[str] = None  # Date when subscription expires
    created_at: str


class StaticAIUsers(BaseModel):
    chatId: int
    dataGpt: Dict[str, int]
    created_at: str


class ChatHistory(BaseModel):
    user_id: int
    message_text: str
    response_text: str
    model: str
    timestamp: str
    context: str


class VoiceMessages(BaseModel):
    chatId: int
    voice_data: str
    voice_name: str
    virtual_path: str
    created_at: str
