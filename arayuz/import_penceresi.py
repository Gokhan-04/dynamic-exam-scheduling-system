# arayuz/import_penceresi.py
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from utils.mesaj import bilgi, hata
from excel_parser import ders_excel_parse, ogrenci_excel_parse
from veri_deposu import dersleri_toplu_yaz, ogrencileri_toplu_yaz_ve_kayitla, derslik_sayisi

LOG_DIR = Path(__file__).resolve().parents[1] / "data"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class ImportPenceresi(ttk.Frame):
    def __init__(self, master, koordinator, on_after_import=None):
        super().__init__(master)
        self.koordinator = koordinator
        self.on_after_import = on_after_import  # ✅ AnaPencere’den gelen callback
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Excel Aktarımları", font=("", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )

        # ---- Ders Listesi Yükleme ----
        frm_ders = ttk.LabelFrame(self, text="Ders Listesi Yükle", padding=8)
        frm_ders.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        ttk.Button(frm_ders, text="Excel seç ve yükle", command=self._ders_yukle).grid(
            row=0, column=0, sticky="w"
        )

        # ---- Öğrenci Listesi Yükleme ----
        frm_ogr = ttk.LabelFrame(self, text="Öğrenci Listesi Yükle", padding=8)
        frm_ogr.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        ttk.Button(frm_ogr, text="Excel seç ve yükle", command=self._ogrenci_yukle).grid(
            row=0, column=0, sticky="w"
        )

        # Bilgi/Hata etiketi (varsayılan boş)
        self.lbl_hata = ttk.Label(self, text="", foreground="#666")
        self.lbl_hata.grid(row=3, column=0, sticky="w", padx=8, pady=(0, 8))

    # ---------- Yardımcılar ----------
    def _derslik_kontrol(self):
        if derslik_sayisi(self.koordinator) == 0:
            hata("Önce en az bir derslik eklemelisiniz. (Gereksinim)")
            return False
        return True

    # ---------- Ders Yükleme ----------
    def _ders_yukle(self):
        if not self._derslik_kontrol():
            return

        yol = filedialog.askopenfilename(
            title="Ders Excel seç",
            filetypes=[("Excel", "*.xlsx *.xls")],
        )
        if not yol:
            return

        # Eski mesajı temizle
        self.lbl_hata.config(text="", foreground="#666")

        dersler, hatalar = ders_excel_parse(yol)

        if dersler:
            dersleri_toplu_yaz(self.koordinator["bolum_id"], dersler)
            bilgi(f"{len(dersler)} ders işlendi.")

            # ✅ Import sonrası callback
            if self.on_after_import:
                self.on_after_import("ders")

        # Hata günlüğü / bilgilendirme
        if hatalar:
            log = LOG_DIR / "ders_yukleme_hatalari.txt"
            log.write_text("\n".join(hatalar), encoding="utf-8")
            renk = "red" if not dersler else "#666"  # hiç kayıt yoksa kırmızı
            self.lbl_hata.config(
                text=f"Bazı satırlar atlandı. Ayrıntılar: {log}",
                foreground=renk,
            )

    # ---------- Öğrenci Yükleme ----------
    def _ogrenci_yukle(self):
        if not self._derslik_kontrol():
            return

        yol = filedialog.askopenfilename(
            title="Öğrenci Excel seç",
            filetypes=[("Excel", "*.xlsx *.xls")],
        )
        if not yol:
            return

        # Eski mesajı temizle
        self.lbl_hata.config(text="", foreground="#666")

        ogrenciler, kayitlar, hatalar = ogrenci_excel_parse(yol)

        if ogrenciler:
            ogrencileri_toplu_yaz_ve_kayitla(
                self.koordinator["bolum_id"], ogrenciler, kayitlar
            )
            bilgi(f"{len(ogrenciler)} öğrenci ve {len(kayitlar)} kayıt işlendi.")

            # ✅ Import sonrası callback
            if self.on_after_import:
                self.on_after_import("ogrenci")

        # Hata günlüğü / bilgilendirme
        if hatalar:
            log = LOG_DIR / "ogrenci_yukleme_hatalari.txt"
            log.write_text("\n".join(hatalar), encoding="utf-8")
            renk = "red" if not ogrenciler else "#666"  # hiç kayıt yoksa kırmızı
            self.lbl_hata.config(
                text=f"Bazı satırlar atlandı. Ayrıntılar: {log}",
                foreground=renk,
            )
