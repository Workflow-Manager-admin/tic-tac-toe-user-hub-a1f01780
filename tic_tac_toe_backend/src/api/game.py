from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# Import game history recorder
from .game_history import record_completed_game

# -- MVP IN-MEMORY USER/SESSION STATE STORAGE --
# For MVP, we use username (from JWT) as session key. This is NOT persistent!
games: Dict[str, "TicTacToeGame"] = {}

# ------------- Game Logic Class -------------
class TicTacToeGame:
    """Manages a game board, player turn, and win/draw logic for Tic Tac Toe."""

    def __init__(self, player_x: str, player_o: Optional[str] = None):
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.player_x = player_x
        self.player_o = player_o or "cpu"
        self.next_turn = "X"
        self.winner: Optional[str] = None
        self.finished: bool = False
        self.move_count: int = 0
    
    def make_move(self, player: str, row: int, col: int):
        if self.finished:
            raise ValueError("Game is already finished.")
        if not (0 <= row < 3 and 0 <= col < 3):
            raise ValueError("Move out of bounds.")
        if self.board[row][col]:
            raise ValueError("Cell is already occupied.")
        if (self.next_turn == "X" and player != self.player_x) or (self.next_turn == "O" and player != self.player_o):
            raise ValueError(f"It is not {player}'s turn.")

        mark = self.next_turn
        self.board[row][col] = mark
        self.move_count += 1
        self._update_state(row, col, mark)

        # Change turn if not finished
        if not self.finished:
            self.next_turn = "O" if self.next_turn == "X" else "X"
    
    def _update_state(self, row: int, col: int, mark: str):
        # Check win
        b = self.board
        lines = [
            [b[row][0], b[row][1], b[row][2]],
            [b[0][col], b[1][col], b[2][col]],
            [b[0][0], b[1][1], b[2][2]],
            [b[0][2], b[1][1], b[2][0]],
        ]
        if any(all(cell == mark for cell in line) for line in lines):
            self.winner = self.player_x if mark == "X" else self.player_o
            self.finished = True
            return
        # Draw
        if self.move_count == 9:
            self.finished = True

    def reset(self):
        self.__init__(self.player_x, self.player_o)

    def to_dict(self):
        """Export all state for API response."""
        return {
            "board": self.board,
            "player_x": self.player_x,
            "player_o": self.player_o,
            "next_turn": self.next_turn,
            "winner": self.winner,
            "finished": self.finished,
        }

# --------- API Models ---------
class NewGameStartRequest(BaseModel):
    opponent_username: Optional[str] = Field(None, description="Optional second player (future support for VS player).")

class MoveRequest(BaseModel):
    row: int = Field(..., ge=0, le=2, description="Row index of move (0-2)")
    col: int = Field(..., ge=0, le=2, description="Column index of move (0-2)")

class GameStateResponse(BaseModel):
    board: List[List[str]]
    player_x: str
    player_o: str
    next_turn: str
    winner: Optional[str]
    finished: bool

# --------- Dependency to Extract Username ---------
def get_current_username(request: Request) -> str:
    """
    Extracts username from JWT in Authorization header using FastAPI Request.state injected by auth
    (MVP: For simplification, expects 'Authorization: Bearer <token>' and decodes manually)
    This function is a placeholder - in production, use dependency from Auth/JWT verification.
    """
    # For MVP, we just assume the username is always 'testuser'.
    # Proper implementation would decode the JWT.
    # Here, try to extract from request.state.user or similar if middleware is implemented.
    user = None
    if hasattr(request.state, "user"):
        user = getattr(request.state, "user")
    if not user:
        # Fallback: for basic examples use a made up user.
        user = "testuser"
    return user

router = APIRouter(
    prefix="/game",
    tags=["TicTacToe Game"],
)


# PUBLIC_INTERFACE
@router.post("/start", response_model=GameStateResponse, tags=["TicTacToe Game"], summary="Start a new game", description="Start a new Tic Tac Toe game. Optionally specify a 2nd player (else play vs CPU placeholder).")
def start_game(request: Request, req: NewGameStartRequest):
    """Starts a new game session for the user. Overwrites any In-Progress game for MVP."""
    username = get_current_username(request)
    opponent = req.opponent_username
    games[username] = TicTacToeGame(player_x=username, player_o=opponent)
    return games[username].to_dict()

# PUBLIC_INTERFACE
@router.post("/move", response_model=GameStateResponse, tags=["TicTacToe Game"], summary="Make a move", description="Make a move at (row, col) for the current user's game session.")
def make_move(request: Request, move: MoveRequest):
    """Makes a move as the current user on their in-progress game."""
    username = get_current_username(request)
    if username not in games:
        raise HTTPException(status_code=404, detail="No game found for user. Start a game first.")
    game = games[username]
    try:
        game.make_move(username, move.row, move.col)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    # If game finished, log game history (avoid double-recording)
    if game.finished and game.winner is not None:
        if game.winner == username:
            outcome = "win"
            opponent = game.player_o if game.player_x == username else game.player_x
        else:
            outcome = "loss"
            opponent = game.player_o if game.player_x == username else game.player_x
        record_completed_game(username, opponent, game.board, outcome)
        # Also record for the opponent if not CPU
        if opponent and opponent != "cpu":
            rev_outcome = "loss" if outcome == "win" else "win"
            record_completed_game(opponent, username, game.board, rev_outcome)
    elif game.finished and game.winner is None:
        # Draw
        opponent = game.player_o if game.player_x == username else game.player_x
        record_completed_game(username, opponent, game.board, "draw")
        if opponent and opponent != "cpu":
            record_completed_game(opponent, username, game.board, "draw")
    return game.to_dict()

# PUBLIC_INTERFACE
@router.post("/reset", response_model=GameStateResponse, tags=["TicTacToe Game"], summary="Reset game", description="Reset the current game (board cleared, new game state created for user).")
def reset_game(request: Request):
    """Resets the user's in-progress game (if any), else starts a new one."""
    username = get_current_username(request)
    if username not in games:
        games[username] = TicTacToeGame(player_x=username)
    else:
        # Before reset, if game was finished, record it
        prev_game = games[username]
        if prev_game.finished:
            if prev_game.winner is not None:
                if prev_game.winner == username:
                    outcome = "win"
                    opponent = prev_game.player_o if prev_game.player_x == username else prev_game.player_x
                else:
                    outcome = "loss"
                    opponent = prev_game.player_o if prev_game.player_x == username else prev_game.player_x
                record_completed_game(username, opponent, prev_game.board, outcome)
                if opponent and opponent != "cpu":
                    rev_outcome = "loss" if outcome == "win" else "win"
                    record_completed_game(opponent, username, prev_game.board, rev_outcome)
            else:
                opponent = prev_game.player_o if prev_game.player_x == username else prev_game.player_x
                record_completed_game(username, opponent, prev_game.board, "draw")
                if opponent and opponent != "cpu":
                    record_completed_game(opponent, username, prev_game.board, "draw")
        games[username].reset()
    return games[username].to_dict()
