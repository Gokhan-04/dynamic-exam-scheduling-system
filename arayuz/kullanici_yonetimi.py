import re
import tkinter as tk
from tkinter import ttk
import bcrypt
from utils.mesaj import bilgi, hata
from veri_deposu import yetkili_kullanici_ekle, tum_bolumleri_getir

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class KullaniciYonetimi(ttk.Frame):
    def __init__(self, master, admin_kullanici):
        super().__init__(master)
        self.admin = admin_kullanici
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text="Kullanıcı Ekle (Admin)", font=("", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(10, 4)
        )

        frm = ttk.Frame(self, padding=8)
        frm.grid(row=1, column=0, sticky="ew")
        for i in range(2):
            frm.columnconfigure(i, weight=1)

        ttk.Label(frm, text="E-posta").grid(row=0, column=0, sticky="w")
        self.ent_eposta = ttk.Entry(frm, width=36)
        self.ent_eposta.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Şifre").grid(row=1, column=0, sticky="w")
        self.ent_sifre = ttk.Entry(frm, width=36, show="*")
        self.ent_sifre.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frm, text="Rol").grid(row=2, column=0, sticky="w")
        self.cmb_rol = ttk.Combobox(frm, values=["admin", "koordinator"], state="readonly", width=18)
        self.cmb_rol.grid(row=2, column=1, sticky="w", pady=2)
        self.cmb_rol.bind("<<ComboboxSelected>>", self._rol_degisti)

        ttk.Label(frm, text="Bölüm (koordinatör için)").grid(row=3, column=0, sticky="w")
        self.cmb_bolum = ttk.Combobox(frm, state="disabled", width=28)
        self.cmb_bolum.grid(row=3, column=1, sticky="w", pady=2)

        # Bölümleri yükle
        bolumler = tum_bolumleri_getir()
        self._bolum_items = [(str(b["id"]), b["ad"]) for b in bolumler]
        if self._bolum_items:
            self.cmb_bolum["values"] = [f"{bid} - {ad}" for bid, ad in self._bolum_items]

        # Varsayılan rol boş kalsın; istersen: self.cmb_rol.set("koordinator")
        btn = ttk.Button(self, text="Kullanıcıyı Ekle", command=self._ekle)
        btn.grid(row=2, column=0, sticky="e", padx=8, pady=8)

        # Kısayollar
        self.bind_all("<Return>", lambda e: self._ekle())
        self.bind_all("<Escape>", lambda e: self._temizle())

        # İlk odak
        self.after(100, self.ent_eposta.focus_set)

    def _rol_degisti(self, *_):
        rol = self.cmb_rol.get()
        if rol == "koordinator":
            self.cmb_bolum.configure(state="readonly")
        else:
            self.cmb_bolum.set("")
            self.cmb_bolum.configure(state="disabled")

    def _temizle(self):
        self.ent_eposta.delete(0, "end")
        self.ent_sifre.delete(0, "end")
        self.cmb_rol.set("")
        self.cmb_bolum.set("")
        self.cmb_bolum.configure(state="disabled")
        self.ent_eposta.focus_set()

    def _ekle(self):
        eposta = (self.ent_eposta.get() or "").strip()
        sifre = (self.ent_sifre.get() or "").strip()
        rol = (self.cmb_rol.get() or "").strip()
        bolum_id = None

        # Alan kontrolleri
        if not eposta or not sifre or not rol:
            hata("E-posta, şifre ve rol zorunludur.")
            return
        if not EMAIL_RE.match(eposta):
            hata("Lütfen geçerli bir e-posta adresi giriniz.")
            return
        if len(sifre) < 6:
            hata("Şifre en az 6 karakter olmalıdır.")
            return

        if rol == "koordinator":
            secim = self.cmb_bolum.get().strip()
            if not secim:
                hata("Koordinatör için bölüm seçiniz.")
                return
            try:
                bid = secim.split(" - ", 1)[0]
                bolum_id = int(bid)
            except Exception:
                hata("Bölüm seçimi geçersiz.")
                return

        try:
            sifre_hash = bcrypt.hashpw(sifre.encode(), bcrypt.gensalt())
            yetkili_kullanici_ekle(self.admin, eposta, sifre_hash, rol, bolum_id)
            bilgi("Kullanıcı eklendi.")
            self._temizle()
        except ValueError as ve:
            # Örn: "Bu bölümde zaten bir koordinatör kayıtlı."
            hata(str(ve))
        except Exception as e:
            hata(str(e))
