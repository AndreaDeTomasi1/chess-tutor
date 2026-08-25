"""
tutor_explainer.py

Genera spiegazioni testuali (in italiano) per il pannello "Spiegazione del tutor",
senza usare nessun LLM: tutto e' rilevamento di pattern tattici via python-chess
+ classificazione della mossa in base alla differenza di valutazione, con testo
prodotto da template.

Uso tipico (vedi anche l'esempio di integrazione in fondo al file):

    explainer = TutorExplainer()
    testo = explainer.explain(
        board_before=board_prima_della_mossa,
        played_move=mossa_del_giocatore,
        best_move=mossa_migliore_secondo_stockfish,
        eval_before_cp=eval_prima_in_centipawn,        # dal punto di vista del bianco
        eval_after_played_cp=eval_dopo_mossa_giocatore,
        eval_after_best_cp=eval_dopo_mossa_migliore,
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import chess

PIECE_NAMES_IT = {
    chess.PAWN: "pedone",
    chess.KNIGHT: "cavallo",
    chess.BISHOP: "alfiere",
    chess.ROOK: "torre",
    chess.QUEEN: "donna",
    chess.KING: "re",
}

# genere grammaticale, per usare l'articolo corretto (il/la)
PIECE_ARTICLE_IT = {
    chess.PAWN: "il",
    chess.KNIGHT: "il",
    chess.BISHOP: "l'",
    chess.ROOK: "la",
    chess.QUEEN: "la",
    chess.KING: "il",
}

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # il re non si "cattura", ma serve per confronti di valore
}


def piece_name_it(piece: chess.Piece) -> str:
    return PIECE_NAMES_IT[piece.piece_type]


def piece_name_with_article_it(piece: chess.Piece) -> str:
    """Es: 'la torre', 'il cavallo', 'l'alfiere'."""
    article = PIECE_ARTICLE_IT[piece.piece_type]
    sep = "" if article.endswith("'") else " "
    return f"{article}{sep}{PIECE_NAMES_IT[piece.piece_type]}"


def square_name(square: chess.Square) -> str:
    return chess.square_name(square)


# ---------------------------------------------------------------------------
# Conversione eval -> "winning chances" (stessa formula usata da Lichess)
# ---------------------------------------------------------------------------

def winning_chances(cp: float) -> float:
    """Converte centipawn (dal punto di vista del bianco) in un valore -1..1.

    Serve per confrontare in modo piu' onesto due eval: una differenza di 300cp
    a +100 e' molto piu' significativa della stessa differenza a +900, perche'
    la probabilita' di vittoria satura.
    """
    return 2 / (1 + math.exp(-0.00368208 * cp)) - 1


def classify_move_quality(eval_before_cp: float | None, eval_after_cp: float | None,
                           side_to_move_was_white: bool) -> str:
    """Classifica la mossa giocata confrontando le winning chances prima/dopo,
    dal punto di vista di chi ha mosso.

    Ritorna una delle stringhe: "ottima", "corretta", "imprecisione",
    "errore", "grave errore".
    """

    if eval_after_cp is None:
        return "ottima"
    if eval_before_cp is None:
        return "corretta"
        
    wc_before = winning_chances(eval_before_cp)
    wc_after = winning_chances(eval_after_cp)

    if not side_to_move_was_white:
        wc_before, wc_after = -wc_before, -wc_after

    delta = wc_before - wc_after  # quanto si e' peggiorata la propria posizione

    if delta >= 0.30:
        return "grave errore"
    if delta >= 0.15:
        return "errore"
    if delta >= 0.06:
        return "imprecisione"
    if delta <= -0.03:
        return "ottima"
    return "corretta"


# ---------------------------------------------------------------------------
# Rilevamento pattern tattici (pura logica su python-chess, nessun motore)
# ---------------------------------------------------------------------------

@dataclass
class Motif:
    kind: str          # "fork" | "pin" | "skewer" | "discovered_attack" | "hanging_piece"
    text: str          # frase gia' pronta in italiano
    priority: int = 0  # per scegliere il motivo piu' "importante" da mostrare


def _attacked_pieces(board: chess.Board, attacker_square: chess.Square,
                      attacker_color: chess.Color) -> list[tuple[chess.Square, chess.Piece]]:
    """Pezzi nemici attaccati dal pezzo su attacker_square, DOPO la mossa."""
    targets = []
    for target_square in board.attacks(attacker_square):
        target_piece = board.piece_at(target_square)
        if target_piece is not None and target_piece.color != attacker_color:
            targets.append((target_square, target_piece))
    return targets


def detect_fork(board_after: chess.Board, move: chess.Move) -> Motif | None:
    """Forchetta: il pezzo appena mosso attacca 2+ pezzi nemici di valore
    pari o superiore al proprio (o comunque pezzi che non puo' permettersi
    di perdere entrambi)."""
    mover_color = not board_after.turn  # dopo la mossa il turno e' gia' passato
    attacker_piece = board_after.piece_at(move.to_square)
    if attacker_piece is None:
        return None

    targets = _attacked_pieces(board_after, move.to_square, mover_color)
    if len(targets) < 2:
        return None

    attacker_value = PIECE_VALUES[attacker_piece.piece_type]
    # consideriamo "vera" forchetta se almeno due bersagli valgono >= attaccante,
    # oppure uno dei due e' il re (scacco + attacco = forchetta comunque forte)
    king_targets = [t for t in targets if t[1].piece_type == chess.KING]
    valuable_targets = [t for t in targets if PIECE_VALUES[t[1].piece_type] >= attacker_value]

    if king_targets or len(valuable_targets) >= 2:
        names = ", ".join(f"{piece_name_it(p)} in {square_name(sq)}" for sq, p in targets)
        return Motif(
            kind="fork",
            text=(f"{piece_name_with_article_it(attacker_piece)} in {square_name(move.to_square)} "
                  f"mette in forchetta piu' pezzi contemporaneamente: {names}."),
            priority=3,
        )
    return None


def detect_pin(board_after: chess.Board, move: chess.Move) -> Motif | None:
    """Pin assoluto o relativo creato/sfruttato dalla mossa (usa is_pinned
    della libreria per il caso assoluto rispetto al re)."""
    mover_color = not board_after.turn
    enemy_color = not mover_color

    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece is not None and piece.color == enemy_color:
            if board_after.is_pinned(enemy_color, square):
                pinned_name = piece_name_with_article_it(piece)
                king_sq = board_after.king(enemy_color)
                return Motif(
                    kind="pin",
                    text=(f"{pinned_name} in {square_name(square)} e' inchiodato "
                          f"al re in {square_name(king_sq)} e non puo' muoversi liberamente."),
                    priority=2,
                )
    return None


def detect_skewer(board_after: chess.Board, move: chess.Move) -> Motif | None:
    """Infilata: un pezzo che scorre (alfiere/torre/donna) attacca un pezzo
    di valore maggiore che, spostandosi, scoprirebbe un pezzo di valore
    minore sulla stessa linea."""
    mover_color = not board_after.turn
    attacker_piece = board_after.piece_at(move.to_square)
    if attacker_piece is None or attacker_piece.piece_type not in (
        chess.BISHOP, chess.ROOK, chess.QUEEN
    ):
        return None

    directions = {
        chess.BISHOP: [(1, 1), (1, -1), (-1, 1), (-1, -1)],
        chess.ROOK: [(1, 0), (-1, 0), (0, 1), (0, -1)],
    }
    directions[chess.QUEEN] = directions[chess.BISHOP] + directions[chess.ROOK]

    from_file, from_rank = chess.square_file(move.to_square), chess.square_rank(move.to_square)

    for df, dr in directions[attacker_piece.piece_type]:
        line_pieces = []
        f, r = from_file + df, from_rank + dr
        while 0 <= f <= 7 and 0 <= r <= 7:
            sq = chess.square(f, r)
            p = board_after.piece_at(sq)
            if p is not None:
                line_pieces.append((sq, p))
                if len(line_pieces) == 2:
                    break
            f, r = f + df, r + dr

        if len(line_pieces) == 2:
            (sq1, p1), (sq2, p2) = line_pieces
            if (p1.color == enemy_color_of(mover_color) and
                    p2.color == enemy_color_of(mover_color) and
                    PIECE_VALUES[p1.piece_type] > PIECE_VALUES[p2.piece_type]):
                return Motif(
                    kind="skewer",
                    text=(f"{piece_name_with_article_it(attacker_piece)} in {square_name(move.to_square)} "
                          f"infila {piece_name_with_article_it(p1)} in {square_name(sq1)}: se si sposta, "
                          f"resta scoperto {piece_name_with_article_it(p2)} in {square_name(sq2)}."),
                    priority=3,
                )
    return None


def enemy_color_of(color: chess.Color) -> chess.Color:
    return not color


def detect_discovered_attack(board_before: chess.Board, board_after: chess.Board,
                              move: chess.Move) -> Motif | None:
    """Attacco di scoperta: confronta gli attacchi PRIMA e DOPO la mossa per
    trovare linee appena rivelate da un pezzo diverso da quello mosso."""
    mover_color = not board_after.turn
    enemy_color = not mover_color

    for square in chess.SQUARES:
        piece = board_before.piece_at(square)
        if piece is None or piece.color != mover_color or square == move.from_square:
            continue
        if piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        # se questo pezzo ora attacca il re o un pezzo di valore che prima
        # non attaccava (perche' il pezzo mosso gli faceva ombra), e' scoperta
        before_targets = {sq for sq in board_before.attacks(square)
                           if board_before.piece_at(sq) and
                           board_before.piece_at(sq).color == enemy_color}
        after_targets = {sq for sq in board_after.attacks(square)
                          if board_after.piece_at(sq) and
                          board_after.piece_at(sq).color == enemy_color}
        new_targets = after_targets - before_targets
        if new_targets:
            king_sq = board_after.king(enemy_color)
            if king_sq in new_targets:
                return Motif(
                    kind="discovered_attack",
                    text=(f"spostando il pezzo in {square_name(move.to_square)} si scopre "
                          f"{piece_name_with_article_it(piece)} in {square_name(square)}, che ora da' "
                          f"scacco al re: attacco di scoperta."),
                    priority=4,
                )
            target_sq = next(iter(new_targets))
            target_piece = board_after.piece_at(target_sq)
            return Motif(
                kind="discovered_attack",
                text=(f"spostando il pezzo in {square_name(move.to_square)} si scopre "
                      f"{piece_name_with_article_it(piece)} in {square_name(square)}, che ora attacca "
                      f"{piece_name_with_article_it(target_piece)} in {square_name(target_sq)}."),
                priority=3,
            )
    return None


def detect_hanging_piece(board_after: chess.Board) -> Motif | None:
    """Pezzo indifeso: cerca il pezzo di maggior valore lasciato attaccabile
    e non difeso, dal punto di vista di chi deve ancora muovere (cioe' la
    vittima potenziale della mossa appena giocata)."""
    victim_color = board_after.turn  # tocca a lui: e' lui il potenziale bersaglio
    attacker_color = not victim_color

    worst = None
    for square in chess.SQUARES:
        piece = board_after.piece_at(square)
        if piece is None or piece.color != victim_color or piece.piece_type == chess.KING:
            continue
        attackers = board_after.attackers(attacker_color, square)
        if not attackers:
            continue
        defenders = board_after.attackers(victim_color, square)
        if defenders:
            continue  # e' difeso, non conta come "appeso"
        value = PIECE_VALUES[piece.piece_type]
        if worst is None or value > worst[1]:
            worst = (square, value, piece)

    if worst is None:
        return None
    square, _, piece = worst
    return Motif(
        kind="hanging_piece",
        text=f"{piece_name_with_article_it(piece)} in {square_name(square)} e' indifeso e puo' essere catturato gratis.",
        priority=2,
    )


def detect_motifs_for_move(board_before: chess.Board, move: chess.Move) -> list[Motif]:
    """Applica la mossa su una copia della board e rileva tutti i motivi
    tattici rilevanti creati da quella mossa."""
    board_after = board_before.copy()
    board_after.push(move)

    motifs = []
    for fn in (detect_fork, detect_pin, detect_skewer):
        m = fn(board_after, move)
        if m:
            motifs.append(m)
    m = detect_discovered_attack(board_before, board_after, move)
    if m:
        motifs.append(m)
    m = detect_hanging_piece(board_after)
    if m:
        motifs.append(m)

    motifs.sort(key=lambda m: -m.priority)
    return motifs


# ---------------------------------------------------------------------------
# Composizione del testo finale mostrato nel pannello "Spiegazione del tutor"
# ---------------------------------------------------------------------------

class TutorExplainer:

    def explain(
        self,
        board_before: chess.Board,
        played_move: chess.Move,
        best_move: chess.Move | None,
        eval_before_cp: float,
        eval_after_played_cp: float,
        eval_after_best_cp: float | None = None,
    ) -> str:
        """Ritorna il testo completo da inserire nel pannello.

        Tutti gli eval sono centipawn dal punto di vista del BIANCO (come li
        da' normalmente python-chess / uci). Se il tuo EngineManager restituisce
        gia' un valore "dal punto di vista di chi muove", convertilo prima di
        chiamare questa funzione (moltiplica per -1 se tocca al nero).
        """
        side_white = board_before.turn == chess.WHITE
        quality = classify_move_quality(eval_before_cp, eval_after_played_cp, side_white)

        played_motifs = detect_motifs_for_move(board_before, played_move)
        san_played = board_before.san(played_move)

        lines = []

        if quality in ("errore", "grave errore"):
            lines.append(f"{san_played} e' {'un grave errore' if quality == 'grave errore' else 'un errore'}.")
        elif quality == "imprecisione":
            lines.append(f"{san_played} e' un'imprecisione.")
        elif quality == "ottima":
            lines.append(f"{san_played} e' un'ottima mossa!")
        else:
            lines.append(f"{san_played} e' una mossa corretta.")

        # Perche' e' un problema: cosa lascia indietro / permette all'avversario
        if quality in ("errore", "grave errore", "imprecisione"):
            if played_motifs:
                lines.append("Il problema: " + played_motifs[0].text)
            else:
                lines.append("Il problema: peggiora sensibilmente la valutazione della posizione, "
                              "probabilmente per motivi posizionali (struttura pedonale, sicurezza "
                              "del re o attivita' dei pezzi) piu' che per una tattica immediata.")

        # Perche' la mossa migliore e' migliore
        if best_move is not None and best_move != played_move:
            best_motifs = detect_motifs_for_move(board_before, best_move)
            san_best = board_before.san(best_move)
            if best_motifs:
                lines.append(f"Mossa consigliata: {san_best}. {best_motifs[0].text}")
            else:
                lines.append(f"Mossa consigliata: {san_best}, che mantiene una posizione migliore.")

            if eval_after_best_cp is not None:
                wc_played = winning_chances(eval_after_played_cp if side_white else -eval_after_played_cp)
                wc_best = winning_chances(eval_after_best_cp if side_white else -eval_after_best_cp)
                diff_pct = round((wc_best - wc_played) * 50)  # scala approssimativa in "punti %"
                if diff_pct > 2:
                    lines.append(f"Differenza stimata: circa {diff_pct} punti percentuali di probabilita' di vittoria in piu'.")

        return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Auto-test rapido (eseguibile con: python tutor_explainer.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Posizione con una forchetta di cavallo pronta: Nc3-d5 forchetta Dc7/Ta8? etc.
    # Esempio semplice: cavallo bianco che salta su un pezzo che forchetta re+torre.
    b = chess.Board("r3k2r/8/8/3N4/8/8/8/4K3 w kq - 0 1")
    mv = chess.Move.from_uci("d5c7")  # Nc7+ forchetta Re8 e Ta8 (in questa posizione)
    print("Motivi rilevati per", b.san(mv), ":")
    for m in detect_motifs_for_move(b, mv):
        print(" -", m.kind, "->", m.text)

    print()
    exp = TutorExplainer()
    print(exp.explain(
        board_before=b,
        played_move=chess.Move.from_uci("e1e2"),  # mossa "debole" a caso
        best_move=mv,
        eval_before_cp=20,
        eval_after_played_cp=10,
        eval_after_best_cp=350,
    ))