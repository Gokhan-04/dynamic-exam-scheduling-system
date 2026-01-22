import tkinter as tk
from tkinter import ttk
from utils.mesaj import bilgi, uyari, hata, sor
from veri_deposu import (
    derslik_listele, derslik_ekle, derslik_guncelle, derslik_sil,
    derslik_ara_id, bolum_getir, derslik_sayisi
)


class DerslikPenceresi(ttk.Frame):
    def __init__(self, master, koordinator, on_derslik_eklendi=None):
        """
        on_derslik_eklendi: AnaPencere'den geçirilirse, ilk derslik eklendikten sonra
        Import sekmesini otomatik aktif etmek için çağrılır.
        """
        super().__init__(master)
        self.koordinator = koordinator
        self.on_derslik_eklendi = on_derslik_eklendi
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Bölüm adı
        bolum = bolum_getir(self.koordinator["bolum_id"])
        baslik = f"Derslik Yönetimi — Bölüm: {bolum['ad']}" if bolum else "Derslik Yönetimi"
        ttk.Label(self, text=baslik, font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        # Liste
        frm_list = ttk.Frame(self, padding=8)
        frm_list.grid(row=1, column=0, sticky="nsew")
        frm_list.columnconfigure(0, weight=1)
        frm_list.rowconfigure(1, weight=1)

        self.tree = ttk.Treeview(
            frm_list,
            columns=("kodu", "adi", "kapasite", "enine", "boyuna", "sira"),
            show="headings",
            height=10,
        )
        for i, (k, ad) in enumerate(
            [
                ("kodu", "Kodu"),
                ("adi", "Adı"),
                ("kapasite", "Kapasite"),
                ("enine", "Enine"),
                ("boyuna", "Boyuna"),
                ("sira", "Sıra Yapısı"),
            ]
        ):
            self.tree.heading(k, text=ad)
            self.tree.column(k, width=120 if i < 2 else 90, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew")

        self.tree.bind("<<TreeviewSelect>>", self._liste_secildi)

        sb = ttk.Scrollbar(frm_list, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=1, column=1, sticky="ns")

        # Form
        frm_form = ttk.LabelFrame(self, text="Ekle/Güncelle", padding=8)
        frm_form.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        labels = [
            "Derslik Kodu",
            "Derslik Adı",
            "Kapasite",
            "Enine (sütun)",
            "Boyuna (sıra)",
            "Sıra Yapısı (2/3/4)",
        ]
        self.vars = [tk.StringVar() for _ in labels]
        for i, lab in enumerate(labels):
            ttk.Label(frm_form, text=lab).grid(row=i, column=0, sticky="w")
            ttk.Entry(frm_form, textvariable=self.vars[i], width=24).grid(row=i, column=1, padx=4, pady=2)

        btns = ttk.Frame(frm_form)
        btns.grid(row=0, column=2, rowspan=3, padx=8)
        ttk.Button(btns, text="Ekle", command=self._ekle).grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Button(btns, text="Güncelle", command=self._guncelle).grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(btns, text="Sil", command=self._sil).grid(row=2, column=0, sticky="ew", pady=2)

        # Arama + Görsel
        frm_arama = ttk.LabelFrame(self, text="Sınıf ID ile Arama / Görselleştir", padding=8)
        frm_arama.grid(row=3, column=0, sticky="ew", padx=8, pady=8)
        ttk.Label(frm_arama, text="Sınıf ID:").grid(row=0, column=0)
        self.var_arama = tk.StringVar()
        ttk.Entry(frm_arama, textvariable=self.var_arama, width=10).grid(row=0, column=1, padx=4)
        ttk.Button(frm_arama, text="Bul ve Göster", command=self._ara_goster).grid(row=0, column=2, padx=4)

        self.canvas = tk.Canvas(
            frm_arama, width=640, height=300, bg="#fafafa", highlightthickness=1, highlightbackground="#ccc"
        )
        self.canvas.grid(row=1, column=0, columnspan=3, pady=(8, 0), sticky="ew")

        self._yenile()

    # --- Yardımcılar ---

    def _int_or_error(self, s: str, alan_adi: str) -> int:
        try:
            v = int(s)
            if v <= 0 and alan_adi != "Sıra Yapısı (2/3/4)":
                raise ValueError
            return v
        except Exception:
            raise ValueError(f"'{alan_adi}' sayısal ve pozitif olmalıdır.")

    def _form_temizle(self):
        for v in self.vars: v.set("")

    # --- Liste & Form akışı ---

    def _yenile(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        liste = derslik_listele(self.koordinator)
        for row in liste:
            iid = str(row["id"])
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=iid,
                values=(row["derslik_kodu"], row["derslik_adi"], row["kapasite"], row["enine"], row["boyuna"], row["sira_yapisi"]),
            )

    def _liste_secildi(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        # Kodu, Adı, Kapasite, Enine, Boyuna, Sıra Yapısı
        for i in range(min(len(self.vars), len(vals))):
            self.vars[i].set(str(vals[i]))

    # --- CRUD ---

    def _ekle(self):
        try:
            kod   = self.vars[0].get().strip()
            ad    = self.vars[1].get().strip()
            if not kod or not ad:
                raise ValueError("Derslik Kodu ve Derslik Adı zorunludur.")

            kapasite = self._int_or_error(self.vars[2].get(), "Kapasite")
            enine    = self._int_or_error(self.vars[3].get(), "Enine (sütun)")
            boyuna   = self._int_or_error(self.vars[4].get(), "Boyuna (sıra)")
            sira     = self._int_or_error(self.vars[5].get(), "Sıra Yapısı (2/3/4)")

            derslik_ekle(self.koordinator, kod, ad, kapasite, enine, boyuna, sira)
            bilgi("Derslik eklendi.")
            self._yenile()
            self._form_temizle()

            # İlk kez derslik eklenmişse Import sekmesini aktifleştir
            if self.on_derslik_eklendi and derslik_sayisi(self.koordinator) > 0:
                self.on_derslik_eklendi()

        except ValueError as ve:
            hata(str(ve))
        except Exception as e:
            hata(str(e))

    def _guncelle(self):
        sel = self.tree.selection()
        if not sel:
            uyari("Güncellemek için listeden bir satır seçin.")
            return
        derslik_id = int(sel[0])
        try:
            kod   = self.vars[0].get().strip()
            ad    = self.vars[1].get().strip()
            if not kod or not ad:
                raise ValueError("Derslik Kodu ve Derslik Adı zorunludur.")

            kapasite = self._int_or_error(self.vars[2].get(), "Kapasite")
            enine    = self._int_or_error(self.vars[3].get(), "Enine (sütun)")
            boyuna   = self._int_or_error(self.vars[4].get(), "Boyuna (sıra)")
            sira     = self._int_or_error(self.vars[5].get(), "Sıra Yapısı (2/3/4)")

            derslik_guncelle(self.koordinator, derslik_id, kod, ad, kapasite, enine, boyuna, sira)
            bilgi("Derslik güncellendi.")
            self._yenile()
        except ValueError as ve:
            hata(str(ve))
        except Exception as e:
            hata(str(e))

    def _sil(self):
        sel = self.tree.selection()
        if not sel:
            uyari("Silmek için listeden bir satır seçin.")
            return
        derslik_id = int(sel[0])
        if not sor("Bu derslik silinsin mi?"):
            return
        try:
            derslik_sil(self.koordinator, derslik_id)
            bilgi("Derslik silindi.")
            self._yenile()
            self._form_temizle()
        except Exception as e:
            hata(str(e))

    # --- Arama & Görselleştirme ---

    def _ara_goster(self):
        try:
            sinif_id = int(self.var_arama.get())
        except Exception:
            hata("Geçerli bir sayı girin.")
            return
        row = derslik_ara_id(self.koordinator, sinif_id)
        if not row:
            uyari("Derslik bulunamadı.")
            return
        self._ciz_oturma_duzeni(row["enine"], row["boyuna"], row["sira_yapisi"])

    def _ciz_oturma_duzeni(self, enine, boyuna, sira_yapisi):
        """İkili/üçlü/dörtlü grupları görsel olarak ayır (küçük boşluk çizgileriyle)."""
        self.canvas.delete("all")
        if not enine or not boyuna:
            return

        pad = 10
        w = int(self.canvas["width"]) - 2 * pad
        h = int(self.canvas["height"]) - 2 * pad
        dx = w / max(enine, 1)
        dy = h / max(boyuna, 1)
        r = min(dx, dy) * 0.3

        for y in range(boyuna):
            for x in range(enine):
                cx = pad + x * dx + dx / 2
                cy = pad + y * dy + dy / 2
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#e5e7eb", outline="#9ca3af")
                # grup ayırıcıları
                if sira_yapisi and (x + 1) % sira_yapisi == 0 and x != enine - 1:
                    gx = pad + (x + 1) * dx
                    self.canvas.create_line(gx, cy - r, gx, cy + r, fill="#cccccc")

        self.canvas.create_text(
            pad, h + pad - 2, text=f"{boyuna} sıra × {enine} sütun | Grup: {sira_yapisi}", anchor="sw", fill="#111"
        )
