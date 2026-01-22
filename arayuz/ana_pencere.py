# arayuz/ana_pencere.py
import tkinter as tk
from tkinter import ttk
from veri_deposu import kullaniciya_gorunecek_bolumler, derslik_sayisi
from arayuz.derslik_penceresi import DerslikPenceresi
from arayuz.import_penceresi import ImportPenceresi
from arayuz.oturma_plani_penceresi import OturmaPlaniPenceresi
from arayuz.kullanici_yonetimi import KullaniciYonetimi
from arayuz.ogrenci_listesi_penceresi import OgrenciListesiPenceresi
from arayuz.sinav_programi_penceresi import SinavProgramiPenceresi
from arayuz.ders_listesi_penceresi import DersListesiPenceresi  # ✅ dosya adı ve import uyumlu

class AnaPencere(tk.Toplevel):
    """
    Koordinatör:
      - Derslikler
      - Excel Aktar
      - Sınav Programı (Excel’den sonra otomatik eklenir)
      - Oturma Planı
      - Öğrenci Listesi (Excel’den sonra otomatik eklenir)
      - Ders Listesi    (Excel’den sonra otomatik eklenir)

    Admin:
      - Kullanıcı Yönetimi
      - Genel
    """
    def __init__(self, kullanici, master=None):
        super().__init__(master)
        self.title("Dinamik Sınav Takvimi")
        self.geometry("1100x720")
        self.kullanici = kullanici

        # referanslar / sonradan eklemek için
        self._tab_refs = {}   # {'ogrenci_listesi': widget, ...}

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._kapat)

    def _kapat(self):
        if self.master:
            self.master.destroy()
        else:
            self.destroy()

    # ---------------- UI ----------------
    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.nb = nb

        if self.kullanici["rol"] == "koordinator":
            # Derslikler
            frm_derslik = DerslikPenceresi(nb, self.kullanici,
                                           on_derslik_eklendi=self._on_first_derslik_added)
            nb.add(frm_derslik, text="Derslikler")

            # Excel Aktarımları
            frm_import = ImportPenceresi(
                nb,
                self.kullanici,
                on_after_import=self._on_after_import  # ✅ excel sonrası menüleri aç
            )
            nb.add(frm_import, text="Excel Aktar")

            # Oturma Planı (her zaman mevcut)
            frm_oturma = OturmaPlaniPenceresi(nb, self.kullanici)
            nb.add(frm_oturma, text="Oturma Planı")
            self._tab_refs["oturma"] = frm_oturma

            # Derslik yoksa Excel Aktar tabını kilitle (ilk kurulum akışı)
            if derslik_sayisi(self.kullanici) == 0:
                idx = list(nb.tabs()).index(str(frm_import))
                nb.tab(idx, state="disabled")
                self.after(400, lambda: self._bilgilendir_kilit(nb, idx))

            # Eğer zaten veri varsa (yeniden açılışlar), menüleri hazırla
            self.after(100, self._ensure_data_tabs)

        else:
            # Admin
            frm_kul = KullaniciYonetimi(nb, self.kullanici)
            nb.add(frm_kul, text="Kullanıcı Yönetimi")

            frm = ttk.Frame(nb, padding=16)
            nb.add(frm, text="Genel")
            ttk.Label(frm, text="Admin girişi yaptınız.", font=("", 12, "bold")).grid(row=0, column=0, sticky="w")
            gorunen = ", ".join([b["ad"] for b in kullaniciya_gorunecek_bolumler(self.kullanici)])
            ttk.Label(frm, text=f"Görünen bölümler: {gorunen}").grid(row=1, column=0, sticky="w")

    def _bilgilendir_kilit(self, nb, idx):
        title = nb.tab(idx, "text")
        nb.tab(idx, text=f"{title} (Önce derslik girin)")

    # ------------- Dinamik sekmeler -------------
    def _on_first_derslik_added(self):
        """İlk derslik eklendiğinde 'Excel Aktar' sekmesini serbest bırak."""
        # Excel Aktar sekmesini etkinleştir
        for i, tab_id in enumerate(self.nb.tabs()):
            if self.nb.tab(tab_id, "text").startswith("Excel Aktar"):
                self.nb.tab(i, state="normal")
                break

    def _on_after_import(self, tip: str):
        """
        ImportPenceresi'nden gelir.
        tip: 'ders' veya 'ogrenci'
        - Excel yüklemesi biter bitmez gerekli menüleri ekler ve odaklar.
        """
        self._ensure_data_tabs()
        # Kullanıcıyı görünür sekmeye alalım (mantıklı varsayımlar):
        if tip == "ders":
            self._focus_tab("sinav_programi")  # önce program sekmesine götürelim
        else:
            self._focus_tab("ogrenci_listesi")

    def _focus_tab(self, key: str):
        w = self._tab_refs.get(key)
        if not w:
            return
        for i, tab_id in enumerate(self.nb.tabs()):
            if str(w) == tab_id:
                self.nb.select(i)
                break

    def _ensure_data_tabs(self):
        """
        Excel verileri geldiyse (ders/öğrenci tablosunda kayıtlar varsa)
        aşağıdaki sekmelerin ekli olduğundan emin olur:
          - Sınav Programı
          - Öğrenci Listesi
          - Ders Listesi
        """
        # Sınav Programı
        if "sinav_programi" not in self._tab_refs:
            frm_sp = SinavProgramiPenceresi(self.nb, self.kullanici)
            self.nb.add(frm_sp, text="Sınav Programı")
            self._tab_refs["sinav_programi"] = frm_sp

        # Öğrenci Listesi
        if "ogrenci_listesi" not in self._tab_refs:
            frm_ogr = OgrenciListesiPenceresi(self.nb, self.kullanici)
            self.nb.add(frm_ogr, text="Öğrenci Listesi")
            self._tab_refs["ogrenci_listesi"] = frm_ogr

        # Ders Listesi
        if "ders_listesi" not in self._tab_refs:
            frm_ders = DersListesiPenceresi(self.nb, self.kullanici)
            self.nb.add(frm_ders, text="Ders Listesi")
            self._tab_refs["ders_listesi"] = frm_ders
