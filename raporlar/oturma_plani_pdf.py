# raporlar/oturma_plani_pdf.py
from __future__ import annotations
from typing import List, Dict
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# -------------------------------------------------------
# Yardımcı çizim fonksiyonları (satır sayısı korunur)
# -------------------------------------------------------

def _draw_grid(c: canvas.Canvas, x0: float, y0: float,
               enine: int, boyuna: int,
               hucre_w: float, hucre_h: float):
    # dış çerçeve
    c.rect(x0, y0, enine * hucre_w, boyuna * hucre_h, stroke=1, fill=0)
    # yatay çizgiler
    for r in range(1, boyuna):
        c.line(x0, y0 + r * hucre_h, x0 + enine * hucre_w, y0 + r * hucre_h)
    # dikey çizgiler
    for s in range(1, enine):
        c.line(x0 + s * hucre_w, y0, x0 + s * hucre_w, y0 + boyuna * hucre_h)

def _seat_label_pos(x0: float, y0: float, col: int, row: int,
                    hucre_w: float, hucre_h: float):
    # row: 1..boyuna (alttan yukarı), col: 1..enine (soldan sağa)
    cx = x0 + (col - 0.5) * hucre_w
    cy = y0 + (row - 0.5) * hucre_h
    return cx, cy

def esine(n: int) -> int:
    # küçük yardımcı: None/0 korumalı yazı için
    try:
        return int(n)
    except Exception:
        return 0

# -------------------------------------------------------
# Ana PDF yazıcı
# -------------------------------------------------------

def oturma_plani_pdf_yaz(
    dosya_yolu: str,
    sinav_baslik: str,
    tarih_saat: str,
    derslikler: List[Dict],
    atamalar: List[Dict]
):
    """
    derslikler: [{'id','derslik_kodu','enine','boyuna','kapasite'}, ...]
    atamalar: [{'ogrenci_id','adsoyad','ogr_no','derslik_kodu','derslik_id',
                'sira_no','sutun_no'}, ...]
    """
    c = canvas.Canvas(dosya_yolu, pagesize=A4)
    W, H = A4

    # PDF oluşmadı uyarısı yaşamamak için en az bir sayfa garantisi
    sayfa_sayildi = False

    for dl in derslikler:
        d_id = int(dl["id"])
        kod = str(dl.get("derslik_kodu", "—"))
        enine = int(dl.get("enine") or 0)
        boyuna = int(dl.get("boyuna") or 0)

        c.setFont("Helvetica-Bold", 14)
        c.drawString(20 * mm, H - 25 * mm, sinav_baslik)
        c.setFont("Helvetica", 11)
        c.drawString(20 * mm, H - 32 * mm, f"Tarih/Saat: {tarih_saat}")
        c.drawString(20 * mm, H - 38 * mm,
                     f"Derslik: {kod}  (Sütun: {esine(enine)}, Sıra: {esine(boyuna)})")

        # Grid boyutu – sayfaya sığdır
        margin_x = 20 * mm
        margin_y = 25 * mm
        usable_w = W - 2 * margin_x
        usable_h = H - 60 * mm - margin_y
        if enine <= 0 or boyuna <= 0:
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(20 * mm, H - 48 * mm,
                         "Uyarı: Geçersiz sınıf düzeni (enine/boyuna).")
            c.showPage()
            sayfa_sayildi = True
            continue

        hucre_w = usable_w / max(1, enine)
        hucre_h = usable_h / max(1, boyuna)
        hucre = min(hucre_w, hucre_h)
        grid_w = enine * hucre
        grid_h = boyuna * hucre
        x0 = (W - grid_w) / 2
        y0 = (H - 60 * mm - grid_h) / 2

        _draw_grid(c, x0, y0, enine, boyuna, hucre, hucre)

        # Bu derslikteki atamalar
        this = [a for a in atamalar if int(a["derslik_id"]) == d_id]
        c.setFont("Helvetica", 7.5)
        for a in this:
            row = int(a["sira_no"])
            col = int(a["sutun_no"])
            etiket = f"{a.get('ogr_no','')}"
            cx, cy = _seat_label_pos(x0, y0, col, row, hucre, hucre)
            c.drawCentredString(cx, cy - 2, etiket)

        # Öğrenci listesi (sağ alt)
        c.setFont("Helvetica", 9)
        c.drawString(20 * mm, 18 * mm, "Öğrenci Yerleşimleri:")
        ylist = 14 * mm
        c.setFont("Helvetica", 8)
        max_list = 50
        for i, a in enumerate(this[:max_list], start=1):
            c.drawString(
                20 * mm, ylist,
                f"{i:02d}) {a.get('ogr_no','')} - {a.get('adsoyad','')}  "
                f"(Sıra:{a['sira_no']}, Sütun:{a['sutun_no']})"
            )
            ylist -= 4.2 * mm
            if ylist < 10 * mm:
                break

        c.showPage()
        sayfa_sayildi = True

    # Derslik hiç yoksa yine de boş örnek sayfa — “PDF bozuk” hatasını önler
    if not sayfa_sayildi:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20 * mm, H - 25 * mm, sinav_baslik or "Oturma Planı")
        c.setFont("Helvetica", 11)
        c.drawString(20 * mm, H - 32 * mm, tarih_saat or "")
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(20 * mm, H - 48 * mm,
                     "Uyarı: Bu sınava ait derslik bulunamadı (PDF örnek sayfası).")
        c.showPage()

    c.save()

# --- GERİYE DÖNÜK UYUMLULUK ALIAS'I --------------------
def oturma_plani_pdf_kaydet(
    dosya_yolu: str,
    sinav_baslik: str,
    tarih_saat: str,
    derslikler: List[Dict],
    atamalar: List[Dict]
):
    """
    Eski UI 'oturma_plani_pdf_kaydet' adını import ediyor.
    Geriye dönük uyumluluk için 'oturma_plani_pdf_yaz' fonksiyonuna yönlendirir.
    Parametre isimleri birebir aynı tutuldu; kwargs/positional uyumlu.
    """
    return oturma_plani_pdf_yaz(
        dosya_yolu=dosya_yolu,
        sinav_baslik=sinav_baslik,
        tarih_saat=tarih_saat,
        derslikler=derslikler,
        atamalar=atamalar
    )
