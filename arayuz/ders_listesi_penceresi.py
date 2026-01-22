# arayuz/ders_listesi_penceresi.py
import tkinter as tk
from tkinter import ttk
from veri_deposu import dersler_ogrsay_ve_alanlar_detayli, derse_kayitli_ogrenciler

class DersListesiPenceresi(ttk.Frame):
    """
    - Solda ders listesi (kod + ad)
    - Sağda seçilen dersi alan öğrenciler (No – Ad Soyad) tablo halinde
    """
    def __init__(self, master, koordinator):
        super().__init__(master, padding=10)
        self.k = koordinator
        self._dersler = []
        self._build()

    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Başlık
        ttk.Label(self, text="Ders Listesi", font=("", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")

        # ----- Sol: Dersler -----
        left = ttk.Frame(self)
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 8))
        left.rowconfigure(1, weight=1)

        ttk.Label(left, text="Dersler", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.lst = tk.Listbox(left, height=22, width=36)
        self.lst.grid(row=1, column=0, sticky="nsw")
        self.lst.bind("<<ListboxSelect>>", self._ders_secildi)

        # ----- Sağ: Öğrenciler (tablo) -----
        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(right, text="Dersi Alan Öğrenciler", font=("", 11, "bold")).grid(row=0, column=0, sticky="w")

        self.tree = ttk.Treeview(
            right,
            columns=("no", "adsoyad"),
            show="headings",
            height=20
        )
        self.tree.heading("no", text="Öğr. No")
        self.tree.heading("adsoyad", text="Ad Soyad")
        self.tree.column("no", width=120, anchor="w")
        self.tree.column("adsoyad", width=320, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew")

        sb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=1, sticky="ns")

        self._dersleri_yukle()

    # ----- Veri yükleme -----
    def _dersleri_yukle(self):
        self._dersler = dersler_ogrsay_ve_alanlar_detayli(self.k["bolum_id"])
        self.lst.delete(0, "end")
        for d in self._dersler:
            self.lst.insert("end", f"{d['kod']} – {d['ad']} ({d['ogr_say']})")

    # ----- Etkileşim -----
    def _ders_secildi(self, *_):
        sel = self.lst.curselection()
        if not sel:
            return
        ders = self._dersler[sel[0]]
        ogrenciler = derse_kayitli_ogrenciler(ders["id"])

        for i in self.tree.get_children():
            self.tree.delete(i)

        for o in ogrenciler:
            self.tree.insert("", "end", values=(o["ogr_no"], o["adsoyad"]))
