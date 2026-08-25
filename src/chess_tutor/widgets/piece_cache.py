from pathlib import Path

import chess
from PIL import Image, ImageTk

from ..chess_utils import asset_filename

class PieceImageCache:
    """Carica da disco i PNG dei pezzi (pre-renderizzati ad alta
    risoluzione in assets/pieces/) e li ridimensiona con PIL alla
    dimensione richiesta, mettendo in cache sia l'originale ad alta
    risoluzione sia le versioni gia' scalate per ogni square_size usata."""

    def __init__(self, assets_dir: Path):
        self._assets_dir = assets_dir
        self._originals = {}  # symbol -> PIL.Image ad alta risoluzione
        self._scaled_cache = {}  # (symbol, size) -> ImageTk.PhotoImage

    def _load_original(self, piece: chess.Piece) -> Image.Image:
        symbol = piece.symbol()
        original = self._originals.get(symbol)
        if original is None:
            path = self._assets_dir / asset_filename(piece)
            if not path.exists():
                raise FileNotFoundError(
                    f"Immagine pezzo mancante: {path}. "
                    "Assicurati che la cartella assets/pieces/ sia distribuita col progetto."
                )
            original = Image.open(path).convert("RGBA")
            self._originals[symbol] = original
        return original

    def get(self, piece: chess.Piece, size: int) -> ImageTk.PhotoImage:
        key = (piece.symbol(), size)
        cached = self._scaled_cache.get(key)
        if cached is not None:
            return cached

        original = self._load_original(piece)
        resized = original.resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        self._scaled_cache[key] = photo
        return photo

    def clear(self):
        self._scaled_cache.clear()