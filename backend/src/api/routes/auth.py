from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any

from src.api.dependencies import get_pipeline_repository, get_current_user
from src.repositories import MongoPipelineRepository
from src.api.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class UserLoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    username: str

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegisterRequest,
    repo: MongoPipelineRepository = Depends(get_pipeline_repository)
):
    existing = repo.get_user_by_username(data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if this is the first user
    is_first = repo.users.count_documents({}) == 0
    
    pwd_hash = hash_password(data.password)
    user = repo.create_user(data.username, pwd_hash)
    
    # If this is the first user, auto-claim any existing unowned assets!
    if is_first:
        claimed = repo.claim_unowned_assets(user["_id"])
        print(f"First user '{data.username}' registered. Claimed {claimed} unowned assets.")
        
    return {"id": user["_id"], "username": user["username"]}

@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLoginRequest,
    repo: MongoPipelineRepository = Depends(get_pipeline_repository)
):
    user = repo.get_user_by_username(data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Claim any assets ingested without an owner (e.g. ingested before this user existed)
    claimed = repo.claim_unowned_assets(user["_id"])
    if claimed:
        print(f"Login '{data.username}': claimed {claimed} previously unowned assets.")

    token = create_access_token(data={"sub": user["_id"]})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"id": current_user["_id"], "username": current_user["username"]}
