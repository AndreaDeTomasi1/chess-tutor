import tkinter as tk


class HomeScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text="Chess Tutor", font=("Helvetica", 28, "bold")).pack(pady=(60, 40))
        tk.Label(self, text="Scegli una modalità", font=("Helvetica", 14)).pack(pady=(0, 20))

        style = {"font": ("Helvetica", 14), "width": 24, "height": 2}
        tk.Button(self, text="Gioca contro il motore", command=lambda: self.app.show_screen("game", mode="engine"), **style).pack(pady=8)
        tk.Button(self, text="Gioca da solo", command=lambda: self.app.show_screen("game", mode="solo"), **style).pack(pady=8)
        tk.Button(self, text="Puzzle", command=lambda: self.app.show_screen("puzzle"), **style).pack(pady=8)