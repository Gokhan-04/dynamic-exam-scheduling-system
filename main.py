# main.py
import tkinter as tk
import bcrypt
from veritabani import veritabani_baslat, varsayilan_veri_yukle, VERITABANI_YOLU
from arayuz.giris_penceresi import GirisPenceresi
from arayuz.ana_pencere import AnaPencere
import os

def giris_sonrasi_cb(kullanici):
    AnaPencere(kullanici, master=root)

if __name__ == "__main__":
    veritabani_baslat()

    if not os.path.exists(VERITABANI_YOLU) or os.path.getsize(VERITABANI_YOLU) == 0:
        admin_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
        varsayilan_veri_yukle(admin_hash)
        print("Varsayılan admin: admin@uni.edu / admin123")

    root = tk.Tk(); root.withdraw()
    GirisPenceresi(root, giris_sonrasi_cb)
    root.mainloop()
