import tkinter as tk


class PuzzleScreen(tk.Frame):
    """Placeholder in attesa dell'implementazione dei puzzle."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app

        tk.Label(self, text="Puzzle — in arrivo!", font=("Helvetica", 20)).pack(pady=40)
        tk.Button(self, text="← Torna alla home",
                  command=lambda: self.app.show_screen("home")).pack()