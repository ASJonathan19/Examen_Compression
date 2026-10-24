#!/usr/bin/env python3
"""
gui.py - Interface graphique animée pour compressor.py (Tkinter, module standard).

Lancer :  python gui.py        (compressor.py doit être dans le même dossier)

Animations : fondu à l'ouverture, spinner pendant le calcul, barres qui grandissent
en cascade avec compteur de pourcentage, boutons qui réagissent au survol.
"""
import math
import os
import queue
import threading
import time
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

import compressor as C

# ------------------------------------------------------------------ thème
BG, CARD, TEXT, MUTED = "#1b1c2b", "#272940", "#eef0ff", "#9aa0b5"
ACCENT, ACCENT_HOVER = "#6c8cff", "#8aa3ff"
COLORS = {"Original": "#9aa0b5", "bzip2": "#ff8a65", "lzma": "#4dd0e1", "7z": "#81c784"}
FONT, FONT_B = ("Segoe UI", 10), ("Segoe UI", 10, "bold")


def ease_out(p):
    """Décélération douce (cubic ease-out) : 0 -> 1."""
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


class FancyButton(tk.Button):
    """Bouton plat qui change de couleur au survol."""

    def __init__(self, master, text, command, bg=ACCENT, hover=ACCENT_HOVER):
        super().__init__(master, text=text, command=command, bg=bg, fg="white",
                         activebackground=hover, activeforeground="white",
                         relief="flat", bd=0, padx=16, pady=8, font=FONT_B, cursor="hand2")
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mini 7-zip / bzip2 / lzma — Projet Codage et Traitement du Signal")
        self.geometry("820x640")
        self.minsize(720, 560)
        self.configure(bg=BG)

        self.path = tk.StringVar(value="Aucun fichier sélectionné")
        self.algo = tk.StringVar(value="lzma")
        self.q = queue.Queue()
        self.busy = False
        self.angle = 0
        self.bars = []
        self.t0 = 0.0

        self._build()
        self._fade_in()
        self.after(100, self._poll)

    # -------------------------------------------------------------- interface
    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(header, text="Compresseur", bg=BG, fg=TEXT,
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        self.spinner = tk.Canvas(header, width=36, height=36, bg=BG, highlightthickness=0)
        self.spinner.pack(side="right")

        card = tk.Frame(self, bg=CARD)
        card.pack(fill="x", padx=24, pady=8)
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=16, pady=(14, 6))
        FancyButton(row, "📂  Choisir un fichier", self.choose_file).pack(side="left")
        tk.Label(row, textvariable=self.path, bg=CARD, fg=MUTED, font=FONT,
                 anchor="w").pack(side="left", padx=14, fill="x", expand=True)

        row2 = tk.Frame(card, bg=CARD)
        row2.pack(fill="x", padx=16, pady=(6, 14))
        tk.Label(row2, text="Algorithme :", bg=CARD, fg=TEXT, font=FONT_B).pack(side="left")
        for name in ("bzip2", "lzma", "7z"):
            tk.Radiobutton(row2, text=name, value=name, variable=self.algo, bg=CARD, fg=TEXT,
                           selectcolor=BG, activebackground=CARD, activeforeground=ACCENT,
                           font=FONT, bd=0, highlightthickness=0).pack(side="left", padx=8)

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=24, pady=6)
        FancyButton(actions, "🗜  Compresser", self.on_compress).pack(side="left", padx=(0, 8))
        FancyButton(actions, "📤  Décompresser", self.on_decompress,
                    bg="#4a4d6e", hover="#5d6190").pack(side="left", padx=(0, 8))
        FancyButton(actions, "📊  Comparer les 3", self.on_compare,
                    bg="#e0709a", hover="#ee8cb0").pack(side="left")

        self.chart = tk.Canvas(self, bg=CARD, highlightthickness=0, height=250)
        self.chart.pack(fill="both", expand=True, padx=24, pady=(10, 6))
        self.chart.bind("<Configure>", lambda e: self._draw(1.0))
        self._draw_placeholder()

        self.log = tk.Label(self, text="Prêt.", bg=BG, fg=MUTED, font=FONT, anchor="w",
                            justify="left", wraplength=760)
        self.log.pack(fill="x", padx=24, pady=(0, 14))

    def _fade_in(self, a=0.0):
        try:
            self.attributes("-alpha", a)
            if a < 1.0:
                self.after(20, lambda: self._fade_in(a + 0.08))
        except tk.TclError:
            pass  # plateforme sans transparence

    # -------------------------------------------------------------- actions
    def choose_file(self):
        p = filedialog.askopenfilename(title="Choisir un fichier")
        if p:
            self.path.set(p)
            self._say(f"Fichier : {os.path.basename(p)} ({C.human(os.path.getsize(p))})")

    def _need_file(self):
        p = self.path.get()
        if not os.path.isfile(p):
            messagebox.showinfo("Fichier manquant", "Choisis d'abord un fichier.")
            return None
        return p

    def on_compress(self):
        p = self._need_file()
        if p and not self.busy:
            algo = self.algo.get()
            self._run(lambda: self._job_compress(algo, p))

    def on_decompress(self):
        if self.busy:
            return
        p = filedialog.askopenfilename(title="Fichier à décompresser",
                                       filetypes=[("Archives", "*.bz2 *.lzma *.xz *.7z"),
                                                  ("Tous", "*.*")])
        if p:
            algo = self.algo.get()
            self._run(lambda: self._job_decompress(algo, p))

    def on_compare(self):
        p = self._need_file()
        if p and not self.busy:
            self._run(lambda: self._job_compare(p))

    # -------------------------------------------------------------- travaux (thread)
    def _job_compress(self, algo, p):
        out, t = C.timed(C.compress, algo, p)
        s0, s1 = os.path.getsize(p), os.path.getsize(out)
        msg = f"✔ {os.path.basename(out)} créé en {t:.3f} s"
        return msg, [("Original", s0, 0.0), (algo, s1, t)]

    def _job_decompress(self, algo, p):
        out, t = C.timed(C.decompress, algo, p)
        return f"✔ Décompressé vers {out} en {t:.3f} s", None

    def _job_compare(self, p):
        s0 = os.path.getsize(p)
        bars = [("Original", s0, 0.0)]
        with tempfile.TemporaryDirectory() as tmp:
            for algo in ("bzip2", "lzma", "7z"):
                out = os.path.join(tmp, os.path.basename(p) + C.EXT[algo])
                _, t = C.timed(C.compress, algo, p, out)
                bars.append((algo, os.path.getsize(out), t))
        best = min(bars[1:], key=lambda b: b[1])
        return f"✔ Comparaison terminée — meilleur taux : {best[0]}", bars

    def _run(self, job):
        self.busy = True
        self._say("Calcul en cours…")
        self._spin()

        def worker():
            try:
                self.q.put(("ok", job()))
            except Exception as e:  # noqa: BLE001
                self.q.put(("err", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            kind, payload = self.q.get_nowait()
            self.busy = False
            if kind == "ok":
                msg, bars = payload
                self._say(msg)
                if bars:
                    self.bars, self.t0 = bars, time.perf_counter()
                    self._tick()
            else:
                self._say(f"✘ Erreur : {payload}")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # -------------------------------------------------------------- animations
    def _say(self, text):
        self.log.config(text=text)

    def _spin(self):
        """Spinner : arc qui tourne tant qu'un calcul est en cours."""
        self.spinner.delete("all")
        if self.busy:
            self.angle = (self.angle + 18) % 360
            self.spinner.create_oval(4, 4, 32, 32, outline=CARD, width=4)
            self.spinner.create_arc(4, 4, 32, 32, start=self.angle, extent=100,
                                    style="arc", outline=ACCENT, width=4)
            self.after(30, self._spin)
        else:
            self.spinner.create_text(18, 18, text="✔", fill="#81c784", font=("Segoe UI", 16, "bold"))

    def _tick(self):
        p = (time.perf_counter() - self.t0) / 1.2
        self._draw(p)
        if p < 1:
            self.after(15, self._tick)

    def _draw_placeholder(self):
        self.chart.delete("all")
        self.chart.create_text(self.chart.winfo_reqwidth() // 2 or 400, 110,
                               text="Choisis un fichier puis lance une action…",
                               fill=MUTED, font=("Segoe UI", 12))

    def _draw(self, progress):
        """Dessine les barres. Chaque barre démarre un peu après la précédente (cascade)."""
        if not self.bars:
            return
        c = self.chart
        c.delete("all")
        w, h = max(c.winfo_width(), 400), max(c.winfo_height(), 200)
        left, right = 90, 270
        biggest = max(b[1] for b in self.bars) or 1
        n = len(self.bars)
        slot = (h - 30) / n
        s0 = self.bars[0][1] or 1
        for i, (label, size, t) in enumerate(self.bars):
            e = ease_out((progress * 1.6 - i * 0.25) / 0.9) if progress < 1 else 1.0
            y = 15 + i * slot
            bh = min(34, slot - 12)
            full = (w - left - right) * size / biggest
            c.create_text(left - 12, y + bh / 2, text=label, fill=TEXT,
                          font=FONT_B, anchor="e")
            c.create_rectangle(left, y, w - right, y + bh, fill=BG, outline="")
            c.create_rectangle(left, y, left + full * e, y + bh,
                               fill=COLORS.get(label, ACCENT), outline="")
            if label == "Original":
                info = C.human(size * e)
            else:
                taux = (1 - size / s0) * 100
                info = f"{C.human(size * e)}  ({taux * e:+.1f} %)  {t:.2f}s"
            c.create_text(w - right + 10, y + bh / 2, text=info, fill=TEXT,
                          font=FONT, anchor="w")


if __name__ == "__main__":
    App().mainloop()
