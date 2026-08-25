import tkinter as tk

from .chess_utils import LEFT_PANEL_WIDTH, RIGHT_PANEL_WIDTH, MIN_SQUARE_SIZE


class ChessTutorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chess Tutor - locale, offline")
        self.resizable(True, True)
        self.minsize(
            LEFT_PANEL_WIDTH + RIGHT_PANEL_WIDTH + MIN_SQUARE_SIZE * 8 + 60,
            MIN_SQUARE_SIZE * 8 + 40,
        )

        self._container = tk.Frame(self)
        self._container.pack(fill="both", expand=True)
        self._current_screen = None
        self.show_screen("home")

    def show_screen(self, name: str, **kwargs):
        if self._current_screen is not None:
            self._current_screen.destroy()

        screen_cls = self._resolve_screen(name)
        self._current_screen = screen_cls(self._container, app=self, **kwargs)
        self._current_screen.pack(fill="both", expand=True)

    @staticmethod
    def _resolve_screen(name: str):
        from .screens.home_screen import HomeScreen
        from .screens.game_screen import GameScreen
        from .screens.puzzle_screen import PuzzleScreen

        return {"home": HomeScreen, "game": GameScreen, "puzzle": PuzzleScreen}[name]