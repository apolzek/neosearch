from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# User Models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None


# Bookmark Models
class BookmarkCreate(BaseModel):
    url: str
    description: str
    tags: List[str] = []
    category: str = "USER"


class BookmarkResponse(BaseModel):
    id: int
    user_id: int
    url: str
    description: str
    tags: List[str]
    category: str
    source: Optional[str] = None
    created_at: str


# Repository Models
class RepositoryCreate(BaseModel):
    name: str
    url: str


class RepositoryResponse(BaseModel):
    id: int
    user_id: int
    name: str
    url: str
    last_synced: Optional[str] = None
    created_at: str


class RepositoryImportResult(BaseModel):
    repository_id: int
    bookmarks_imported: int
    message: str
