"""Individua il percorso locale dell'eseguibile Stockfish.

Ordine di ricerca:
1. Variabile d'ambiente STOCKFISH_PATH
2. Cartella ./engines/ nella root del progetto (dove lo mette install.sh/install.ps1)
3. Stockfish disponibile nel PATH di sistema (es. installato con apt/brew)
"""

import os
import platform
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _project_root() -> Path:
    # src/chess_tutor/config.py -> project root risalendo di 3 livelli
    return Path(__file__).resolve().parents[2]


def find_stockfish_path() -> str:
    env_path = os.environ.get("STOCKFISH_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    engines_dir = _project_root() / "engines"
    candidate = engines_dir / (
        "stockfish.exe" if platform.system() == "Windows" else "stockfish"
    )
    if candidate.exists():
        return str(candidate)

    which_result = shutil.which("stockfish")
    if which_result:
        return which_result

    raise FileNotFoundError(
        "Stockfish non trovato.\n"
        "Esegui lo script di installazione (install.sh su macOS/Linux, "
        "install.ps1 su Windows) oppure imposta la variabile d'ambiente "
        "STOCKFISH_PATH con il percorso completo dell'eseguibile."
    )
