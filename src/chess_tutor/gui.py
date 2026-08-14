"""Interfaccia grafica del Chess Tutor.

- Scacchiera disegnata con Canvas Tkinter + pezzi caricati da immagini
  PNG statiche (set "cburnett", licenza CC-BY-SA 3.0 - Colin M.L.
  Burnett), pre-renderizzate ad alta risoluzione e incluse in
  assets/pieces/. Nessuna libreria di sistema richiesta: solo Pillow
  per ridimensionarle.
- Layout a tre colonne: a sinistra l'elenco delle mosse giocate (con
  valutazione in centipawn), al centro la scacchiera (resta centrata
  nello spazio disponibile anche ridimensionando la finestra), a
  destra i controlli (colore, modalita', difficolta', nuova partita,
  pannello tutor).
- Finestra ridimensionabile: trascinando il bordo la scacchiera e i
  pezzi si riscalano automaticamente (con un piccolo debounce per non
  ri-ridimensionare le immagini ad ogni pixel durante il trascinamento).
- Click-to-move: primo click seleziona il pezzo ed evidenzia le mosse
  legali (pallino per mosse "quiete", anello rosso per le catture),
  secondo click esegue la mossa se valida.
- Colore del giocatore selezionabile (Bianco/Nero): la scacchiera si
  orienta di conseguenza e, se il giocatore e' Nero, il motore apre
  la partita.
- Modalita' selezionabile: "Contro motore" (il motore risponde ad ogni
  mossa) oppure "Solo (studio)" per muovere entrambi i lati liberamente
  senza risposta automatica del motore.
- L'ultima mossa giocata (da chiunque) resta evidenziata sulla
  scacchiera.
- Difficolta' dell'avversario regolabile con uno slider (Skill Level 0-20),
  disabilitato in modalita' solo.
- Pannello tutor: la valutazione della posizione e' sempre visibile.
  La mossa migliore puo' essere rivelata a richiesta (pulsante) oppure
  mostrata automaticamente, sia come testo sia come freccia sulla
  scacchiera, attivando l'apposita casella di spunta.

Dipendenza aggiuntiva rispetto alla versione originale:
    poetry add pillow
(serve solo per ridimensionare i PNG dei pezzi alla dimensione corrente
della scacchiera; nessuna libreria nativa esterna necessaria)
"""

import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

import chess
from PIL import Image, ImageTk

from .engine_manager import EngineManager

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


def _asset_filename(piece: chess.Piece) -> str:
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
            path = self._assets_dir / _asset_filename(piece)
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


class ChessTutorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chess Tutor - locale, offline")
        self.resizable(True, True)
        self.minsize(
            LEFT_PANEL_WIDTH + RIGHT_PANEL_WIDTH + MIN_SQUARE_SIZE * 8 + 60,
            MIN_SQUARE_SIZE * 8 + 40,
        )

        self.board = chess.Board()
        self.selected_square = None

        # Stato di partita configurabile dai controlli a destra.
        self.player_is_white = True
        self.solo_mode = False
        self.board_flipped = False  # True quando il giocatore e' Nero
        self.last_move = None
        self._current_best_move = None
        self._current_eval_result = None

        self.square_size = DEFAULT_SQUARE_SIZE
        self.piece_cache = PieceImageCache(ASSETS_DIR)
        self._resize_after_id = None
        self._board_offset = (0, 0)

        self.engine = EngineManager(think_time=0.4)
        self.engine.set_difficulty(5)  # difficolta' iniziale bassa/media

        # self._start_layout()
        self._build_layout()
        self.update_idletasks()  # forza il calcolo della geometria reale del canvas
        self._draw_board()
        self._draw_captured_pieces()
        self._update_tutor_panel(None)

    # ---------- UI ----------

    def _start_layout(self):
        container = tk.Frame(self)

    def _build_layout(self):
        container = tk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=0)  # elenco mosse: larghezza fissa
        container.columnconfigure(1, weight=1)  # scacchiera: si espande e resta centrata
        container.columnconfigure(2, weight=0)  # controlli: larghezza fissa

        self._build_moves_panel(container)
        self._build_board_canvas(container)
        self._build_controls_panel(container)

    def _build_moves_panel(self, container):
        left = tk.Frame(container, width=LEFT_PANEL_WIDTH)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left.grid_propagate(False)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        tk.Label(left, text="Mosse giocate", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )

        list_frame = tk.Frame(left)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        self.moves_listbox = tk.Listbox(
            list_frame, font=("TkFixedFont", 10), yscrollcommand=scrollbar.set,
            activestyle="none", selectmode="browse",
        )
        scrollbar.config(command=self.moves_listbox.yview)
        self.moves_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _build_board_canvas(self, container):
        board_area = tk.Frame(container)
        board_area.grid(row=0, column=1, sticky="nsew")
        board_area.columnconfigure(0, weight=1)

        # riga 0: catturati dal Nero (pezzi bianchi persi) -> sopra
        # riga 1: la scacchiera -> si prende tutto lo spazio extra
        # riga 2: catturati dal Bianco (pezzi neri persi) -> sotto
        board_area.rowconfigure(0, weight=0)
        board_area.rowconfigure(1, weight=1)
        board_area.rowconfigure(2, weight=0)

        self.canvas_captured_black = tk.Canvas(
            board_area,
            height=CAPTURED_PIECE_SIZE + CAPTURED_PADDING * 2,
            highlightthickness=0,
        )
        self.canvas_captured_black.grid(row=0, column=0, sticky="ew")

        self.canvas = tk.Canvas(
            board_area,
            width=self.square_size * 8,
            height=self.square_size * 8,
            highlightthickness=0,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_square_click)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.canvas_captured_white = tk.Canvas(
            board_area,
            height=CAPTURED_PIECE_SIZE + CAPTURED_PADDING * 2,
            highlightthickness=0,
        )
        self.canvas_captured_white.grid(row=2, column=0, sticky="ew")

    def _draw_captured_pieces(self):
        captured = get_captured_pieces(self.board)
        self._captured_images = []

        # canvas_captured_black = fisicamente in alto (row 0)
        # canvas_captured_white = fisicamente in basso (row 2)
        # A seconda del flip, decidiamo quale canvas fisico sta "vicino al Nero"
        # e quale "vicino al Bianco".
        if self.board_flipped:
            # Nero gioca da sotto -> "vicino al Nero" = canvas in basso
            canvas_near_black = self.canvas_captured_white
            canvas_near_white = self.canvas_captured_black
        else:
            # Bianco gioca da sotto -> "vicino al Nero" = canvas in alto
            canvas_near_black = self.canvas_captured_black
            canvas_near_white = self.canvas_captured_white

        # vicino al Nero -> pezzi BIANCHI catturati
        # vicino al Bianco -> pezzi NERI catturati
        for canvas, color in (
            (canvas_near_black, chess.WHITE),
            (canvas_near_white, chess.BLACK),
        ):
            canvas.delete("all")
            x = CAPTURED_PADDING
            order = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]
            pieces_sorted = sorted(
                captured[color], key=lambda p: order.index(p.piece_type)
            )
            for piece in pieces_sorted:
                photo = self.piece_cache.get(piece, CAPTURED_PIECE_SIZE)
                self._captured_images.append(photo)
                canvas.create_image(
                    x + CAPTURED_PIECE_SIZE // 2,
                    CAPTURED_PADDING + CAPTURED_PIECE_SIZE // 2,
                    image=photo,
                )
                x += CAPTURED_PIECE_SIZE

    def _build_controls_panel(self, container):
        side = tk.Frame(container, width=RIGHT_PANEL_WIDTH)
        side.grid(row=0, column=2, sticky="n", padx=(10, 0))
        side.grid_propagate(False)

        # --- Colore del giocatore ---
        tk.Label(side, text="Colore giocatore", font=("TkDefaultFont", 9, "bold")).pack(
            anchor="w", pady=(0, 2)
        )
        self.color_var = tk.StringVar(value="white")
        color_frame = tk.Frame(side)
        color_frame.pack(anchor="w", pady=(0, 6))
        tk.Radiobutton(color_frame, text="Bianco", variable=self.color_var, value="white").pack(
            side="left"
        )
        tk.Radiobutton(color_frame, text="Nero", variable=self.color_var, value="black").pack(
            side="left"
        )

        # --- Modalita' ---
        tk.Label(side, text="Modalita'", font=("TkDefaultFont", 9, "bold")).pack(
            anchor="w", pady=(0, 2)
        )
        self.mode_var = tk.StringVar(value="engine")
        mode_frame = tk.Frame(side)
        mode_frame.pack(anchor="w", pady=(0, 2))
        tk.Radiobutton(
            mode_frame, text="Contro motore", variable=self.mode_var, value="engine"
        ).pack(anchor="w")
        tk.Radiobutton(
            mode_frame, text="Solo (studio)", variable=self.mode_var, value="solo"
        ).pack(anchor="w")
        tk.Label(
            side, text="(si applica premendo 'Nuova partita')",
            font=("TkDefaultFont", 8), fg="gray",
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(side, text="Difficolta' avversario (0-20)").pack(anchor="w")
        self.difficulty_var = tk.IntVar(value=5)
        self.difficulty_scale = tk.Scale(
            side, from_=0, to=20, orient=tk.HORIZONTAL, variable=self.difficulty_var,
            command=self._on_difficulty_change, length=200,
        )
        self.difficulty_scale.pack(anchor="w", pady=(0, 10))

        tk.Button(side, text="Nuova partita", command=self._new_game).pack(fill="x", pady=2)
        tk.Button(side, text="Annulla ultima mossa", command=self._undo_move).pack(fill="x", pady=2)

        tk.Label(side, text="Valutazione posizione:").pack(anchor="w", pady=(15, 0))
        self.eval_label = tk.Label(side, text="0.00", font=("TkDefaultFont", 14, "bold"))
        self.eval_label.pack(anchor="w")

        self.show_best_move_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            side, text="Mostra mossa migliore (testo + freccia)",
            variable=self.show_best_move_var, command=self._on_show_best_move_toggle,
            wraplength=RIGHT_PANEL_WIDTH - 20, justify="left",
        ).pack(anchor="w", pady=(10, 0))

        tk.Label(side, text="Consiglio del tutor:").pack(anchor="w", pady=(10, 0))
        self.tutor_text = tk.Text(side, width=28, height=8, wrap="word")
        self.tutor_text.pack(anchor="w")
        self.tutor_text.configure(state="disabled")

        self.reveal_button = tk.Button(
            side, text="Mostra mossa consigliata (una volta)", command=self._reveal_advice
        )
        self.reveal_button.pack(fill="x", pady=(6, 2))

    # ---------- Resize ----------

    def _on_canvas_resize(self, event):
        new_size = max(MIN_SQUARE_SIZE, min(event.width, event.height) // 8)
        if new_size == self.square_size:
            # la dimensione dei pezzi non cambia, ma la finestra si e'
            # comunque allungata/accorciata in un solo asse: ridisegniamo
            # comunque per ricentrare la scacchiera nel nuovo spazio.
            self._schedule_redraw()
            return
        self.square_size = new_size
        self._schedule_redraw()

    def _schedule_redraw(self):
        # Debounce: durante il trascinamento continuo del bordo arrivano
        # decine di eventi <Configure>; ridisegniamo solo quando l'utente
        # si ferma un attimo, per restare fluidi.
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(RESIZE_DEBOUNCE_MS, self._draw_board)

    # ---------- Orientamento scacchiera (Bianco/Nero in basso) ----------

    def _screen_to_square(self, col: int, row: int) -> chess.Square:
        """Converte coordinate schermo (colonna/riga, 0-7 dall'angolo in
        alto a sinistra del canvas) in una casella, tenendo conto
        dell'eventuale flip (giocatore Nero -> Nero in basso)."""
        if self.board_flipped:
            file_idx = 7 - col
            rank_idx = row
        else:
            file_idx = col
            rank_idx = 7 - row
        return chess.square(file_idx, rank_idx)

    def _square_top_left(self, square: chess.Square):
        """Coordinate (x0, y0) sul canvas dell'angolo in alto a sinistra
        della casella, tenendo conto del flip e dell'offset di centratura."""
        f = chess.square_file(square)
        r = chess.square_rank(square)
        if self.board_flipped:
            col = 7 - f
            row = r
        else:
            col = f
            row = 7 - r
        offset_x, offset_y = self._board_offset
        size = self.square_size
        return offset_x + col * size, offset_y + row * size

    def _square_center(self, square: chess.Square):
        x0, y0 = self._square_top_left(square)
        size = self.square_size
        return x0 + size / 2, y0 + size / 2

    # ---------- Disegno scacchiera ----------

    def _draw_board(self):
        self._resize_after_id = None
        self.canvas.delete("all")
        size = self.square_size

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        board_px = size * 8
        offset_x = max(0, (canvas_w - board_px) // 2)
        offset_y = max(0, (canvas_h - board_px) // 2)
        self._board_offset = (offset_x, offset_y)

        legal_quiet_targets = set()
        legal_capture_targets = set()
        if self.selected_square is not None:
            for m in self.board.legal_moves:
                if m.from_square == self.selected_square:
                    if self.board.is_capture(m):
                        legal_capture_targets.add(m.to_square)
                    else:
                        legal_quiet_targets.add(m.to_square)

        last_move_squares = set()
        if self.last_move is not None:
            last_move_squares = {self.last_move.from_square, self.last_move.to_square}

        # Teniamo un riferimento alle immagini disegnate: Tkinter non
        # mantiene un ref proprio e le garbage-collecterebbe subito.
        self._piece_images_on_canvas = []

        for col in range(8):
            for row in range(8):
                square = self._screen_to_square(col, row)
                f = chess.square_file(square)
                r = chess.square_rank(square)
                x0, y0 = offset_x + col * size, offset_y + row * size
                x1, y1 = x0 + size, y0 + size

                is_light = (f + r) % 2 != 0

                if square in last_move_squares:
                    fill_color = LAST_MOVE_LIGHT if is_light else LAST_MOVE_DARK
                else:
                    fill_color = LIGHT_COLOR if is_light else DARK_COLOR
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill_color, outline="")

                if square == self.selected_square:
                    self.canvas.create_rectangle(x0, y0, x1, y1, fill=SELECT_COLOR, outline="")

                if square in legal_quiet_targets:
                    # Mossa "quieta": pallino centrale.
                    cx, cy = x0 + size / 2, y0 + size / 2
                    rad = max(4, size // 8)
                    self.canvas.create_oval(
                        cx - rad, cy - rad, cx + rad, cy + rad,
                        fill=MOVE_HINT_COLOR, outline="",
                    )
                elif square in legal_capture_targets:
                    # Mossa di cattura: anello rosso che segue il bordo
                    # della casella, per distinguerla visivamente.
                    cx, cy = x0 + size / 2, y0 + size / 2
                    rad = size / 2 - 4
                    self.canvas.create_oval(
                        cx - rad, cy - rad, cx + rad, cy + rad,
                        outline=CAPTURE_HINT_COLOR, width=max(3, size // 14),
                    )

                piece = self.board.piece_at(square)
                if piece:
                    photo = self.piece_cache.get(piece, size)
                    self._piece_images_on_canvas.append(photo)
                    self.canvas.create_image(x0 + size / 2, y0 + size / 2, image=photo)

        if self.show_best_move_var.get() and self._current_best_move is not None:
            self._draw_best_move_arrow(self._current_best_move)

    def _draw_best_move_arrow(self, move: chess.Move):
        x0, y0 = self._square_center(move.from_square)
        x1, y1 = self._square_center(move.to_square)
        width = max(4, self.square_size // 8)
        self.canvas.create_line(
            x0, y0, x1, y1,
            fill=BEST_MOVE_COLOR, width=width,
            arrow=tk.LAST, arrowshape=(width * 3, width * 4, width * 1.4),
            capstyle=tk.ROUND, joinstyle=tk.ROUND,
        )

    # ---------- Interazione ----------

    def _on_square_click(self, event):
        if self.board.is_game_over():
            return
        size = self.square_size
        offset_x, offset_y = self._board_offset
        rel_x = event.x - offset_x
        rel_y = event.y - offset_y
        if rel_x < 0 or rel_y < 0:
            return
        col = int(rel_x // size)
        row = int(rel_y // size)
        if not (0 <= col < 8 and 0 <= row < 8):
            return
        square = self._screen_to_square(col, row)

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
        san = self.board.san(move)  # va calcolato PRIMA di board.push()
        self.board.push(move)
        self.last_move = move
        self._draw_board()
        self._draw_captured_pieces()

        result = self.engine.evaluate(self.board)
        self._record_move(san, result)
        self._update_tutor_panel(result)

        self._check_game_over()
        if not self.solo_mode and not self.board.is_game_over():
            self.after(200, self._trigger_engine_move)

    def _trigger_engine_move(self):
        threading.Thread(target=self._engine_move_worker, daemon=True).start()

    def _engine_move_worker(self):
        move = self.engine.get_opponent_move(self.board)
        self.after(0, lambda: self._apply_engine_move(move))

    def _apply_engine_move(self, move: chess.Move):
        san = None
        if move in self.board.legal_moves:
            san = self.board.san(move)  # prima di push, come sopra
            self.board.push(move)
            self.last_move = move
        self._draw_board()
        self._draw_captured_pieces()

        result = self.engine.evaluate(self.board)
        if san is not None:
            self._record_move(san, result)
        self._update_tutor_panel(result)

        self._check_game_over()

    # ---------- Elenco mosse ----------

    def _record_move(self, san: str, eval_result):
        ply = len(self.board.move_stack)  # dopo il push
        move_number = (ply + 1) // 2
        prefix = f"{move_number}." if ply % 2 == 1 else f"{move_number}..."
        eval_text = self._format_eval(eval_result)
        self.moves_listbox.insert(tk.END, f"{prefix} {san:<8} {eval_text}")
        self.moves_listbox.see(tk.END)

    def _clear_move_list(self):
        self.moves_listbox.delete(0, tk.END)

    # ---------- Tutor ----------

    @staticmethod
    def _format_eval(eval_result) -> str:
        if eval_result is None:
            return "0.00"
        if eval_result.mate_in is not None:
            return f"M{abs(eval_result.mate_in)}"
        if eval_result.score_cp is not None:
            return f"{eval_result.score_cp / 100:+.2f}"
        return "?"

    def _update_tutor_panel(self, eval_result):
        # La valutazione numerica resta sempre visibile. La mossa
        # migliore (testo + freccia) viene mostrata automaticamente solo
        # se la casella "Mostra mossa migliore" e' attiva; altrimenti
        # resta nascosta finche' non si preme il pulsante di rivelazione.
        self._current_eval_result = eval_result
        self.eval_label.configure(text=self._format_eval(eval_result))

        if self.show_best_move_var.get() and eval_result is not None and eval_result.best_move is not None:
            self._current_best_move = eval_result.best_move
            self._set_tutor_text(f"Mossa consigliata: {self.board.san(eval_result.best_move)}")
        else:
            self._current_best_move = None
            self._set_tutor_text(
                "Mossa consigliata nascosta.\n"
                "Premi 'Mostra mossa consigliata' oppure attiva la casella qui sopra."
            )
        self._draw_board()

    def _on_show_best_move_toggle(self):
        # Riapplica lo stato corrente (senza richiedere una nuova
        # valutazione al motore) cosi' la scelta ha effetto immediato.
        self._update_tutor_panel(self._current_eval_result)

    def _reveal_advice(self):
        # Rivelazione "una tantum": mostra la mossa migliore (testo +
        # freccia) per la posizione attuale, indipendentemente dallo
        # stato della casella di spunta.
        if self.board.is_game_over():
            self._set_tutor_text("Partita finita: nessuna mossa disponibile.")
            return
        result = self.engine.evaluate(self.board)
        self._current_best_move = result.best_move
        if result.best_move is not None:
            self._set_tutor_text(f"Mossa consigliata: {self.board.san(result.best_move)}")
        else:
            self._set_tutor_text("Nessuna mossa disponibile.")
        self._draw_board()

    def _set_tutor_text(self, text: str):
        self.tutor_text.configure(state="normal")
        self.tutor_text.delete("1.0", tk.END)
        self.tutor_text.insert(tk.END, text)
        self.tutor_text.configure(state="disabled")

    # ---------- Controlli generali ----------

    def _on_difficulty_change(self, value):
        self.engine.set_difficulty(int(value))

    def _new_game(self):
        # Applica le scelte correnti di colore/modalita' dai controlli.
        self.player_is_white = (self.color_var.get() == "white")
        self.solo_mode = (self.mode_var.get() == "solo")
        self.board_flipped = not self.player_is_white
        self.difficulty_scale.configure(state="disabled" if self.solo_mode else "normal")

        self.board.reset()
        self.selected_square = None
        self.last_move = None
        self._current_best_move = None
        self._clear_move_list()
        self._draw_captured_pieces()
        self._draw_board()
        self._update_tutor_panel(None)

        # Se il giocatore ha scelto il Nero e non siamo in modalita' solo,
        # il motore (che gioca il Bianco) deve aprire la partita.
        if not self.solo_mode and not self.player_is_white and not self.board.is_game_over():
            self.after(200, self._trigger_engine_move)

    def _undo_move(self):
        if not self.board.move_stack:
            return
        # In modalita' solo non c'e' una mossa del motore da annullare
        # insieme a quella del giocatore: si torna indietro di un ply.
        # Contro il motore si annullano invece coppia giocatore+motore.
        pops_wanted = 1 if self.solo_mode else 2
        pops = 0
        for _ in range(pops_wanted):
            if self.board.move_stack:
                self.board.pop()
                pops += 1
            else:
                break

        if pops:
            end = self.moves_listbox.size()
            start = max(0, end - pops)
            self.moves_listbox.delete(start, tk.END)

        self.selected_square = None
        self.last_move = self.board.peek() if self.board.move_stack else None
        self._draw_board()

        result = self.engine.evaluate(self.board) if self.board.move_stack else None
        self._update_tutor_panel(result)

    def _check_game_over(self):
        if self.board.is_game_over():
            messagebox.showinfo("Partita finita", f"Risultato: {self.board.result()}")

    def destroy(self):
        try:
            self.engine.close()
        finally:
            super().destroy()