from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt

# In-memory storage for users: {username: hashed_password}
users_db: Dict[str, str] = {}

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = "dev-secret-key"  # For MVP only, replace in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

class UserRegister(BaseModel):
    username: str = Field(..., description="Unique username for the user")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")

class UserLogin(BaseModel):
    username: str = Field(..., description="Unique username for the user")
    password: str = Field(..., description="User password")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# PUBLIC_INTERFACE
@router.post("/register", response_model=Token, status_code=201, summary="Register a new user", description="Register a new user with a unique username and password.")
def register_user(user: UserRegister):
    """Register a new user, with hashed password. Returns JWT access token."""
    if user.username in users_db:
        raise HTTPException(status_code=409, detail="Username already registered")
    hashed_pw = hash_password(user.password)
    users_db[user.username] = hashed_pw
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# PUBLIC_INTERFACE
@router.post("/login", response_model=Token, summary="Login as an existing user", description="Authenticate user and return a JWT access token on success.")
def login_user(user: UserLogin):
    """Authenticate existing user, returning a JWT token if successful."""
    hashed_pw = users_db.get(user.username)
    if not hashed_pw or not verify_password(user.password, hashed_pw):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}
