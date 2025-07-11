from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .game import router as game_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PUBLIC_INTERFACE
app.include_router(auth_router)
# PUBLIC_INTERFACE
app.include_router(game_router)

@app.get("/")
def health_check():
    """Health check endpoint for API."""
    return {"message": "Healthy"}
