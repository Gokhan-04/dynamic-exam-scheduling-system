# koltuk_atama.py
from __future__ import annotations
from typing import List, Dict, Tuple

def _koltuk_listesi(enine: int, boyuna: int, sira_yapisi: int = 2) -> List[Tuple[int, int]]:
    """
    Yan yana oturmamayı olabildiğince azaltmak için sütun gezişini sıra yapısına göre ayarlarız:
    - 2'li: önce tek sütunlar (1,3,5,...) sonra çift sütunlar (2,4,6,...)
    - 3'lü: 1,4,7,... → 2,5,8,... → 3,6,9,...
    """
    if enine <= 0 or boyuna <= 0:
        return []
    sira_yapisi = 3 if int(sira_yapisi or 0) == 3 else 2

    if sira_yapisi == 2:
        tek_sutunlar = [c for c in range(1, enine + 1) if c % 2 == 1]
        cift_sutunlar = [c for c in range(1, enine + 1) if c % 2 == 0]
        sutun_sirasi = tek_sutunlar + cift_sutunlar
    else:
        g1 = list(range(1, enine + 1, 3))
        g2 = list(range(2, enine + 1, 3))
        g3 = list(range(3, enine + 1, 3))
        sutun_sirasi = g1 + g2 + g3

    koltuklar: List[Tuple[int, int]] = []
    for sira in range(1, boyuna + 1):
        for sut in sutun_sirasi:
            koltuklar.append((sira, sut))
    return koltuklar

def atama_yap(ogrenciler: List[Dict], derslikler: List[Dict]):
    """
    Parametreler
    ------------
    ogrenciler: [{'id', 'ogr_no', 'adsoyad'}]
    derslikler: [{'id','derslik_kodu','enine','boyuna','kapasite','sira_yapisi'}]
                 -> aynı sınava atanmış derslikler

    Dönüş
    -----
    atamalar: List[Dict]
        [{'ogrenci_id', 'derslik_id', 'sira_no', 'sutun_no'}]
    uyarilar: List[str]
    """
    uyarilar: List[str] = []

    # Toplam kapasite kontrolü
    toplam_kapasite = sum(max(0, int(dl.get("kapasite") or 0)) for dl in derslikler)
    if toplam_kapasite < len(ogrenciler):
        uyarilar.append(
            f"Kapasite yetersiz: {len(ogrenciler)} öğrenci için toplam {toplam_kapasite} koltuk var."
        )

    # Derslikleri kapasiteye göre sırala (büyükten küçüğe)
    derslikler = sorted(derslikler, key=lambda d: int(d.get("kapasite") or 0), reverse=True)

    # Her derslik için koltuk üret
    derslik_koltuklari: Dict[int, List[Tuple[int, int]]] = {}
    for dl in derslikler:
        enine = int(dl.get("enine") or 0)
        boyuna = int(dl.get("boyuna") or 0)
        sira_yapisi = int(dl.get("sira_yapisi") or 2)
        derslik_koltuklari[dl["id"]] = _koltuk_listesi(enine, boyuna, sira_yapisi=sira_yapisi)

    # Öğrencileri round-robin mantığıyla dersliklere sırayla dağıt
    atamalar: List[Dict] = []
    ogrenci_index = 0
    derslik_index = 0
    ogrenci_sayisi = len(ogrenciler)

    if ogrenci_sayisi == 0:
        return [], ["Bu sınav için öğrenci bulunamadı."]

    # Her dersliğin kaç koltuğunun dolduğunu takip et
    doluluk: Dict[int, int] = {dl["id"]: 0 for dl in derslikler}

    while ogrenci_index < ogrenci_sayisi and derslikler:
        dl = derslikler[derslik_index % len(derslikler)]
        dl_id = dl["id"]
        koltuklar = derslik_koltuklari.get(dl_id, [])
        dolu = doluluk[dl_id]

        if dolu < len(koltuklar):
            ogr = ogrenciler[ogrenci_index]
            sira_no, sutun_no = koltuklar[dolu]
            atamalar.append({
                "ogrenci_id": ogr["id"],
                "derslik_id": dl_id,
                "sira_no": sira_no,
                "sutun_no": sutun_no
            })
            doluluk[dl_id] += 1
            ogrenci_index += 1
        else:
            # Derslik dolmuş, listeden çıkar
            derslikler.pop(derslik_index % len(derslikler))
            continue

        derslik_index += 1

    # Eğer hala öğrenci kaldıysa uyarı ver
    if ogrenci_index < ogrenci_sayisi:
        kalan = ogrenci_sayisi - ogrenci_index
        uyarilar.append(f"{kalan} öğrenci yerleştirilemedi (kapasite dolu).")

    return atamalar, uyarilar
