import tkinter as tk
from tkinter import ttk
import bcrypt
from veri_deposu import kullanici_bul
from utils.mesaj import hata

class GirisPenceresi(tk.Toplevel):
    def __init__(self, master, giris_sonrasi_cb):
        super().__init__(master)
        self.title("Sınav Sistemi - Giriş")
        self.resizable(False, False)
        self.giris_sonrasi_cb = giris_sonrasi_cb

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="E-posta").grid(row=0, column=0, sticky="w")
        self.ent_eposta = ttk.Entry(frm, width=32)
        self.ent_eposta.grid(row=0, column=1, pady=4)

        ttk.Label(frm, text="Şifre").grid(row=1, column=0, sticky="w")
        self.ent_sifre = ttk.Entry(frm, show="*", width=32)
        self.ent_sifre.grid(row=1, column=1, pady=4)

        ttk.Button(frm, text="Giriş Yap", command=self._giris_yap).grid(row=2, column=0, columnspan=2, pady=8, sticky="ew")
        self.bind("<Return>", lambda e: self._giris_yap())

    def _giris_yap(self):
        eposta = self.ent_eposta.get().strip()
        sifre = self.ent_sifre.get().strip().encode()
        kayit = kullanici_bul(eposta)
        if not kayit:
            hata("Kullanıcı bulunamadı.")
            return
        if not bcrypt.checkpw(sifre, kayit["sifre_hash"]):
            hata("Şifre hatalı.")
            return
        self.destroy()
        self.giris_sonrasi_cb(kayit)
