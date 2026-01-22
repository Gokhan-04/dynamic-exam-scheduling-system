# arayuz/sinav_programi_penceresi.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, time
from veri_deposu import (
    dersler_ogrsay_ve_alanlar_detayli, derslikler_kapasite_listesi,
    sinav_programini_temizle, sinav_kaydet, sinav_programi_listele,
    export_sinav_programi_to_excel
)
from planner import PlanKisit, planla

def _msg_info(t): messagebox.showinfo("Bilgi", t)
def _msg_err(t): messagebox.showerror("Hata", t)

class SinavProgramiPenceresi(ttk.Frame):
    def __init__(self, master, koordinator):
        super().__init__(master, padding=10)
        self.k = koordinator
        self._build()

    def _build(self):
        ttk.Label(self, text="Sınav Programı Oluştur", font=("", 12, "bold")).grid(row=0, column=0, sticky="w")

        frm = ttk.LabelFrame(self, text="Kısıtlar", padding=8)
        frm.grid(row=1, column=0, sticky="ew", pady=6)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Dahil Edilecek Dersler:").grid(row=0, column=0, sticky="nw")
        self.lst = tk.Listbox(frm, selectmode="extended", height=8)
        self.lst.grid(row=0, column=1, sticky="ew")
        self._dersleri_yukle_listbox()

        row = 1
        ttk.Label(frm, text="Tarih Aralığı (YYYY-MM-DD):").grid(row=row, column=0, sticky="w")
        self.ent_t1 = ttk.Entry(frm, width=12); self.ent_t1.insert(0, date.today().isoformat())
        self.ent_t2 = ttk.Entry(frm, width=12); self.ent_t2.insert(0, date.today().isoformat())
        self.ent_t1.grid(row=row, column=1, sticky="w"); self.ent_t2.grid(row=row, column=1, sticky="e")

        row += 1
        ttk.Label(frm, text="Dahil Olmayan Günler:").grid(row=row, column=0, sticky="w")
        self.var_we = tk.BooleanVar(value=True)
        self.var_su = tk.BooleanVar(value=True)
        chkfrm = ttk.Frame(frm); chkfrm.grid(row=row, column=1, sticky="w")
        ttk.Checkbutton(chkfrm, text="Cumartesi", variable=self.var_we).pack(side="left")
        ttk.Checkbutton(chkfrm, text="Pazar", variable=self.var_su).pack(side="left")

        row += 1
        ttk.Label(frm, text="Günlük Slot Saatleri:").grid(row=row, column=0, sticky="w")
        self.ent_saatler = ttk.Entry(frm, width=40)
        self.ent_saatler.insert(0, "10:00, 12:30, 14:00, 15:30, 16:45, 17:45, 19:15")
        self.ent_saatler.grid(row=row, column=1, sticky="ew")

        row += 1
        ttk.Label(frm, text="Sınav Türü:").grid(row=row, column=0, sticky="w")
        self.cmb_tur = ttk.Combobox(frm, values=["vize", "final", "butunleme"], state="readonly", width=14)
        self.cmb_tur.set("vize"); self.cmb_tur.grid(row=row, column=1, sticky="w")

        row += 1
        ttk.Label(frm, text="Varsayılan Süre (dk):").grid(row=row, column=0, sticky="w")
        self.ent_sure = ttk.Entry(frm, width=6); self.ent_sure.insert(0, "75")
        self.ent_sure.grid(row=row, column=1, sticky="w")

        row += 1
        ttk.Label(frm, text="Bekleme Süresi (dk):").grid(row=row, column=0, sticky="w")
        self.ent_bekleme = ttk.Entry(frm, width=6); self.ent_bekleme.insert(0, "15")
        self.ent_bekleme.grid(row=row, column=1, sticky="w")

        row += 1
        self.var_nopar = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Hiçbir dersin sınavı aynı anda olmasın (paralel yasak)",
                        variable=self.var_nopar).grid(row=row, column=1, sticky="w")

        bfrm = ttk.Frame(self); bfrm.grid(row=2, column=0, sticky="ew", pady=(8, 4))
        ttk.Button(bfrm, text="Programı Oluştur", command=self._olustur).pack(side="left")
        ttk.Button(bfrm, text="Programı Temizle", command=self._temizle).pack(side="left", padx=6)
        ttk.Button(bfrm, text="Excel'e Aktar", command=self._export_excel).pack(side="left")

        self.tree = ttk.Treeview(self, columns=("kod", "ad", "bas", "bit"), show="headings", height=14)
        for k, t in (("kod", "Ders Kodu"), ("ad", "Ders Adı"), ("bas", "Başlangıç"), ("bit", "Bitiş")):
            self.tree.heading(k, text=t)
            self.tree.column(k, width=160 if k in ("bas", "bit") else 140)
        self.tree.grid(row=3, column=0, sticky="nsew")
        self.rowconfigure(3, weight=1)

        self._listele()

    def _dersleri_yukle_listbox(self):
        self._dersler = dersler_ogrsay_ve_alanlar_detayli(self.k["bolum_id"])
        self.lst.delete(0, "end")
        for d in self._dersler:
            sinif_txt = f" [S{d['sinif']}]" if d.get("sinif") else ""
            self.lst.insert("end", f"{d['kod']} - {d['ad']}{sinif_txt}  ({d['ogr_say']} öğr.)")

    def _secili_ders_ids(self):
        idxs = self.lst.curselection()
        if not idxs:
            return [d["id"] for d in self._dersler]
        return [self._dersler[i]["id"] for i in idxs]

    def _parse_saatler(self):
        out = []
        for p in self.ent_saatler.get().split(","):
            p = p.strip()
            if not p:
                continue
            hh, mm = p.split(":")
            out.append(time(int(hh), int(mm)))
        return out

    def _olustur(self):
        try:
            t1 = date.fromisoformat(self.ent_t1.get().strip())
            t2 = date.fromisoformat(self.ent_t2.get().strip())
            saatler = self._parse_saatler()
            sinav_turu = self.cmb_tur.get()
            default_sure = int(self.ent_sure.get())
            bekleme = int(self.ent_bekleme.get())
            gun_disi = set()
            if self.var_we.get(): gun_disi.add(5)
            if self.var_su.get(): gun_disi.add(6)
            dahil = self._secili_ders_ids()

            dersler = dersler_ogrsay_ve_alanlar_detayli(self.k["bolum_id"])
            derslikler = derslikler_kapasite_listesi(self.k["bolum_id"])

            k = PlanKisit(
                dahil_ders_ids=dahil,
                tarih_bas=t1, tarih_bit=t2,
                gun_disi=gun_disi,
                gunluk_slot_saatleri=saatler,
                sinav_turu=sinav_turu,
                default_sure=default_sure,
                ders_istisna_sure={},
                bekleme_dk=bekleme,
                paralel_yasak=self.var_nopar.get()
            )

            cikti, uyarilar, fatal = planla(k, dersler, derslikler)
            if fatal:
                _msg_err("Program oluşturulamadı.")
                return

            sinav_programini_temizle(self.k["bolum_id"], sinav_turu)

            yerlesemeyen = 0
            for row in cikti:
                if row["baslangic"] is None:
                    yerlesemeyen += 1
                    continue
                b = row["baslangic"].strftime("%Y-%m-%d %H:%M")
                e = row["bitis"].strftime("%Y-%m-%d %H:%M")
                sinav_kaydet(
                    self.k["bolum_id"], row["ders_id"], sinav_turu,
                    b, e, (row["bitis"] - row["baslangic"]).seconds // 60, bekleme,
                    row["derslik_ids"]
                )

            self._listele()

            msg = f"Program üretildi. Yerleşemeyen ders: {yerlesemeyen}"
            if uyarilar:
                msg += "\n\nUyarılar:\n- " + "\n- ".join(uyarilar[:10])
                if len(uyarilar) > 10:
                    msg += f"\n... (+{len(uyarilar) - 10} uyarı)"
            _msg_info(msg)

        except Exception as e:
            _msg_err(str(e))

    def _temizle(self):
        try:
            sinav_turu = self.cmb_tur.get()
            sinav_programini_temizle(self.k["bolum_id"], sinav_turu)
            self._listele()
            _msg_info("Bu sınav türündeki program temizlendi.")
        except Exception as e:
            _msg_err(str(e))

    def _listele(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        sinav_turu = self.cmb_tur.get() or "vize"
        rows = sinav_programi_listele(self.k["bolum_id"], sinav_turu)
        for r in rows:
            self.tree.insert("", "end", values=(r["kod"], r["ad"], r["baslangic"], r["bitis"]))

    def _export_excel(self):
        try:
            sinav_turu = self.cmb_tur.get() or "vize"
            p = filedialog.asksaveasfilename(
                title="Excel kaydet",
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")]
            )
            if not p:
                return
            export_sinav_programi_to_excel(self.k["bolum_id"], sinav_turu, p)
            _msg_info(f"Excel kaydedildi:\n{p}")
        except Exception as e:
            _msg_err(str(e))
