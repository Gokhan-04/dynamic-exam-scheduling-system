from tkinter import messagebox

def bilgi(metin:str): messagebox.showinfo("Bilgi", metin)
def uyari(metin:str): messagebox.showwarning("Uyarı", metin)
def hata(metin:str):  messagebox.showerror("Hata", metin)
def sor(metin:str)->bool: return messagebox.askyesno("Onay", metin)
