"""Interfaccia grafica del Chess Tutor.

- Scacchiera disegnata con Canvas Tkinter + simboli Unicode dei pezzi
  (nessuna dipendenza grafica esterna).
- Click-to-move: primo click seleziona il pezzo ed evidenzia le mosse
  legali, secondo click esegue la mossa se valida.
- Difficoltà dell'avversario regolabile con uno slider (Skill Level 0-20).
- Pannello tutor: dopo ogni mossa del giocatore mostra la valutazione
  della posizione e, se la mossa non era la migliore, la mossa che
  Stockfish avrebbe consigliato al suo posto.
"""

import tkinter as tk
from tkinter import messagebox
import threading

import chess

from .engine_manager import EngineManager

PIECE_UNICODE = {
    "P": "\u2659", "N": "\u2658", "B": "\u2657", "R": "\u2656", "Q": "\u2655", "K": "\u2654",
    "p": "\u265F", "n": "\u265E", "b": "\u265D", "r": "\u265C", "q": "\u265B", "k": "\u265A",
}

SQUARE_SIZE = 64
BOARD_PIXELS = SQUARE_SIZE * 8
LIGHT_COLOR = "#eeeed2"
DARK_COLOR = "#769656"
SELECT_COLOR = "#f6f669"
MOVE_HINT_COLOR = "#8ab4f8"


class ChessTutorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chess Tutor - locale, offline")
        self.resizable(False, False)

        self.board = chess.Board()
        self.selected_square = None
        self.player_is_white = True

        self.engine = EngineManager(think_time=0.4)
        self.engine.set_difficulty(5)  # difficoltà iniziale bassa/media

        self._build_layout()
        self._draw_board()

    # ---------- UI ----------

    def _build_layout(self):
        container = tk.Frame(self)
        container.pack(padx=10, pady=10)

        self.canvas = tk.Canvas(container, width=BOARD_PIXELS, height=BOARD_PIXELS)
        self.canvas.grid(row=0, column=0, rowspan=6)
        self.canvas.bind("<Button-1>", self._on_square_click)

        side = tk.Frame(container)
        side.grid(row=0, column=1, sticky="n", padx=15)

        tk.Label(side, text="Difficolta' avversario (0-20)").pack(anchor="w")
        self.difficulty_var = tk.IntVar(value=5)
        tk.Scale(
            side, from_=0, to=20, orient=tk.HORIZONTAL, variable=self.difficulty_var,
            command=self._on_difficulty_change, length=200,
        ).pack(anchor="w", pady=(0, 10))

        tk.Button(side, text="Nuova partita", command=self._new_game).pack(fill="x", pady=2)
        tk.Button(side, text="Suggerisci mossa (hint)", command=self._show_hint).pack(fill="x", pady=2)
        tk.Button(side, text="Annulla ultima mossa", command=self._undo_move).pack(fill="x", pady=2)

        tk.Label(side, text="Valutazione posizione:").pack(anchor="w", pady=(15, 0))
        self.eval_label = tk.Label(side, text="0.00", font=("TkDefaultFont", 14, "bold"))
        self.eval_label.pack(anchor="w")

        tk.Label(side, text="Consiglio del tutor:").pack(anchor="w", pady=(15, 0))
        self.tutor_text = tk.Text(side, width=28, height=10, wrap="word")
        self.tutor_text.pack(anchor="w")
        self.tutor_text.configure(state="disabled")

    # ---------- Disegno scacchiera ----------

    def _draw_board(self):
        self.canvas.delete("all")
        legal_targets = set()
        if self.selected_square is not None:
            legal_targets = {
                m.to_square for m in self.board.legal_moves
                if m.from_square == self.selected_square
            }

        for rank in range(8):
            for file in range(8):
                square = chess.square(file, 7 - rank)
                x0, y0 = file * SQUARE_SIZE, rank * SQUARE_SIZE
                x1, y1 = x0 + SQUARE_SIZE, y0 + SQUARE_SIZE

                color = LIGHT_COLOR if (file + rank) % 2 == 0 else DARK_COLOR
                if square == self.selected_square:
                    color = SELECT_COLOR
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

                if square in legal_targets:
                    cx, cy = x0 + SQUARE_SIZE / 2, y0 + SQUARE_SIZE / 2
                    self.canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill=MOVE_HINT_COLOR, outline="")

                piece = self.board.piece_at(square)
                if piece:
                    symbol = PIECE_UNICODE[piece.symbol()]
                    self.canvas.create_text(
                        x0 + SQUARE_SIZE / 2, y0 + SQUARE_SIZE / 2,
                        text=symbol, font=("TkDefaultFont", 36),
                    )

    # ---------- Interazione ----------

    def _on_square_click(self, event):
        if self.board.is_game_over():
            return
        file = event.x // SQUARE_SIZE
        rank = 7 - (event.y // SQUARE_SIZE)
        if not (0 <= file < 8 and 0 <= rank < 8):
            return
        square = chess.square(file, rank)

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                self.selected_square = square
                self._draw_board()
            return

        move = chess.Move(self.selected_square, square)
        if move not in self.board.legal_moves:
            # prova con promozione a donna se serve
            promo_move = chess.Move(self.selected_square, square, promotion=chess.QUEEN)
            move = promo_move if promo_move in self.board.legal_moves else None

        self.selected_square = None
        if move is None:
            self._draw_board()
            return

        self._play_player_move(move)

    def _play_player_move(self, move: chess.Move):
        self.board.push(move)
        self._draw_board()
        self._update_tutor_panel()
        self._check_game_over()
        if not self.board.is_game_over():
            self.after(200, self._trigger_engine_move)

    def _trigger_engine_move(self):
        threading.Thread(target=self._engine_move_worker, daemon=True).start()

    def _engine_move_worker(self):
        move = self.engine.get_opponent_move(self.board)
        self.after(0, lambda: self._apply_engine_move(move))

    def _apply_engine_move(self, move: chess.Move):
        if move in self.board.legal_moves:
            self.board.push(move)
        self._draw_board()
        self._update_tutor_panel()
        self._check_game_over()

    # ---------- Tutor ----------

    def _update_tutor_panel(self):
        result = self.engine.evaluate(self.board)
        if result.mate_in is not None:
            eval_text = f"Matto in {abs(result.mate_in)}"
        elif result.score_cp is not None:
            eval_text = f"{result.score_cp / 100:+.2f}"
        else:
            eval_text = "?"
        self.eval_label.configure(text=eval_text)

        advice_lines = []
        if result.best_move is not None:
            advice_lines.append(f"Mossa migliore ora: {self.board.san(result.best_move)}")
        if not self.board.turn == (chess.WHITE if self.player_is_white else chess.BLACK):
            advice_lines.append("(valutazione dopo la mossa del motore)")

        self._set_tutor_text("\n".join(advice_lines))

    def _show_hint(self):
        result = self.engine.evaluate(self.board)
        if result.best_move is not None:
            self._set_tutor_text(f"Suggerimento: gioca {self.board.san(result.best_move)}")

    def _set_tutor_text(self, text: str):
        self.tutor_text.configure(state="normal")
        self.tutor_text.delete("1.0", tk.END)
        self.tutor_text.insert(tk.END, text)
        self.tutor_text.configure(state="disabled")

    # ---------- Controlli generali ----------

    def _on_difficulty_change(self, value):
        self.engine.set_difficulty(int(value))

    def _new_game(self):
        self.board.reset()
        self.selected_square = None
        self._draw_board()
        self._set_tutor_text("Nuova partita iniziata.")
        self.eval_label.configure(text="0.00")

    def _undo_move(self):
        if len(self.board.move_stack) >= 2:
            self.board.pop()
            self.board.pop()
        elif len(self.board.move_stack) == 1:
            self.board.pop()
        self.selected_square = None
        self._draw_board()
        self._update_tutor_panel()

    def _check_game_over(self):
        if self.board.is_game_over():
            messagebox.showinfo("Partita finita", f"Risultato: {self.board.result()}")

    def destroy(self):
        try:
            self.engine.close()
        finally:
            super().destroy()
