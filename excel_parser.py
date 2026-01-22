# excel_parser.py
from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pandas as pd


# ---------------- yardımcılar ----------------
def _norm(s: str) -> str:
    return (str(s).strip().lower()
            .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
            .replace("ö", "o").replace("ü", "u").replace("ç", "c"))


def _clean_headingish(s: str) -> str:
    return _norm(re.sub(r"[.:;,\-_/]+", " ", s or "")).strip()


def _safe_str(v) -> Optional[str]:
    try:
        if v is None:
            return None
        if pd.isna(v):
            return None
    except Exception:
        pass
    s = str(v).strip()
    return s if s else None


def _as_int_or_none(v) -> Optional[int]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        txt = str(v).strip()
        if not txt:
            return None
        return int(float(txt))
    except Exception:
        return None


# ---------------- kalıplar ----------------
RE_KOD = re.compile(r"^[A-Za-z]{1,6}\s*[-/]?\s*\d{1,4}[A-Za-z0-9\-]*$")  # ders kodu
RE_OGRNO = re.compile(r"^\d{5,}$")  # ogrenci no
RE_TEXTY = re.compile(r"[A-Za-zİIıŞşĞğÜüÖöÇç]")

HEADING_LIKE = {
    "ders kodu", "dersin adi", "ders adi", "ders ismi", "kod", "ad", "adi",
    "secimli ders", "secimlik ders", "secmeli ders", "secmelik ders", "secmeli", "secimlik",
    "1 sinif", "2 sinif", "3 sinif", "4 sinif", "1. sinif", "2. sinif", "3. sinif", "4. sinif",
    "ogretim elemani", "ogretim uyesi", "ogretim gorevlisi", "ders", "bolum", "sinif", "dersin adi"
}

TITLE_TOKENS = ("prof", "doc", "doç", "dr", "ogr", "ögr", "yard", "yrd", "ars", "arş")


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


def _first_nonempty_row_idx(df: pd.DataFrame, max_scan: int = 60) -> int:
    for i in range(min(len(df), max_scan)):
        if any(_safe_str(v) for v in df.iloc[i].values):
            return i
    return 0


# ---- YENİ: Ders kodundan sınıf tahmini (Excel'de sınıf kolonu yoksa) ----
def _infer_sinif_from_kod(kod: Optional[str]) -> Optional[int]:
    """
    Tipik kodlar: CSE101, MAT-205, PHY/301 vb.
    İlk 3-4 basamaktaki rakamların ilk hanesine göre 1..4 sınıf tahmini yapar.
    Örn: 1xx→1, 2xx→2, 3xx→3, 4xx→4. Aksi halde None döner.
    """
    if not kod:
        return None
    s = re.sub(r"\D", "", str(kod))  # yalnız rakamlar
    if not s:
        return None
    first = s[0]
    try:
        d = int(first)
        if 1 <= d <= 4:
            return d
    except Exception:
        pass
    # Bazı bölümlerde 5-8 de görülebilir; bu durumda 1-4'e eşlemeden kaçın.
    return None


# skorlayıcılar
def _score_code_col(series: pd.Series) -> float:
    vals = series.dropna().astype(str).map(str.strip)
    n = len(vals)
    if not n: return 0.0
    return vals.map(lambda x: bool(RE_KOD.match(x))).sum() / n


def _score_name_col(series: pd.Series) -> float:
    vals = series.dropna().astype(str).map(str.strip)
    if not len(vals): return 0.0

    def sc(s: str) -> float:
        if _clean_headingish(s) in HEADING_LIKE:
            return 0.0
        letters = 1.0 if RE_TEXTY.search(s) else 0.0
        spaces = min(s.count(" "), 3) * 0.6
        length = 1.0 if len(s) >= 4 else 0.0
        return letters * 1.5 + spaces + length

    return vals.map(sc).mean()


def _score_ogrno_col(series: pd.Series) -> float:
    vals = series.dropna().astype(str).map(str.strip)
    return (vals.map(lambda x: bool(RE_OGRNO.match(x))).sum() / len(vals)) if len(vals) else 0.0


def _score_grade_col(series: pd.Series) -> float:
    vals = series.dropna()
    if not len(vals): return 0.0

    def _ok(v) -> bool:
        iv = _as_int_or_none(v)
        return iv is not None and 0 <= iv <= 8

    return vals.map(_ok).sum() / len(vals)


# ---------------- DERSLER ----------------
def ders_excel_parse(yol: str) -> Tuple[List[Dict], List[str]]:
    dersler_map: Dict[str, Dict] = {}
    hatalar: List[str] = []
    try:
        xls = pd.ExcelFile(Path(yol))
    except Exception as e:
        return [], [f"Excel açılamadı: {e}"]

    KOD_KEYS = {"ders kodu", "kod", "kodu", "course code", "code", "ders"}
    AD_KEYS = {"dersin adi", "ders adi", "ders ismi", "ad", "adi", "course", "name"}
    HOCA_KEYS = {"hoca", "ogretim uyesi", "instructor", "ogretim gorevlisi", "ogretim elemani"}
    SINIF_KEYS = {"sinif", "grade", "year", "sinifi"}
    TUR_KEYS = {"tur", "type", "zorunlu", "zorunlu/secmeli", "z/s"}

    for sheet in xls.sheet_names:
        try:
            df = xls.parse(sheet, dtype=object)
        except Exception as e:
            hatalar.append(f"Sayfa '{sheet}' okunamadı: {e}")
            continue
        if df.empty:
            continue

        start = _first_nonempty_row_idx(df)
        if start > 0:
            df = df.iloc[start:].reset_index(drop=True)

        # -------- 1) Başlık satırı arama --------
        header_found = False
        for hi in range(min(len(df), 25)):
            vals = [_safe_str(v) or "" for v in df.iloc[hi].values]
            norm = [_clean_headingish(v) for v in vals]
            colmap: Dict[str, int] = {}

            def _find(keys, name):
                for j, v in enumerate(norm):
                    if v in keys and name not in colmap:
                        colmap[name] = j
                        break

            _find(KOD_KEYS, "kod")
            _find(AD_KEYS, "ad")
            _find(HOCA_KEYS, "hoca")
            _find(SINIF_KEYS, "sinif")
            _find(TUR_KEYS, "tur")

            if "kod" in colmap and "ad" in colmap:
                header_found = True
                for ridx in range(hi + 1, len(df)):
                    row = df.iloc[ridx]
                    kod = _safe_str(row.iloc[colmap["kod"]])
                    ad = _safe_str(row.iloc[colmap["ad"]])
                    hoca = _safe_str(row.iloc[colmap["hoca"]]) if "hoca" in colmap else None
                    sinif = _as_int_or_none(row.iloc[colmap["sinif"]]) if "sinif" in colmap else None
                    tur = _safe_str(row.iloc[colmap["tur"]]) if "tur" in colmap else None

                    if kod and _clean_headingish(kod) in HEADING_LIKE:   continue
                    if ad and _clean_headingish(ad) in HEADING_LIKE:   continue
                    if hoca and _clean_headingish(hoca) in HEADING_LIKE: continue
                    if not kod or not ad:                                 continue
                    if not RE_KOD.match(kod):                             continue

                    # güçlü swap
                    if _looks_like_person(ad) or (not _looks_like_course(ad) and _looks_like_course(hoca)):
                        ad, hoca = (hoca, ad) if (hoca or ad) else (ad, hoca)

                    # ---- YENİ: sınıf boş ise koddan sez ----
                    if sinif is None:
                        sinif = _infer_sinif_from_kod(kod)

                    dersler_map[kod] = {"kod": kod, "ad": ad, "hoca": hoca, "sinif": sinif, "tur": tur}
                break

        if header_found:
            continue

        # -------- 2) Otomatik kolon bulma --------
        usable = []
        for c in df.columns:
            nonempty = df[c].map(_safe_str).notna().sum()
            if nonempty >= max(3, int(len(df) * 0.1)):
                usable.append(c)
        if len(usable) < 2:
            usable = list(df.columns)[:2]

        scores = [(c, _score_code_col(df[c].astype(object)), _score_name_col(df[c].astype(object)),
                   _score_grade_col(df[c].astype(object))) for c in usable]
        if not scores:
            continue

        candidates = [s for s in scores if s[1] >= 0.60]
        if not candidates:
            continue
        kod_col = max(candidates, key=lambda x: x[1])[0]
        ad_col = max([s for s in scores if s[0] != kod_col], key=lambda x: x[2], default=scores[0])[0]

        hoca_col = None; sinif_col = None; tur_col = None
        for c, sc_code, sc_name, sc_grade in scores:
            if c not in (kod_col, ad_col) and sc_name >= 1.2 and sc_code < 0.2:
                hoca_col = c; break
        for c, sc_code, sc_name, sc_grade in scores:
            if c not in (kod_col, ad_col) and sc_grade >= 0.5:
                sinif_col = c; break
        for c, sc_code, sc_name, sc_grade in scores:
            if c not in (kod_col, ad_col, hoca_col, sinif_col):
                vals = df[c].dropna().astype(str).map(str.strip)
                if len(vals) and (vals.map(len).mean() <= 12):
                    tur_col = c; break

        for ridx, row in df.iterrows():
            kod = _safe_str(row.get(kod_col))
            ad = _safe_str(row.get(ad_col))
            if kod and _clean_headingish(kod) in HEADING_LIKE:   continue
            if ad and _clean_headingish(ad) in HEADING_LIKE:   continue
            if not kod or not ad:                                  continue
            if not RE_KOD.match(kod):                              continue

            hoca = _safe_str(row.get(hoca_col)) if hoca_col else None
            if hoca and _clean_headingish(hoca) in HEADING_LIKE:
                hoca = None
            sinif = _as_int_or_none(row.get(sinif_col)) if sinif_col else None
            tur = _safe_str(row.get(tur_col)) if tur_col else None

            # güçlü swap
            if _looks_like_person(ad) or (not _looks_like_course(ad) and _looks_like_course(hoca)):
                ad, hoca = (hoca, ad) if (hoca or ad) else (ad, hoca)

            # ---- YENİ: sınıf boş ise koddan sez ----
            if sinif is None:
                sinif = _infer_sinif_from_kod(kod)

            dersler_map[kod] = {"kod": kod, "ad": ad, "hoca": hoca, "sinif": sinif, "tur": tur}

    return list(dersler_map.values()), []


# ---------------- ÖĞRENCİLER ----------------
def ogrenci_excel_parse(yol: str) -> Tuple[List[Dict], List[Tuple[str, str]], List[str]]:
    ogrenciler: Dict[str, Dict] = {}
    kayit_set: set[Tuple[str, str]] = set()
    hatalar: List[str] = []
    try:
        xls = pd.ExcelFile(Path(yol))
    except Exception as e:
        return [], [], [f"Excel açılamadı: {e}"]

    for sheet in xls.sheet_names:
        try:
            df = xls.parse(sheet, dtype=object)
        except Exception as e:
            hatalar.append(f"Sayfa '{sheet}' okunamadı: {e}")
            continue
        if df.empty:
            continue

        start = _first_nonempty_row_idx(df)
        if start > 0:
            df = df.iloc[start:].reset_index(drop=True)

        cols_norm = [_clean_headingish(c) for c in df.columns]
        df.columns = cols_norm

        OGRNO_KEYS = {"ogr_no", "ogrenci no", "ogrenci_no", "ogrenci numarasi", "ogrencino", "numara", "student id",
                      "ogrenci id"}
        ADSOYAD_KEYS = {"adsoyad", "ad soyad", "adi soyadi", "isim", "name"}
        SINIF_KEYS = {"sinif", "grade", "year", "sinifi"}

        col_ogrno = next((c for c in df.columns if c in OGRNO_KEYS), None)
        col_adsoyad = next((c for c in df.columns if c in ADSOYAD_KEYS), None)
        col_sinif = next((c for c in df.columns if c in SINIF_KEYS), None)

        ders_cols = [c for c in df.columns if c.startswith("ders")]
        ders_cols += [c for c in df.columns if c in {"ders_kodu", "ders kodu", "kod", "course code", "code", "course"}]
        ders_cols = list(dict.fromkeys(ders_cols))

        if col_ogrno is None:
            sc = [(c, _score_ogrno_col(df[c].astype(object))) for c in df.columns]
            sc.sort(key=lambda x: x[1], reverse=True)
            if sc and sc[0][1] > 0: col_ogrno = sc[0][0]
        if col_adsoyad is None:
            sc = [(c, _score_name_col(df[c].astype(object))) for c in df.columns]
            sc.sort(key=lambda x: x[1], reverse=True)
            if sc: col_adsoyad = sc[0][0]
        if col_sinif is None:
            sc = [(c, _score_grade_col(df[c].astype(object))) for c in df.columns]
            sc.sort(key=lambda x: x[1], reverse=True)
            if sc and sc[0][1] > 0: col_sinif = sc[0][0]
        if not ders_cols:
            cand = []
            for c in df.columns:
                sc = _score_code_col(df[c].astype(object))
                if sc >= 0.2:
                    cand.append((c, sc))
            cand.sort(key=lambda x: x[1], reverse=True)
            ders_cols = [c for c, _ in cand[:6]]

        for ridx, row in df.iterrows():
            ogr_no = _safe_str(row.get(col_ogrno)) if col_ogrno else None
            adsoyad = _safe_str(row.get(col_adsoyad)) if col_adsoyad else None
            sinif = _as_int_or_none(row.get(col_sinif)) if col_sinif else None

            if not ogr_no:
                hatalar.append(f"Sayfa '{sheet}', satır {ridx + 1}: 'ogr_no' boş veya bulunamadı.")
                continue

            key = ogr_no
            if key not in ogrenciler:
                ogrenciler[key] = {"ogr_no": key, "adsoyad": adsoyad, "sinif": sinif}
            else:
                if adsoyad is not None: ogrenciler[key]["adsoyad"] = adsoyad
                if sinif is not None: ogrenciler[key]["sinif"] = sinif

            for c in ders_cols:
                v = _safe_str(row.get(c))
                if not v: continue
                if RE_KOD.match(v):
                    kayit_set.add((key, v))

    return list(ogrenciler.values()), sorted(kayit_set), hatalar
