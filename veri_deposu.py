# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, date, time, timedelta
from typing import List, Dict, Tuple, Set, Optional
import re

from veritabani import baglanti
from raporlar.sinav_programi_excel import programi_xlsx_yaz

# -------- doğrulamalar / yardımcılar --------
RE_DERSKODU = re.compile(r"^[A-Za-z]{1,6}[-/]?\d{1,4}[A-Za-z0-9\-]*$")

def _norm(s: str) -> str:
    return (str(s).strip().lower()
            .replace("ı","i").replace("ş","s").replace("ğ","g")
            .replace("ö","o").replace("ü","u").replace("ç","c"))

def _clean_headingish(s: str) -> str:
    return _norm(re.sub(r"[.:;,\-_/]+", " ", s or ""))

HEADING_LIKE = {
    "ders kodu","dersin adi","ders adi","ders ismi","kod","ad","adi",
    "secimli ders","secimlik ders","secmeli ders","secmelik ders","secmeli","secimlik",
    "1 sinif","2 sinif","3 sinif","4 sinif","1. sinif","2. sinif","3. sinif","4. sinif",
    "ogretim elemani","ogretim uyesi","ogretim gorevlisi","ders","bolum","sinif","dersin adi"
}
TITLE_TOKENS = ("prof", "doc", "doç", "dr", "ogr", "ögr", "yard", "yrd", "ars", "arş")

def _is_heading_like(s: Optional[str]) -> bool:
    if not s: return False
    return _clean_headingish(s) in HEADING_LIKE or bool(re.match(r"^\s*\d+\s*\.?\s*sinif\s*$", _clean_headingish(s)))

def _looks_like_person(s: Optional[str]) -> bool:
    if not s: return False
    sn = _norm(s)
    return any(tok in sn for tok in TITLE_TOKENS)

def _looks_like_course(s: Optional[str]) -> bool:
    if not s: return False
    sn = _norm(s)
    if any(tok in sn for tok in TITLE_TOKENS):
        return False
    return len(s.strip()) >= 5 and (" " in s or len(s) >= 8)

def _ensure_iterable(x):
    if x is None: return []
    if isinstance(x, (list, tuple, set)): return x
    return [x]

# =========================================================
# 🔹 Kullanıcı & Bölüm
# =========================================================
def kullanici_bul(eposta: str):
    with baglanti() as vt:
        return vt.execute("SELECT * FROM kullanicilar WHERE eposta=?", (eposta,)).fetchone()

def _bolumde_koordinator_var_mi(bolum_id: int) -> bool:
    with baglanti() as vt:
        row = vt.execute(
            "SELECT COUNT(*) AS adet FROM kullanicilar WHERE rol='koordinator' AND bolum_id=?",
            (bolum_id,)
        ).fetchone()
        return (row["adet"] or 0) > 0

def yetkili_kullanici_ekle(giris_yapan, eposta: str, sifre_hash: bytes, rol: str, bolum_id: Optional[int]):
    if giris_yapan["rol"] != "admin":
        raise PermissionError("Yeni kullanıcı ekleme yetkisi yalnızca admin’dedir.")
    if rol not in ("admin", "koordinator"):
        raise ValueError("Rol 'admin' veya 'koordinator' olmalıdır.")
    if rol == "koordinator":
        if not bolum_id:
            raise ValueError("Koordinatör için bölüm seçilmelidir.")
        if _bolumde_koordinator_var_mi(bolum_id):
            raise ValueError("Bu bölümde zaten bir koordinatör kayıtlı.")
    if rol == "admin":
        bolum_id = None

    with baglanti() as vt:
        vt.execute(
            "INSERT INTO kullanicilar(eposta,sifre_hash,rol,bolum_id) VALUES(?,?,?,?)",
            (eposta, sifre_hash, rol, bolum_id)
        )

def tum_bolumleri_getir():
    with baglanti() as vt:
        return vt.execute("SELECT id, ad FROM bolumler ORDER BY ad").fetchall()

def kullaniciya_gorunecek_bolumler(kullanici):
    with baglanti() as vt:
        if kullanici["rol"] == "admin" or kullanici["bolum_id"] is None:  # <<< BURADAYDI
            return vt.execute("SELECT id, ad FROM bolumler ORDER BY ad").fetchall()
        return vt.execute("SELECT id, ad FROM bolumler WHERE id=?", (kullanici["bolum_id"],)).fetchall()

def bolum_getir(bolum_id: int):
    with baglanti() as vt:
        return vt.execute("SELECT id, ad FROM bolumler WHERE id=?", (bolum_id,)).fetchone()

# =========================================================
# 🔹 Yardımcılar: Çakışma Kontrolü
# =========================================================
def _zaman_cakisiyor_mu(bas1: datetime, bit1: datetime, bas2: datetime, bit2: datetime) -> bool:
    return not (bit1 <= bas2 or bit2 <= bas1)

def _derslikte_cakisiyor_mu(vt, bolum_id: int, sinav_turu: str,
                            derslik_id: int, bas_dt: datetime, bit_dt: datetime) -> bool:
    q = vt.execute(
        """
        SELECT sp.baslangic, sp.bitis
        FROM sinav_programi sp
        JOIN sinav_programi_derslik spd ON spd.sinav_id = sp.id
        WHERE sp.bolum_id=? AND sp.sinav_turu=? AND spd.derslik_id=?
          AND NOT (sp.bitis <= ? OR sp.baslangic >= ?)
        """,
        (bolum_id, sinav_turu, derslik_id,
         bas_dt.isoformat(timespec="minutes"),
         bit_dt.isoformat(timespec="minutes"))
    ).fetchone()
    return q is not None

# =========================================================
# 🔹 Derslik CRUD
# =========================================================
def derslik_listele(koordinator):
    if koordinator["rol"] != "koordinator":
        return []
    with baglanti() as vt:
        return vt.execute("""
            SELECT id, derslik_kodu, derslik_adi, kapasite, enine, boyuna, sira_yapisi
            FROM derslikler
            WHERE bolum_id=?
            ORDER BY derslik_kodu
        """, (koordinator["bolum_id"],)).fetchall()

def derslik_sayisi(koordinator) -> int:
    if koordinator["rol"] != "koordinator":
        return 0
    with baglanti() as vt:
        row = vt.execute(
            "SELECT COUNT(*) AS adet FROM derslikler WHERE bolum_id=?",
            (koordinator["bolum_id"],)
        ).fetchone()
        return row["adet"] or 0

def derslik_ekle(koordinator, derslik_kodu, derslik_adi, kapasite, enine, boyuna, sira_yapisi):
    if koordinator["rol"] != "koordinator":
        raise PermissionError("Derslik ekleme yetkisi yalnızca bölüm koordinatöründedir.")
    with baglanti() as vt:
        vt.execute("""
            INSERT INTO derslikler(bolum_id, derslik_kodu, derslik_adi, kapasite, enine, boyuna, sira_yapisi)
            VALUES(?,?,?,?,?,?,?)
        """, (koordinator["bolum_id"], derslik_kodu, derslik_adi, kapasite, enine, boyuna, sira_yapisi))

def derslik_guncelle(koordinator, derslik_id, derslik_kodu, derslik_adi, kapasite, enine, boyuna, sira_yapisi):
    if koordinator["rol"] != "koordinator":
        raise PermissionError("Güncelleme yetkisi yalnızca bölüm koordinatöründedir.")
    with baglanti() as vt:
        vt.execute("""
            UPDATE derslikler
            SET derslik_kodu=?, derslik_adi=?, kapasite=?, enine=?, boyuna=?, sira_yapisi=?
            WHERE id=? AND bolum_id=?
        """, (derslik_kodu, derslik_adi, kapasite, enine, boyuna, sira_yapisi, derslik_id, koordinator["bolum_id"]))

def derslik_sil(koordinator, derslik_id):
    if koordinator["rol"] != "koordinator":
        raise PermissionError("Silme yetkisi yalnızca bölüm koordinatöründedir.")
    with baglanti() as vt:
        vt.execute("DELETE FROM derslikler WHERE id=? AND bolum_id=?", (derslik_id, koordinator["bolum_id"]))

def derslik_ara_id(koordinator, sinif_id):
    if koordinator["rol"] != "koordinator":
        return None
    with baglanti() as vt:
        return vt.execute("""
            SELECT id, derslik_kodu, derslik_adi, kapasite, enine, boyuna, sira_yapisi
            FROM derslikler
            WHERE id=? AND bolum_id=?
        """, (sinif_id, koordinator["bolum_id"])).fetchone()

# =========================================================
# 🔹 Ders & Öğrenci (Excel ile toplu)
# =========================================================
def dersleri_toplu_yaz(bolum_id: int, ders_listesi: list[dict]):
    with baglanti() as vt:
        for d in ders_listesi:
            kod = (d.get('kod') or "").strip()
            ad  = (d.get('ad')  or "").strip()
            hoca = (d.get('hoca') or None)
            sinif = d.get('sinif'); tur = d.get('tur')

            if not kod or not ad:
                continue
            if _is_heading_like(kod) or _is_heading_like(ad) or (hoca and _is_heading_like(hoca)):
                continue
            if not RE_DERSKODU.match(kod):
                continue

            # güçlü swap
            if _looks_like_person(ad) or (not _looks_like_course(ad) and _looks_like_course(hoca)):
                ad, hoca = (hoca, ad) if (hoca or ad) else (ad, hoca)

            vt.execute("""
                INSERT INTO dersler(bolum_id,kod,ad,hoca,sinif,tur)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(bolum_id,kod) DO UPDATE SET
                  ad=excluded.ad,
                  hoca=COALESCE(excluded.hoca, dersler.hoca),
                  sinif=COALESCE(excluded.sinif, dersler.sinif),
                  tur=COALESCE(excluded.tur, dersler.tur)
            """, (bolum_id, kod, ad, hoca, sinif, tur))

def ogrencileri_toplu_yaz_ve_kayitla(bolum_id: int, ogrenciler: list[dict], kayitlar: list[tuple[str, str]]):
    with baglanti() as vt:
        for o in ogrenciler:
            vt.execute("""
                INSERT INTO ogrenciler(bolum_id,ogr_no,adsoyad,sinif)
                VALUES(?,?,?,?)
                ON CONFLICT(bolum_id,ogr_no) DO UPDATE SET
                  adsoyad=excluded.adsoyad,
                  sinif=COALESCE(excluded.sinif, ogrenciler.sinif)
            """, (bolum_id, o.get('ogr_no'), o.get('adsoyad'), o.get('sinif')))

        ogr_map = {row["ogr_no"]: row["id"]
                   for row in vt.execute("SELECT id, ogr_no FROM ogrenciler WHERE bolum_id=?", (bolum_id,))}
        ders_map = {row["kod"]: row["id"]
                    for row in vt.execute("SELECT id, kod FROM dersler WHERE bolum_id=?", (bolum_id,))}

        for ogr_no, ders_kod in kayitlar:
            if not RE_DERSKODU.match(ders_kod or ""):
                continue
            ogr_id = ogr_map.get(ogr_no)
            ders_id = ders_map.get(ders_kod)
            if ogr_id and ders_id:
                vt.execute("INSERT OR IGNORE INTO ogrenci_ders(ogrenci_id, ders_id) VALUES(?,?)", (ogr_id, ders_id))

def ogrenci_ara_ve_dersleri_getir(bolum_id: int, ogr_no: str):
    with baglanti() as vt:
        ogr = vt.execute("""
            SELECT id, ogr_no, adsoyad, sinif FROM ogrenciler
            WHERE bolum_id=? AND ogr_no=?
        """, (bolum_id, ogr_no)).fetchone()
        if not ogr:
            return None, []
        dersler = vt.execute("""
            SELECT d.kod, d.ad
            FROM ogrenci_ders od
            JOIN dersler d ON d.id = od.ders_id
            WHERE od.ogrenci_id=?
            ORDER BY d.kod
        """, (ogr["id"],)).fetchall()
        return ogr, dersler

# =========================================================
# 🔹 Sınav Programı (Planlayıcı için I/O)
# =========================================================
def _program_satiri_yaz(vt, bolum_id: int, ders_id: int, sinav_turu: str,
                        bas_dt: datetime, bit_dt: datetime, bekleme_dk: int,
                        derslik_ids: list[int]) -> int:
    for dl in _ensure_iterable(derslik_ids):
        if _derslikte_cakisiyor_mu(vt, bolum_id, sinav_turu, int(dl), bas_dt, bit_dt):
            raise ValueError(
                f"Derslik çakışması: derslik_id={dl} {bas_dt:%Y-%m-%d %H:%M}–{bit_dt:%H:%M} saatinde başka bir sınavla çakışıyor."
            )

    sure_dk = max(1, int(round((bit_dt - bas_dt).total_seconds() / 60.0)))
    r = vt.execute("""
        INSERT INTO sinav_programi(bolum_id, ders_id, sinav_turu, baslangic, bitis, sure_dk, bekleme_dk)
        VALUES(?,?,?,?,?,?,?)
        RETURNING id
    """, (bolum_id, ders_id, sinav_turu,
          bas_dt.isoformat(timespec="minutes"),
          bit_dt.isoformat(timespec="minutes"),
          sure_dk, int(bekleme_dk))).fetchone()
    sp_id = r["id"]
    for dl in _ensure_iterable(derslik_ids):
        vt.execute("INSERT INTO sinav_programi_derslik(sinav_id, derslik_id) VALUES(?,?)", (sp_id, int(dl)))
    return sp_id

def plan_kaynagini_hazirla(bolum_id: int) -> tuple[list[dict], list[dict]]:
    with baglanti() as vt:
        derslikler = vt.execute("""
            SELECT id, derslik_kodu, kapasite, enine, boyuna
            FROM derslikler
            WHERE bolum_id=?
            ORDER BY kapasite DESC
        """, (bolum_id,)).fetchall()
        dersler = vt.execute("""
            SELECT d.id, d.kod, d.ad, d.hoca, d.sinif
            FROM dersler d WHERE d.bolum_id=? ORDER BY d.kod
        """, (bolum_id,)).fetchall()

        out = []
        for d in dersler:
            ogr_ids_rows = vt.execute(
                "SELECT ogrenci_id FROM ogrenci_ders WHERE ders_id=?", (d["id"],)
            ).fetchall()
            ogr_ids = {r["ogrenci_id"] for r in ogr_ids_rows}

            # --- YENİ: ders sinif bilgisi yoksa öğrencilerin sinif modunu kullan ---
            ders_sinif = d["sinif"]
            if ders_sinif is None and ogr_ids:
                # öğrencilerin sinif değerlerini topla
                sinif_rows = vt.execute(
                    f"SELECT sinif FROM ogrenciler WHERE id IN ({','.join(['?']*len(ogr_ids))})",
                    tuple(ogr_ids)
                ).fetchall()
                frek: Dict[int, int] = {}
                for r in sinif_rows:
                    try:
                        if r["sinif"] is None:
                            continue
                        s = int(r["sinif"])
                        frek[s] = frek.get(s, 0) + 1
                    except Exception:
                        continue
                if frek:
                    # en sık görülen sınıfı ata
                    ders_sinif = sorted(frek.items(), key=lambda x: (-x[1], x[0]))[0][0]

            out.append({
                "id": d["id"], "kod": d["kod"], "ad": d["ad"],
                "hoca": d["hoca"], "sinif": ders_sinif,
                "ogr_say": len(ogr_ids), "ogr_ids": ogr_ids
            })
        return out, list(derslikler)

def sinav_programi_kaydet(bolum_id: int, sinav_turu: str, yerlestirmeler: list[dict], bekleme_dk: int = 0):
    with baglanti() as vt:
        for y in yerlestirmeler:
            if y.get("baslangic") is None:
                continue
            _program_satiri_yaz(vt, bolum_id, int(y["ders_id"]), sinav_turu,
                                y["baslangic"], y["bitis"], int(bekleme_dk), [int(x) for x in (y["derslik_ids"] or [])])

def sinav_programi_detay(bolum_id: int, sinav_turu: str):
    stur = (sinav_turu or "vize").strip().lower()
    with baglanti() as vt:
        return vt.execute("""
            SELECT sp.id, d.id AS ders_id, d.kod, d.ad, sp.baslangic, sp.bitis
            FROM sinav_programi sp
            JOIN dersler d ON d.id = sp.ders_id
            WHERE sp.bolum_id=? AND sp.sinav_turu=?
            ORDER BY sp.baslangic, d.kod
        """, (bolum_id, stur)).fetchall()

def sinav_derslikleri(sinav_id: int):
    with baglanti() as vt:
        return vt.execute("""
            SELECT dl.id, dl.derslik_kodu, dl.enine, dl.boyuna, dl.kapasite
            FROM sinav_programi_derslik spd
            JOIN derslikler dl ON dl.id=spd.derslik_id
            WHERE spd.sinav_id=?
            ORDER BY dl.kapasite DESC
        """, (sinav_id,)).fetchall()

def derse_kayitli_ogrenciler(ders_id: int):
    with baglanti() as vt:
        return vt.execute("""
            SELECT o.id, o.ogr_no, o.adsoyad
            FROM ogrenci_ders od
            JOIN ogrenciler o ON o.id=od.ogrenci_id
            WHERE od.ders_id=?
            ORDER BY o.ogr_no
        """, (ders_id,)).fetchall()

# =========================================================
# 🔹 Oturma Planı
# =========================================================
def oturma_plani_temizle(sinav_id: int):
    with baglanti() as vt:
        vt.execute("DELETE FROM oturma_plani WHERE sinav_id=?", (sinav_id,))

def oturma_plani_kaydet(sinav_id: int, atamalar: list[tuple[int, int, int, int]]):
    with baglanti() as vt:
        for ogr_id, derslik_id, sira, sut in atamalar:
            vt.execute("""
                INSERT INTO oturma_plani(sinav_id, ogrenci_id, derslik_id, sira_no, sutun_no)
                VALUES(?,?,?,?,?)
            """, (sinav_id, ogr_id, derslik_id, sira, sut))

def oturma_plani_listele(sinav_id: int):
    with baglanti() as vt:
        return vt.execute("""
            SELECT op.ogrenci_id, o.adsoyad, o.ogr_no, dl.derslik_kodu,
                   op.sira_no, op.sutun_no
            FROM oturma_plani op
            JOIN ogrenciler o ON o.id=op.ogrenci_id
            JOIN derslikler dl ON dl.id=op.derslik_id
            WHERE op.sinav_id=?
            ORDER BY dl.derslik_kodu, op.sira_no, op.sutun_no
        """, (sinav_id,)).fetchall()

# =========================================================
# 🔹 Örnek program (opsiyonel)
# =========================================================
def ornek_sinav_programi_olustur(bolum_id: int, sinav_turu: str):
    eklenen = 0
    uyarilar: list[str] = []
    dersler, derslikler = plan_kaynagini_hazirla(bolum_id)
    if not dersler or not derslikler:
        return 0, ["Ders veya derslik yok."]

    base = datetime.now().date()
    with baglanti() as vt:
        for i, d in enumerate(dersler):
            bas = datetime.combine(base + timedelta(days=i // 3), time(9 + 2 * (i % 3), 0))
            bit = bas + timedelta(minutes=90)
            try:
                _program_satiri_yaz(vt, bolum_id, d["id"], sinav_turu, bas, bit, 15, [derslikler[0]["id"]])
                eklenen += 1
            except ValueError as e:
                uyarilar.append(str(e))
    return eklenen, uyarilar

# =========================================================
# 🔹 UI için uyumluluk API'leri
# =========================================================
def dersler_ogrsay_ve_alanlar_detayli(bolum_id: int) -> list[dict]:
    with baglanti() as vt:
        dersler = vt.execute("""
            SELECT d.id, d.kod, d.ad, d.hoca, d.sinif
            FROM dersler d
            WHERE d.bolum_id=?
            ORDER BY d.kod
        """, (bolum_id,)).fetchall()

        out = []
        for d in dersler:
            ogr_ids = {r["ogrenci_id"] for r in vt.execute(
                "SELECT ogrenci_id FROM ogrenci_ders WHERE ders_id=?", (d["id"],)
            ).fetchall()}

            # --- YENİ: sinif boşsa öğrencilerden mod ---
            ders_sinif = d["sinif"]
            if ders_sinif is None and ogr_ids:
                sinif_rows = vt.execute(
                    f"SELECT sinif FROM ogrenciler WHERE id IN ({','.join(['?']*len(ogr_ids))})",
                    tuple(ogr_ids)
                ).fetchall()
                frek: Dict[int, int] = {}
                for r in sinif_rows:
                    try:
                        if r["sinif"] is None:
                            continue
                        s = int(r["sinif"])
                        frek[s] = frek.get(s, 0) + 1
                    except Exception:
                        continue
                if frek:
                    ders_sinif = sorted(frek.items(), key=lambda x: (-x[1], x[0]))[0][0]

            out.append({
                "id": d["id"], "kod": d["kod"], "ad": d["ad"],
                "hoca": d["hoca"], "sinif": ders_sinif,
                "ogr_say": len(ogr_ids), "ogr_ids": ogr_ids
            })
        return out

def derslikler_kapasite_listesi(bolum_id: int) -> list[dict]:
    with baglanti() as vt:
        return vt.execute("""
            SELECT id, derslik_kodu, kapasite, enine, boyuna
            FROM derslikler
            WHERE bolum_id=?
            ORDER BY kapasite DESC
        """, (bolum_id,)).fetchall()

def sinav_programini_temizle(bolum_id: int, sinav_turu: str):
    with baglanti() as vt:
        ids = [r["id"] for r in vt.execute(
            "SELECT id FROM sinav_programi WHERE bolum_id=? AND sinav_turu=?",
            (bolum_id, sinav_turu)
        ).fetchall()]
        if ids:
            q = ",".join("?" * len(ids))
            vt.execute(f"DELETE FROM oturma_plani WHERE sinav_id IN ({q})", ids)
            vt.execute(f"DELETE FROM sinav_programi_derslik WHERE sinav_id IN ({q})", ids)
            vt.execute("DELETE FROM sinav_programi WHERE bolum_id=? AND sinav_turu=?", (bolum_id, sinav_turu))

def sinav_kaydet(bolum_id: int, ders_id: int, sinav_turu: str,
                 baslangic_txt: str, bitis_txt: str, sure_dk: int, bekleme_dk: int,
                 derslik_ids: list[int]) -> int:
    bas_dt = datetime.fromisoformat(baslangic_txt)
    bit_dt = datetime.fromisoformat(bitis_txt)
    with baglanti() as vt:
        return _program_satiri_yaz(vt, bolum_id, ders_id, sinav_turu, bas_dt, bit_dt, int(bekleme_dk), derslik_ids)

def sinav_programi_listele(bolum_id: int, sinav_turu: str):
    with baglanti() as vt:
        return vt.execute("""
            SELECT sp.id, d.kod, d.ad, sp.baslangic, sp.bitis
            FROM sinav_programi sp
            JOIN dersler d ON d.id=sp.ders_id
            WHERE sp.bolum_id=? AND sp.sinav_turu=?
            ORDER BY sp.baslangic, d.kod
        """, (bolum_id, sinav_turu)).fetchall()

def export_sinav_programi_to_excel(bolum_id: int, sinav_turu: str, dosya_yolu: str):
    with baglanti() as vt:
        rows = vt.execute("""
            SELECT sp.id, sp.baslangic, sp.bitis, d.kod, d.ad, d.hoca, b.ad AS bolum_adi
            FROM sinav_programi sp
            JOIN dersler d ON d.id=sp.ders_id
            JOIN bolumler b ON b.id=sp.bolum_id
            WHERE sp.bolum_id=? AND sp.sinav_turu=?
            ORDER BY sp.baslangic, d.kod
        """, (bolum_id, sinav_turu)).fetchall()

        payload = []
        for r in rows:
            if not RE_DERSKODU.match(r["kod"] or ""):
                continue

            bas = datetime.fromisoformat(r["baslangic"])
            bit = datetime.fromisoformat(r["bitis"])
            ad = r["ad"]; hoca = r["hoca"]

            if _is_heading_like(ad) or _is_heading_like(hoca):
                continue

            # çok güçlü swap
            if _looks_like_person(ad) or (not _looks_like_course(ad) and _looks_like_course(hoca)):
                ad, hoca = (hoca, ad) if (hoca or ad) else (ad, hoca)

            derslikler = [x["derslik_kodu"] for x in vt.execute("""
                SELECT dl.derslik_kodu
                FROM sinav_programi_derslik spd
                JOIN derslikler dl ON dl.id=spd.derslik_id
                WHERE spd.sinav_id=?
                ORDER BY dl.kapasite DESC
            """, (r["id"],)).fetchall()]

            if not ad:
                continue

            payload.append({
                "bolum": r["bolum_adi"],
                "tarih": bas.date(),
                "saat": bas.time().strftime("%H:%M"),
                "bas": bas, "bit": bit,
                "kod": r["kod"], "ad": ad, "hoca": hoca,
                "derslikler": derslikler
            })

    programi_xlsx_yaz(dosya_yolu, payload, sinav_turu=sinav_turu)
