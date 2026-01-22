import tkinter as tk
from tkinter import ttk, messagebox
from veri_deposu import ogrenci_ara_ve_dersleri_getir

class OgrenciListesiPenceresi(ttk.Frame):
    def __init__(self, master, koordinator):
        super().__init__(master, padding=10)
        self.koordinator = koordinator
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Öğrenci No ile Arama:", font=("", 11, "bold")).grid(row=0, column=0, sticky="w")

        arama_frame = ttk.Frame(self)
        arama_frame.grid(row=1, column=0, sticky="ew", pady=6)
        self.ogr_no_var = tk.StringVar()
        ent = ttk.Entry(arama_frame, textvariable=self.ogr_no_var, width=20)
        ent.pack(side="left", padx=(0, 6))
        ttk.Button(arama_frame, text="Ara", command=self._ara).pack(side="left")

        # Enter ile arama
        ent.bind("<Return>", lambda e: self._ara())

        self.sonuc_box = tk.Text(self, height=16, width=64, wrap="word", state="disabled")
        self.sonuc_box.grid(row=2, column=0, pady=10, sticky="nsew")

        # İlk odak
        self.after(100, ent.focus_set)

    def _ara(self):
        ogr_no = (self.ogr_no_var.get() or "").strip()
        if not ogr_no:
            messagebox.showwarning("Uyarı", "Lütfen öğrenci numarasını giriniz.")
            return

        # Text alanını temizle ve kilitle/aç
        def _set_text(text, append=False):
            self.sonuc_box.config(state="normal")
            if not append:
                self.sonuc_box.delete("1.0", "end")
            self.sonuc_box.insert("end", text)
            self.sonuc_box.config(state="disabled")

        try:
            ogrenci, dersler = ogrenci_ara_ve_dersleri_getir(self.koordinator["bolum_id"], ogr_no)
            if not ogrenci:
                _set_text("Öğrenci bulunamadı.")
                return

            satirlar = [f"Öğrenci: {ogrenci['adsoyad']} ({ogrenci['ogr_no']})"]
            if dersler:
                satirlar.append(f"\nAldığı Dersler ({len(dersler)}):")
                for d in dersler:
                    satirlar.append(f"- {d['ad']} (Kodu: {d['kod']})")
            else:
                satirlar.append("\nBu öğrenciye ait ders kaydı bulunamadı.")

            _set_text("\n".join(satirlar))

        except Exception as e:
            messagebox.showerror("Hata", str(e))
