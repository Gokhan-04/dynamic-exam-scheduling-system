# arayuz/oturma_plani_penceresi.py
from __future__ import annotations

import os
import datetime as dt
import tkinter as tk
from tkinter import ttk, filedialog

# Esnek import: Projedeki farklı isim/yerleşimler için güvenli yakalama
# (Kod satırı düşmesin diye tek tek dener)
veri_deposu = None
try:
    import veri_deposu as veri_deposu  # type: ignore
except Exception:
    pass

# PDF yazıcı – imza: oturma_plani_pdf_kaydet(dosya_yolu, sinav_baslik, tarih_saat, derslikler, atamalar)
from raporlar.oturma_plani_pdf import oturma_plani_pdf_kaydet  # type: ignore


def _str(dtobj):
    return dtobj.strftime("%Y-%m-%d %H:%M") if isinstance(dtobj, dt.datetime) else str(dtobj or "")


def _info(parent, msg: str):
    try:
        from utils.mesaj import bilgi
        bilgi(msg)
    except Exception:
        tk.messagebox.showinfo("Bilgi", msg, parent=parent)


def _warn(parent, msg: str):
    try:
        from utils.mesaj import uyari
        uyari(msg)
    except Exception:
        tk.messagebox.showwarning("Uyarı", msg, parent=parent)


def _error(parent, msg: str):
    try:
        from utils.mesaj import hata
        hata(msg)
    except Exception:
        tk.messagebox.showerror("Hata", msg, parent=parent)


class OturmaPlaniPenceresi(ttk.Frame):
    """
    Oturma Planı sekmesi.
    - Hızlı kısıt/süre/slot girişi **KALDIRILDI**. Program, Sınav Programı'ndan okunur.
    - Seçili sınav için oturma planı üretir ve PDF'e yazar.
    """

    KOLONLAR = ("ders_kodu", "ders_adi", "baslangic", "bitis", "derslik")

    def __init__(self, master, get_program_func=None, get_atamalar_func=None, get_derslikler_func=None):
        """
        Parametreler (opsiyonel):
        - get_program_func(sinav_turu:str|None) -> List[Dict]
          Kayıt örn: {'program_id', 'ders_kodu','ders_adi','baslangic','bitis','derslik_kodu', ...}
        - get_atamalar_func(program_id:int) -> List[Dict]
          Örn: {'ogr_no','adsoyad','derslik_id','derslik_kodu','sira_no','sutun_no'}
        - get_derslikler_func(program_id:int|None) -> List[Dict]
          Örn: {'id','derslik_kodu','enine','boyuna','kapasite'}
        """
        super().__init__(master)
        self.get_program_func = get_program_func
        self.get_atamalar_func = get_atamalar_func
        self.get_derslikler_func = get_derslikler_func
        self._build()

        # İlk yükleme
        self._load_program()

    # ---------------------------- UI ----------------------------

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frm = ttk.Frame(self)
        frm.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(0, weight=1)

        # Üstte herhangi bir kısıt/süre alanı YOK (kaldırıldı)

        # Liste
        self.tv = ttk.Treeview(frm, columns=self.KOLONLAR, show="headings", height=18)
        self.tv.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        self.tv.heading("ders_kodu", text="Ders Kodu")
        self.tv.heading("ders_adi", text="Ders Adı")
        self.tv.heading("baslangic", text="Başlangıç")
        self.tv.heading("bitis", text="Bitiş")
        self.tv.heading("derslik", text="Derslik(ler)")

        self.tv.column("ders_kodu", width=120, anchor="w")
        self.tv.column("ders_adi", width=280, anchor="w")
        self.tv.column("baslangic", width=140, anchor="center")
        self.tv.column("bitis", width=140, anchor="center")
        self.tv.column("derslik", width=120, anchor="center")

        # Alt butonlar
        btns = ttk.Frame(frm)
        btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=0)
        btns.columnconfigure(2, weight=0)

        self.btn_olustur = ttk.Button(btns, text="Oturma Planı Oluştur", command=self._click_olustur)
        self.btn_pdf = ttk.Button(btns, text="PDF Olarak Kaydet", command=self._click_pdf)
        self.btn_xlsx = ttk.Button(btns, text="Programı Excel indir", command=self._click_xlsx)

        self.btn_olustur.grid(row=0, column=0, sticky="w")
        self.btn_pdf.grid(row=0, column=1, padx=(8, 0))
        self.btn_xlsx.grid(row=0, column=2, padx=(8, 0))

    # ---------------------------- Data access helpers ----------------------------

    # Program listesi – esnek erişim
    def _fetch_program(self):
        # 1) Özel fonksiyon verilmişse onu kullan
        if callable(self.get_program_func):
            try:
                return self.get_program_func(None)
            except Exception:
                pass

        # 2) veri_deposu varyantlarını sırayla dene
        if veri_deposu:
            for name in [
                "sinav_programi_listele",
                "program_listele",
                "programi_listele",
                "listele_program",
            ]:
                fn = getattr(veri_deposu, name, None)
                if callable(fn):
                    try:
                        return fn()
                    except Exception:
                        continue
        return []

    # Atamalar
    def _fetch_atamalar(self, program_id):
        if callable(self.get_atamalar_func):
            try:
                return self.get_atamalar_func(program_id)
            except Exception:
                pass

        if veri_deposu:
            for name in [
                "oturma_atamalari_getir",
                "oturma_plani_atamalari",
                "atamalari_getir",
            ]:
                fn = getattr(veri_deposu, name, None)
                if callable(fn):
                    try:
                        return fn(program_id)
                    except Exception:
                        continue
        return []

    # Derslik(ler)
    def _fetch_derslikler(self, program_id=None):
        if callable(self.get_derslikler_func):
            try:
                return self.get_derslikler_func(program_id)
            except Exception:
                pass

        if veri_deposu:
            for name in [
                "derslik_listele",
                "derslikleri_listele",
                "listele_derslik",
            ]:
                fn = getattr(veri_deposu, name, None)
                if callable(fn):
                    try:
                        return fn()
                    except Exception:
                        continue
        return []

    # Oturma planı üretici (hesap)
    def _create_plan_if_needed(self, program_id):
        """
        Eğer atama yoksa, depodaki üretici fonksiyonlardan birini deneyerek oluşturur.
        Varsa dokunmaz.
        """
        atamalar = self._fetch_atamalar(program_id)
        if atamalar:
            return atamalar

        if veri_deposu:
            for name in [
                "oturma_plani_olustur",
                "oturma_planini_olustur",
                "plan_olustur",
            ]:
                fn = getattr(veri_deposu, name, None)
                if callable(fn):
                    try:
                        fn(program_id)  # yan etkili oluşturuyorsa
                        break
                    except Exception:
                        continue
        # tekrar oku
        return self._fetch_atamalar(program_id)

    # ---------------------------- Actions ----------------------------

    def _load_program(self):
        self.tv.delete(*self.tv.get_children())
        program = self._fetch_program()

        # Beklenen alanları normalize et
        for rec in program:
            pid = rec.get("program_id") or rec.get("id") or rec.get("pid")
            ders_kodu = rec.get("ders_kodu") or rec.get("kod") or rec.get("code") or ""
            ders_adi = rec.get("ders_adi") or rec.get("ad") or rec.get("name") or ""
            bas = rec.get("baslangic") or rec.get("start") or rec.get("bas_tarih") or ""
            bit = rec.get("bitis") or rec.get("end") or rec.get("bit_tarih") or ""
            derslik = rec.get("derslik_kodu") or rec.get("derslik") or rec.get("room") or ""

            # datetime ise yazıya çevir
            bas_s = _str(bas)
            bit_s = _str(bit)

            iid = f"p_{pid}"
            self.tv.insert("", "end", iid=iid, values=(ders_kodu, ders_adi, bas_s, bit_s, derslik), tags=(str(pid),))

    def _get_selected_program_id(self):
        sel = self.tv.selection()
        if not sel:
            return None
        iid = sel[0]
        tags = self.tv.item(iid, "tags") or []
        if not tags:
            return None
        try:
            return int(tags[0])
        except Exception:
            return tags[0]  # en azından döndür

    def _click_olustur(self):
        pid = self._get_selected_program_id()
        if pid is None:
            _warn(self, "Lütfen listeden bir sınav seçin.")
            return

        atamalar = self._create_plan_if_needed(pid)
        if not atamalar:
            _warn(self, "Bu sınav için derslik/atama bulunamadı veya oluşturulamadı.")
            return

        _info(self, "Oturma planı oluşturuldu.")

    def _click_pdf(self):
        pid = self._get_selected_program_id()
        if pid is None:
            _warn(self, "Lütfen listeden bir sınav seçin.")
            return

        # Seçili sınavın satırından başlık ve tarih-saat bilgilerini toparla
        item = self.tv.item(self.tv.selection()[0])
        v = item.get("values", ["", "", "", "", ""])
        ders_kodu, ders_adi, bas_s, bit_s, derslik_kisa = (v + ["", "", "", "", ""])[:5]

        # Başlık ve tarih/saat
        sinav_baslik = f"{ders_kodu} – {ders_adi}".strip(" –")
        tarih_saat = f"{bas_s} - {bit_s}".strip()

        # Atamalar & derslikler
        atamalar = self._create_plan_if_needed(pid)
        if not atamalar:
            _warn(self, "Bu sınava ait derslik/atama bulunamadı (PDF üretilemedi).")
            return

        derslikler = self._fetch_derslikler(pid)
        if not derslikler:
            # Bazı veri depolarında derslik listesi global gelir; gene de boşsa PDF'i uyarı ile üretelim
            derslikler = []

        # Dosya yolu sor
        default_name = f"oturma_plani_{ders_kodu or 'sinav'}.pdf"
        pth = filedialog.asksaveasfilename(
            parent=self,
            title="PDF Kaydet",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF Dosyası", "*.pdf"), ("Tüm Dosyalar", "*.*")],
        )
        if not pth:
            return

        try:
            # İMZA sabit: (dosya_yolu, sinav_baslik, tarih_saat, derslikler, atamalar)
            oturma_plani_pdf_kaydet(
                dosya_yolu=pth,
                sinav_baslik=sinav_baslik,
                tarih_saat=tarih_saat,
                derslikler=derslikler,
                atamalar=atamalar,
            )
        except TypeError as e:
            # Yanlış anahtar adı ile çağrılmışsa, pozisyonel fallback
            try:
                oturma_plani_pdf_kaydet(pth, sinav_baslik, tarih_saat, derslikler, atamalar)  # type: ignore
            except Exception:
                _error(self, f"PDF oluşturulamadı:\n{e}")
                return
        except Exception as e:
            _error(self, f"PDF oluşturulamadı:\n{e}")
            return

        _info(self, f"PDF kaydedildi:\n{os.path.basename(pth)}")

    def _click_xlsx(self):
        """
        Basit program dökümü. Projende zaten bir Excel çıktı modülü varsa
        burada sadece devre dışı bırakıldığı mesajını gösteriyoruz (mevcut davranışı korumak için).
        """
        _info(self, "Excel çıktı modülü bu ekranda devre dışı bırakıldı.")
