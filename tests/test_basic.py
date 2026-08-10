import chess


def test_initial_board_has_32_pieces():
    board = chess.Board()
    assert len(board.piece_map()) == 32


def test_legal_moves_from_start():
    board = chess.Board()
    assert board.legal_moves.count() == 20
