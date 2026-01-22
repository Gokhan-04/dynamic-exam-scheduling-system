# veritabani.py
import sqlite3
from pathlib import Path

VERITABANI_YOLU = Path(__file__).parent / "sinav_sistemi.db"

TABLO_YAPISI = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bolumler(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ad TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS kullanicilar(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  eposta TEXT UNIQUE NOT NULL,
  sifre_hash BLOB NOT NULL,
  rol TEXT NOT NULL CHECK(rol IN('admin','koordinator')),
  bolum_id INTEGER,
  FOREIGN KEY(bolum_id) REFERENCES bolumler(id)
);

CREATE TABLE IF NOT EXISTS derslikler(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bolum_id INTEGER NOT NULL,
  derslik_kodu TEXT NOT NULL,
  derslik_adi  TEXT NOT NULL,
  kapasite     INTEGER NOT NULL,
  enine        INTEGER NOT NULL,
  boyuna       INTEGER NOT NULL,
  sira_yapisi  INTEGER NOT NULL,
  FOREIGN KEY(bolum_id) REFERENCES bolumler(id),
  UNIQUE(bolum_id, derslik_kodu)
);

CREATE TABLE IF NOT EXISTS dersler(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bolum_id INTEGER NOT NULL,
  kod TEXT NOT NULL,
  ad  TEXT NOT NULL,
  hoca TEXT,
  sinif INTEGER,
  tur   TEXT,
  FOREIGN KEY(bolum_id) REFERENCES bolumler(id),
  UNIQUE(bolum_id, kod)
);

CREATE TABLE IF NOT EXISTS ogrenciler(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bolum_id INTEGER NOT NULL,
  ogr_no   TEXT NOT NULL,
  adsoyad  TEXT NOT NULL,
  sinif    INTEGER,
  FOREIGN KEY(bolum_id) REFERENCES bolumler(id),
  UNIQUE(bolum_id, ogr_no)
);

CREATE TABLE IF NOT EXISTS ogrenci_ders(
  ogrenci_id INTEGER NOT NULL,
  ders_id    INTEGER NOT NULL,
  PRIMARY KEY(ogrenci_id, ders_id),
  FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE,
  FOREIGN KEY(ders_id)    REFERENCES dersler(id)    ON DELETE CASCADE
);

-- Otomatik program
CREATE TABLE IF NOT EXISTS sinav_programi(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bolum_id   INTEGER NOT NULL,
  ders_id    INTEGER NOT NULL,
  sinav_turu TEXT NOT NULL,
  baslangic  TEXT NOT NULL, -- ISO 8601
  bitis      TEXT NOT NULL, -- ISO 8601
  sure_dk    INTEGER NOT NULL DEFAULT 90,
  bekleme_dk INTEGER NOT NULL DEFAULT 15,
  FOREIGN KEY(bolum_id) REFERENCES bolumler(id),
  FOREIGN KEY(ders_id)  REFERENCES dersler(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_sp_bolum_ders_tur
ON sinav_programi(bolum_id, ders_id, sinav_turu);

CREATE TABLE IF NOT EXISTS sinav_programi_derslik(
  sinav_id   INTEGER NOT NULL,
  derslik_id INTEGER NOT NULL,
  PRIMARY KEY(sinav_id, derslik_id),
  FOREIGN KEY(sinav_id)  REFERENCES sinav_programi(id) ON DELETE CASCADE,
  FOREIGN KEY(derslik_id) REFERENCES derslikler(id)
);

-- Oturma planı
CREATE TABLE IF NOT EXISTS oturma_plani(
  sinav_id INTEGER NOT NULL,
  ogrenci_id INTEGER NOT NULL,
  derslik_id INTEGER NOT NULL,
  sira_no INTEGER NOT NULL,
  sutun_no INTEGER NOT NULL,
  PRIMARY KEY(sinav_id, ogrenci_id),
  FOREIGN KEY(sinav_id) REFERENCES sinav_programi(id) ON DELETE CASCADE,
  FOREIGN KEY(ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE,
  FOREIGN KEY(derslik_id) REFERENCES derslikler(id)
);
"""

def baglanti():
    vt = sqlite3.connect(VERITABANI_YOLU)
    vt.row_factory = sqlite3.Row
    return vt

def _migrate(vt: sqlite3.Connection):
    # Güvenli göç: eksik sütunları ekle
    cur = vt.execute("PRAGMA table_info(sinav_programi)")
    cols = {r["name"] for r in cur.fetchall()}
    if "sure_dk" not in cols:
        vt.execute("ALTER TABLE sinav_programi ADD COLUMN sure_dk INTEGER NOT NULL DEFAULT 90")
    if "bekleme_dk" not in cols:
        vt.execute("ALTER TABLE sinav_programi ADD COLUMN bekleme_dk INTEGER NOT NULL DEFAULT 15")
    # Unique index
    vt.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_sp_bolum_ders_tur
        ON sinav_programi(bolum_id, ders_id, sinav_turu)
    """)

def veritabani_baslat():
    with baglanti() as vt:
        vt.executescript(TABLO_YAPISI)
        _migrate(vt)

def varsayilan_veri_yukle(admin_sifre_hash: bytes):
    bolumler = [
        "Bilgisayar Mühendisliği",
        "Yazılım Mühendisliği",
        "Elektrik Mühendisliği",
        "Elektronik Mühendisliği",
        "İnşaat Mühendisliği",
    ]
    with baglanti() as vt:
        for b in bolumler:
            vt.execute("INSERT OR IGNORE INTO bolumler(ad) VALUES (?)", (b,))
        vt.execute(
            """INSERT OR IGNORE INTO kullanicilar(eposta,sifre_hash,rol,bolum_id)
               VALUES(?, ?, 'admin', NULL)""",
            ("admin@uni.edu", admin_sifre_hash),
        )
