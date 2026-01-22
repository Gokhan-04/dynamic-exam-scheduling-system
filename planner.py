# planner.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Any, Tuple, Iterable, Union, Optional, Set


# ------------------------------
# Yardımcılar
# ------------------------------

def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """[a_start, a_end) ile [b_start, b_end) aralığı kesişiyor mu?"""
    return not (a_end <= b_start or b_end <= a_start)


def _getv(row: Any, key: str, default: Any = None) -> Any:
    """
    sqlite3.Row | dict için güvenli okuyucu:
    - dict ise .get
    - sqlite3.Row ise [] ile okur; yoksa default
    """
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        if hasattr(row, "keys") and key in row.keys():
            return row[key]
    except Exception:
        pass
    return default


_TR_TO_WEEKDAY = {
    "pazartesi": 0, "salı": 1, "sali": 1, "çarşamba": 2, "carsamba": 2,
    "perşembe": 3, "persembe": 3, "cuma": 4, "cumartesi": 5, "pazar": 6,
}

def _normalize_gun_disi(v: Optional[Iterable[Any]]) -> Set[int]:
    """'Cumartesi','Pazar' ya da 5,6 gibi değerleri weekday int setine çevirir (Pzt=0 … Paz=6)."""
    out: Set[int] = set()
    if not v:
        return out
    for it in v:
        if isinstance(it, int):
            if 0 <= it <= 6:
                out.add(it)
            continue
        s = str(it).strip().lower()
        if s.isdigit():
            n = int(s)
            if 0 <= n <= 6:
                out.add(n)
                continue
        n = _TR_TO_WEEKDAY.get(s)
        if n is not None:
            out.add(n)
    return out


def _to_time(x: Any) -> Optional[time]:
    """'09:00' gibi string → time; zaten time ise aynen döner."""
    if isinstance(x, time):
        return x
    if x is None:
        return None
    s = str(x).strip()
    try:
        hh, mm = s.split(":")
        return time(int(hh), int(mm))
    except Exception:
        return None


def _normalize_ders_sureleri(v: Any) -> Dict[int, int]:
    """
    ders bazlı süreleri normalize eder.
    Kabul edilen formatlar:
      - {ders_id: sure_dk, ...}
      - [{"ders_id":1,"sure":90}, ...]  / [{"id":1,"dk":90}, ...]
      - [(1,90), (2,120)]
    """
    out: Dict[int, int] = {}
    if not v:
        return out
    if isinstance(v, dict):
        for k, val in v.items():
            try:
                out[int(k)] = int(val)
            except Exception:
                pass
        return out
    if isinstance(v, (list, tuple, set)):
        for it in v:
            if isinstance(it, (list, tuple)) and len(it) >= 2:
                try:
                    out[int(it[0])] = int(it[1])
                except Exception:
                    pass
                continue
            if isinstance(it, dict):
                cid = it.get("ders_id", it.get("id"))
                dk = it.get("sure", it.get("dk"))
                try:
                    if cid is not None and dk is not None:
                        out[int(cid)] = int(dk)
                except Exception:
                    pass
    return out


# ------------------------------
# Planlama kısıt veri sınıfı (geriye dönük uyumlu)
# ------------------------------

@dataclass
class PlanKisit:
    """
    UI'nin gönderebileceği tüm alanlar (geriye dönük isimlerle birlikte):

      tarih_bas / tarih_bit: planlama aralığı (date)
      slot_saatleri:          list[time | 'HH:MM']
      gunluk_slot_saatleri:   (eski isim) slot_saatleri ile eşdeğer
      varsayilan_sure_dk:     sınav süresi (dk)
      default_sure / sure_dk / vars_sure_dk: varsayilan_sure_dk için takma adlar
      bekleme_dk:             öğrencinin ardışık sınavları arası asgari boşluk (dk)
      bekleme / bekleme_suresi_dk: bekleme_dk takma adları
      sinav_turu:             'vize' / 'final' vb.
      tek_seans:              True → aynı anda yalnızca 1 sınav (paralel yasak)
      paralel_yasak / tek_oturum: tek_seans için takma adlar
      dahil_ders_ids:         sadece bu ders id'leri planlansın
      gun_disi:               planlamadan hariç günler
      ders_istisna_sure:      {ders_id: dakika} (alias: ders_sureleri, ders_ozel_sureleri, per_ders_sure)
    """
    tarih_bas: date
    tarih_bit: date

    # İki isim birden desteklenir:
    slot_saatleri: Optional[List[Union[time, str]]] = None
    gunluk_slot_saatleri: Optional[List[Union[time, str]]] = None

    # Süre ve bekleme
    varsayilan_sure_dk: Optional[int] = None
    default_sure: Optional[int] = None
    sure_dk: Optional[int] = None
    vars_sure_dk: Optional[int] = None

    bekleme_dk: Optional[int] = None
    bekleme: Optional[int] = None
    bekleme_suresi_dk: Optional[int] = None

    sinav_turu: str = "vize"

    tek_seans: Optional[bool] = None
    paralel_yasak: Optional[bool] = None
    tek_oturum: Optional[bool] = None

    dahil_ders_ids: Optional[List[int]] = None
    gun_disi: Optional[Iterable[Any]] = None

    # ders bazlı süreler
    ders_istisna_sure: Optional[Any] = None
    ders_sureleri: Optional[Any] = None
    ders_ozel_sureleri: Optional[Any] = None
    per_ders_sure: Optional[Any] = None

    # normalize edilmiş nihai liste (iç kullanım)
    _slotlar: List[time] = field(default_factory=list, init=False, repr=False)
    _ders_sure_map: Dict[int, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        # slotları topla (iki isimden birini kullanabilir)
        raw = self.slot_saatleri if self.slot_saatleri is not None else self.gunluk_slot_saatleri
        raw = raw or []
        out: List[time] = []
        for s in raw:
            t = _to_time(s)
            if t:
                out.append(t)
        self._slotlar = out

        # süre aliasları
        sure_kaynaklar = [self.varsayilan_sure_dk, self.default_sure, self.sure_dk, self.vars_sure_dk]
        self.varsayilan_sure_dk = next((int(x) for x in sure_kaynaklar if x is not None), 75)

        # bekleme aliasları
        bek_kaynaklar = [self.bekleme_dk, self.bekleme, self.bekleme_suresi_dk]
        self.bekleme_dk = next((int(x) for x in bek_kaynaklar if x is not None), 0)

        # tek seans aliasları
        ts_kaynaklar = [self.tek_seans, self.paralel_yasak, self.tek_oturum]
        self.tek_seans = bool(next((x for x in ts_kaynaklar if x is not None), False))

        # ders-bazlı süre aliasları normalize
        ds = (self.ders_istisna_sure or self.ders_sureleri or
              self.ders_ozel_sureleri or self.per_ders_sure)
        self._ders_sure_map = _normalize_ders_sureleri(ds)


# ------------------------------
# Ana planlayıcı
# ------------------------------

def planla(kisitlar: Union[PlanKisit, Dict[str, Any]],
           dersler: List[Dict[str, Any]],
           derslikler: List[Any]) -> Tuple[List[Dict[str, Any]], List[str], bool]:
    """
    Kurallı yerleştirici:
      - Aynı öğrencinin aynı anda iki sınavı olmaz.
      - Aynı derslik aynı saat aralığında ikinci kez kullanılmaz.
      - Derslik kapasitesi yetmiyorsa uygun başka derslik aranır; bulunamazsa uyarı üretir.
      - 'tek_seans=True' ise aynı anda yalnızca 1 ders (paralel yasak).
      - 'dahil_ders_ids' verilirse sadece bu ID’lerdeki dersler planlanır.
      - 'gun_disi' verilirse bu günlerde slot denenmez.
      - 'ders_istisna_sure' verilirse ders bazlı süre uygulanır.
    Dönenler:
      - yerlestirmeler: [{ders_id, baslangic, bitis, derslik_ids}]
      - uyarilar: [str, ...]
      - fatal: bool
    """
    # PlanKisit -> dict
    if isinstance(kisitlar, PlanKisit):
        k = {
            "tarih_bas": kisitlar.tarih_bas,
            "tarih_bit": kisitlar.tarih_bit,
            "slot_saatleri": kisitlar._slotlar,
            "varsayilan_sure_dk": kisitlar.varsayilan_sure_dk,
            "bekleme_dk": kisitlar.bekleme_dk,
            "sinav_turu": kisitlar.sinav_turu,
            "tek_seans": kisitlar.tek_seans,
            "dahil_ders_ids": kisitlar.dahil_ders_ids,
            "gun_disi": kisitlar.gun_disi,
            "ders_istisna_sure": kisitlar._ders_sure_map,
        }
    else:
        # dict ise aliasları eşle
        k = dict(kisitlar or {})
        if "slot_saatleri" not in k and "gunluk_slot_saatleri" in k:
            k["slot_saatleri"] = k.get("gunluk_slot_saatleri") or []

        # süre aliasları
        if "varsayilan_sure_dk" not in k:
            for alias in ("default_sure", "sure_dk", "vars_sure_dk"):
                if alias in k and k[alias] is not None:
                    k["varsayilan_sure_dk"] = int(k[alias])
                    break

        # bekleme aliasları
        if "bekleme_dk" not in k:
            for alias in ("bekleme", "bekleme_suresi_dk"):
                if alias in k and k[alias] is not None:
                    k["bekleme_dk"] = int(k[alias])
                    break

        # tek seans aliasları
        if "tek_seans" not in k:
            for alias in ("paralel_yasak", "tek_oturum"):
                if alias in k and k[alias] is not None:
                    k["tek_seans"] = bool(k[alias])
                    break

        # ders-bazlı süre aliasları
        if "ders_istisna_sure" not in k:
            for alias in ("ders_sureleri", "ders_ozel_sureleri", "per_ders_sure"):
                if alias in k and k[alias]:
                    k["ders_istisna_sure"] = _normalize_ders_sureleri(k[alias])
                    break
        else:
            k["ders_istisna_sure"] = _normalize_ders_sureleri(k["ders_istisna_sure"])

    uyarilar: List[str] = []
    yerlestirmeler: List[Dict[str, Any]] = []

    # slot saatlerini normalize et (string gelebilir)
    raw_slots = k.get("slot_saatleri", [])
    slot_saatleri: List[time] = []
    for s in raw_slots:
        t = _to_time(s)
        if t:
            slot_saatleri.append(t)

    tarih_bas: date = k["tarih_bas"]
    tarih_bit: date = k["tarih_bit"]
    default_sure_dk: int = int(k.get("varsayilan_sure_dk", 75) or 75)
    bekleme_dk: int = int(k.get("bekleme_dk", 0) or 0)  # şu an bilgi amaçlı
    tek_seans: bool = bool(k.get("tek_seans", False))
    dahil_ders_ids: Optional[List[int]] = k.get("dahil_ders_ids")
    gun_disi: Set[int] = _normalize_gun_disi(k.get("gun_disi"))
    ders_sure_map: Dict[int, int] = k.get("ders_istisna_sure") or {}

    # Sadece seçili dersler istenmişse filtrele
    if dahil_ders_ids:
        izinli = {int(i) for i in dahil_ders_ids}
        dersler = [d for d in dersler if int(d.get("id")) in izinli]

    # Zaman çizelgeleri
    derslik_zaman: Dict[int, List[Tuple[datetime, datetime]]] = {}
    ogr_zaman: Dict[int, List[Tuple[datetime, datetime]]] = {}

    def derslik_musait(derslik_id: int, bas: datetime, bit: datetime) -> bool:
        for (b0, b1) in derslik_zaman.get(derslik_id, []):
            if _overlaps(bas, bit, b0, b1):
                return False
        return True

    def ogrenciler_musait(ogr_ids: Iterable[int], bas: datetime, bit: datetime) -> bool:
        for oid in ogr_ids:
            for (b0, b1) in ogr_zaman.get(int(oid), []):
                if _overlaps(bas, bit, b0, b1):
                    return False
        return True

    # Büyükten küçüğe sırala (öğrenci sayısı fazla olan dersler önce yer bulsun)
    dersler_sirali = sorted(dersler, key=lambda d: int(d.get("ogr_say", 0)), reverse=True)
    # Derslikleri kapasiteye göre sırala
    derslikler_sirali = sorted(derslikler, key=lambda dl: int(_getv(dl, "kapasite", 0)), reverse=True)

    # --- EKLEME: derslik kullanım sayaçları (dengeli dağıtım için) ---
    kullanim_say: Dict[int, int] = {int(_getv(dl, "id")): 0 for dl in derslikler_sirali}
    # ---------------------------------------------------------------

    gun = tarih_bas
    while gun <= tarih_bit:
        # Hariç gün mü?
        if gun.weekday() in gun_disi:
            gun += timedelta(days=1)
            continue

        for slot in slot_saatleri:
            if not dersler_sirali:
                break

            # paralel yasak ise, o slotta tek ders planlayacağız
            max_ders_sayisi = 1 if tek_seans else len(dersler_sirali)

            # bu slottaki adaylar
            eklendi_bu_slot = 0
            for d in list(dersler_sirali):
                if eklendi_bu_slot >= max_ders_sayisi:
                    break

                # ders bazlı süre
                ders_id = int(d["id"])
                sure_dk = int(ders_sure_map.get(ders_id, default_sure_dk))

                bas = datetime.combine(gun, slot)
                bit = bas + timedelta(minutes=sure_dk)

                # öğrenciler uygun mu?
                if not ogrenciler_musait(d.get("ogr_ids") or [], bas, bit):
                    continue

                # --- GÜNCEL: Derslik seçimi (dengeli & küçük kapasite öncelikli) ---
                ogr_say = int(d.get("ogr_say") or 0)
                secilen_derslik_id = None

                uygunlar: List[Any] = []
                for dl in derslikler_sirali:
                    dl_id = int(_getv(dl, "id"))
                    kap = int(_getv(dl, "kapasite", 0))
                    if kap >= ogr_say and derslik_musait(dl_id, bas, bit):
                        uygunlar.append(dl)

                if uygunlar:
                    uygunlar.sort(
                        key=lambda _dl: (
                            kullanim_say[int(_getv(_dl, "id"))],                 # daha az kullanılan önce
                            int(_getv(_dl, "kapasite", 10**9))                   # eşitse kapasitesi küçük olan önce
                        )
                    )
                    secilen = uygunlar[0]
                    secilen_derslik_id = int(_getv(secilen, "id"))
                # -------------------------------------------------------------------

                if secilen_derslik_id is None:
                    uyarilar.append(
                        f"Ders {d.get('kod','?')} için {gun} {slot.strftime('%H:%M')} saatinde uygun/kapasiteli derslik bulunamadı."
                    )
                    continue

                # Yerleştir
                yerlestirmeler.append({
                    "ders_id": ders_id,
                    "baslangic": bas,
                    "bitis": bit,
                    "derslik_ids": [secilen_derslik_id],
                })

                # Çizelgeleri güncelle
                derslik_zaman.setdefault(secilen_derslik_id, []).append((bas, bit))
                for oid in (d.get("ogr_ids") or []):
                    ogr_zaman.setdefault(int(oid), []).append((bas, bit))

                # --- EKLEME: kullanım sayısını artır ---
                kullanim_say[secilen_derslik_id] = kullanim_say.get(secilen_derslik_id, 0) + 1
                # --------------------------------------

                # listeden çıkar
                dersler_sirali.remove(d)
                eklendi_bu_slot += 1

                if tek_seans:
                    break  # bu slot dolu

        gun += timedelta(days=1)

    fatal = False
    return yerlestirmeler, uyarilar, fatal
