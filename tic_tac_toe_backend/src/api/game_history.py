from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime

# In-memory storage mapping usernames to their list of completed games
game_histories: Dict[str, List[dict]] = {}

# --------- API Models ---------
class BoardState(BaseModel):
    board: List[List[str]] = Field(..., description="Final state of the 3x3 game board")

class GameHistoryEntry(BaseModel):
    timestamp: datetime = Field(..., description="When the game finished")
    board: List[List[str]] = Field(..., description="Final state of game board")
    outcome: str = Field(..., description="Game outcome: 'win', 'loss', or 'draw'")
    opponent: str = Field(..., description="Opponent's username or 'cpu'")

class GameHistoryResponse(BaseModel):
    games: List[GameHistoryEntry] = Field(..., description="List of completed games for the user")

def get_current_username(request: Request) -> str:
    """
    Extract username for MVP. For now, get from request.state.user or 'testuser'.
    """
    user = getattr(request.state, "user", None)
    if not user:
        user = "testuser"
    return user

router = APIRouter(
    prefix="/history",
    tags=["Game History"]
)

# PUBLIC_INTERFACE
@router.get("/", response_model=GameHistoryResponse, summary="Get completed game history for current user", description="Returns a list of completed Tic Tac Toe games played by the authenticated user, most recent first.", tags=["Game History"])
def fetch_game_history(request: Request):
    """
    Returns the game history for the current user.
    """
    username = get_current_username(request)
    history = game_histories.get(username, [])
    return {"games": sorted(history, key=lambda g: g["timestamp"], reverse=True)}

# PUBLIC_INTERFACE
def record_completed_game(username: str, opponent: str, board: List[List[str]], outcome: str):
    """
    Records a completed game for a user.
    Args:
        username (str): The username who made the API call (current player)
        opponent (str): Rival username or 'cpu'
        board (List[List[str]]): Final 3x3 board state
        outcome (str): "win", "loss", or "draw" (from current user's perspective)
    """
    entry = {
        "timestamp": datetime.utcnow(),
        "board": [row[:] for row in board],  # Deep copy
        "opponent": opponent,
        "outcome": outcome
    }
    if username not in game_histories:
        game_histories[username] = []
    game_histories[username].append(entry)
