"""Wrapper attorno al motore Stockfish, usato sia come avversario
(con difficoltà regolabile) sia come tutor (valutazione posizione,
suggerimento mossa migliore).
"""

from dataclasses import dataclass
from typing import Optional

import chess
import chess.engine

from .config import find_stockfish_path


@dataclass
class EvalResult:
    score_cp: Optional[int]   # valutazione in centipedoni (positivo = meglio per il Bianco)
    mate_in: Optional[int]    # se non None, matto in N mosse (segno = a favore di chi)
    best_move: Optional[chess.Move]
    pv: list                  # principal variation (lista di mosse consigliate)


class EngineManager:
    def __init__(self, stockfish_path: Optional[str] = None, think_time: float = 0.5):
        self.path = stockfish_path or find_stockfish_path()
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
        self.think_time = think_time
        self._skill_level = 20

    def set_difficulty(self, skill_level: int) -> None:
        """skill_level va da 0 (mosse molto deboli, quasi casuali) a 20
        (piena forza del motore). Usa il parametro UCI 'Skill Level' di Stockfish."""
        skill_level = max(0, min(20, skill_level))
        self._skill_level = skill_level
        self.engine.configure({"Skill Level": skill_level})

    def get_opponent_move(self, board: chess.Board) -> chess.Move:
        """Mossa dell'avversario (motore), rispettando la difficoltà impostata."""
        limit = chess.engine.Limit(time=self.think_time)
        result = self.engine.play(board, limit)
        return result.move

    def evaluate(self, board: chess.Board, depth: int = 15) -> EvalResult:
        """Valutazione 'da tutor': usata a piena forza indipendentemente
        dalla difficoltà dell'avversario, per dare consigli sempre corretti."""
        info = self.engine.analyse(board, chess.engine.Limit(depth=depth))
        score = info["score"].white()
        pv = info.get("pv", [])
        best_move = pv[0] if pv else None
        mate_in = score.mate()
        score_cp = None if mate_in is not None else score.score()
        return EvalResult(score_cp=score_cp, mate_in=mate_in, best_move=best_move, pv=pv)

    def close(self) -> None:
        self.engine.quit()
