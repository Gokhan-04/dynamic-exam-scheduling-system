# oturma_atayici.py
from __future__ import annotations
from typing import List, Tuple, Dict, Any

def _g(row_or_dict: Any, key: str, default=None):
    """
    sqlite3.Row ve dict'i aynı şekilde okuyabilmek için güvenli getter.
    Önce indeks erişimi, sonra dict.get dener; olmazsa default döner.
    """
    try:
        return row_or_dict[key]
    except Exception:
        try:
            return row_or_dict.get(key, default)  # type: ignore[attr-defined]
        except Exception:
            return default

def _koltuk_listesi(enine: int, boyuna: int, sira_yapisi: int = 2) -> List[Tuple[int, int]]:
    """
    Yan yana oturmamayı azaltmak için sütun dolaşımını sıra yapısına göre ayarlarız:
      - 2'li: önce tek sütunlar (1,3,5,...) sonra çift sütunlar (2,4,6,...)
      - 3'lü: 1,4,7,... → 2,5,8,... → 3,6,9,... deseni
    """
    if enine <= 0 or boyuna <= 0:
        return []
    sira_yapisi = 3 if int(sira_yapisi or 0) == 3 else 2

    if sira_yapisi == 2:
        tek = [c for c in range(1, enine + 1) if c % 2 == 1]
        cift = [c for c in range(1, enine + 1) if c % 2 == 0]
        siralama = tek + cift
    else:
        grup1 = list(range(1, enine + 1, 3))
        grup2 = list(range(2, enine + 1, 3))
        grup3 = list(range(3, enine + 1, 3))
        siralama = grup1 + grup2 + grup3

    out: List[Tuple[int, int]] = []
    for sira in range(1, boyuna + 1):
        for sut in siralama:
            out.append((sira, sut))
    return out

def atama_yap(ogrenciler: List[Dict], derslikler: List[Any]) -> tuple[list[tuple[int,int,int,int]], list[str]]:
    """
    ogrenciler: [{id, ogr_no, adsoyad}]
    derslikler: sqlite3.Row | dict [{id, derslik_kodu, enine, boyuna, kapasite, sira_yapisi}]
    Dönüş:
      atamalar: [(ogr_id, derslik_id, sira_no, sutun_no)]
      uyarilar: [str]
    """
    uyarilar: list[str] = []
    atamalar: list[tuple[int,int,int,int]] = []

    # Toplam kapasite (enine*boyuna) kontrolü
    toplam_kapasite = 0
    derslik_koltuklari: Dict[int, List[Tuple[int, int]]] = {}
    for dl in derslikler:
        enine = int(_g(dl, "enine", 0) or 0)
        boyuna = int(_g(dl, "boyuna", 0) or 0)
        sira_yapisi = int(_g(dl, "sira_yapisi", 2) or 2)
        dl_id = int(_g(dl, "id"))
        koltuklar = _koltuk_listesi(enine, boyuna, sira_yapisi=sira_yapisi)
        derslik_koltuklari[dl_id] = koltuklar
        toplam_kapasite += len(koltuklar)

    if toplam_kapasite < len(ogrenciler):
        uyarilar.append(f"Kapasite yetersiz: {len(ogrenciler)} öğrenci için {toplam_kapasite} koltuk var.")

    if not ogrenciler:
        return [], ["Bu sınav için öğrenci bulunamadı."]

    # Büyük kapasiteliler önce
    derslikler_sirali = sorted(
        derslikler,
        key=lambda d: int(_g(d, "kapasite", (_g(d, "enine", 0) or 0) * (_g(d, "boyuna", 0) or 0)) or 0),
        reverse=True,
    )

    ogr_idx = 0
    for dl in derslikler_sirali:
        dl_id = int(_g(dl, "id"))
        koltuklar = derslik_koltuklari.get(dl_id, [])
        for (sira, sut) in koltuklar:
            if ogr_idx >= len(ogrenciler):
                break
            og = ogrenciler[ogr_idx]
            ogr_id = int(_g(og, "id"))
            atamalar.append((ogr_id, dl_id, sira, sut))
            ogr_idx += 1
        if ogr_idx >= len(ogrenciler):
            break

    if ogr_idx < len(ogrenciler):
        kalan = len(ogrenciler) - ogr_idx
        uyarilar.append(f"{kalan} öğrenci yerleşemedi (kapasite dolu).")

    return atamalar, uyarilar
