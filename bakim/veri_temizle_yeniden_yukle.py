# bakim/veri_temizle_yeniden_yukle.py
# Tek seferlik temizlik: yanlış içe aktarılan "2. Sınıf / DERS KODU / SEÇMELİ DERS / DERSİN ADI"
# gibi kayıtları siler ve sınav programını temizler.
from __future__ import annotations
import re
from veritabani import baglanti

RE_KOD = re.compile(r"^[A-Za-z]{1,6}[-/]?\d{1,4}[A-Za-z0-9\-]*$")

HEADING_LIKE = {
    "2. sınıf","3. sınıf","4. sınıf","1. sınıf","2 sinif","3 sinif","4 sinif",
    "ders kodu","dersin adi","ders adi","secimli ders","secmeli ders","secimlik ders","dersin adı",
    "ders", "ogretim elemani","ogretim uyesi","ogretim gorevlisi"
}

def _norm(s: str) -> str:
    return (s.strip().lower().replace("ı","i").replace("ş","s").replace("ğ","g")
            .replace("ö","o").replace("ü","u").replace("ç","c"))

def temizle(bolum_id: int | None = None):
    with baglanti() as vt:
        # 1) dersler tablosunda kod formatı bozuk olanları sil
        rows = vt.execute("SELECT id, bolum_id, kod, ad, hoca FROM dersler").fetchall()
        sil_ids = []
        for r in rows:
            kod = r["kod"] or ""
            ad  = r["ad"] or ""
            hoca = r["hoca"] or ""
            if bolum_id is not None and r["bolum_id"] != bolum_id:
                continue
            if not RE_KOD.match(kod):
                sil_ids.append(r["id"]); continue
            if _norm(ad) in HEADING_LIKE or _norm(kod) in HEADING_LIKE or _norm(hoca) in HEADING_LIKE:
                sil_ids.append(r["id"]); continue
        if sil_ids:
            q = ",".join("?"*len(sil_ids))
            vt.execute(f"DELETE FROM ogrenci_ders WHERE ders_id IN ({q})", sil_ids)
            vt.execute(f"DELETE FROM dersler WHERE id IN ({q})", sil_ids)
            print(f"{len(sil_ids)} ders silindi.")

        # 2) bu derslerle ilişkili sınav kayıtlarını da güvene al
        if bolum_id is not None:
            vt.execute("DELETE FROM sinav_programi WHERE bolum_id=?", (bolum_id,))
        else:
            vt.execute("DELETE FROM sinav_programi", ())

        print("Sınav programı temizlendi.")

if __name__ == "__main__":
    # Tamamını temizlemek için:
    temizle(bolum_id=None)
    # Sadece belirli bölüm için (ör. 1):
    # temizle(bolum_id=1)
