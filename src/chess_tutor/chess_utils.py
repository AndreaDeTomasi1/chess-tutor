import chess
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "pieces"

MIN_SQUARE_SIZE = 36
DEFAULT_SQUARE_SIZE = 64
LEFT_PANEL_WIDTH = 220   # elenco mosse
RIGHT_PANEL_WIDTH = 260  # controlli + pannello tutor

LIGHT_COLOR = "#eeeed2"
DARK_COLOR = "#769656"
SELECT_COLOR = "#f6f669"
MOVE_HINT_COLOR = "#8ab4f8"
CAPTURE_HINT_COLOR = "#eb5757"
LAST_MOVE_LIGHT = "#cdd26a"
LAST_MOVE_DARK = "#aaa23a"
BEST_MOVE_COLOR = "#e08f28"

INITIAL_PIECE_COUNTS = {
    chess.PAWN: 8,
    chess.KNIGHT: 2,
    chess.BISHOP: 2,
    chess.ROOK: 2,
    chess.QUEEN: 1,
    chess.KING: 1,
}
CAPTURED_PIECE_SIZE = 24
CAPTURED_PADDING = 4

RESIZE_DEBOUNCE_MS = 150  # attesa dopo l'ultimo evento di resize prima di ridisegnare

def asset_filename(piece: chess.Piece) -> str:
    color = "w" if piece.color == chess.WHITE else "b"
    return f"{color}{piece.symbol().upper()}.png"  # es. wN.png, bQ.png

def get_captured_pieces(board: chess.Board):
    """Ritorna { chess.WHITE: [chess.Piece,...], chess.BLACK: [chess.Piece,...] }
    cioe' i pezzi che ciascun colore ha PERSO (= catturati dall'avversario),
    dedotti confrontando i pezzi ancora presenti con il conteggio iniziale."""
    remaining = {chess.WHITE: {}, chess.BLACK: {}}
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            remaining[piece.color][piece.piece_type] = (
                remaining[piece.color].get(piece.piece_type, 0) + 1
            )

    captured = {chess.WHITE: [], chess.BLACK: []}
    for color in (chess.WHITE, chess.BLACK):
        for piece_type, initial_count in INITIAL_PIECE_COUNTS.items():
            missing = initial_count - remaining[color].get(piece_type, 0)
            for _ in range(missing):
                captured[color].append(chess.Piece(piece_type, color))
    return captured
