# tools/data_parser.py
import re

def klasifikasi_transaksi(teks: str) -> str:
    """
    Deteksi apakah teks hasil OCR adalah BCA, BLU, atau Struk Belanja
    """
    teks_lower = teks.lower()

    if "m-transfer" in teks_lower and "berhasil" in teks_lower and "bca" in teks_lower:
        return "BCA"

    if "transfer successful" in teks_lower and "blu" in teks_lower:
        return "BCA_BLU"

    if "transaksi berhasil" in teks_lower and "blu" in teks_lower:
        return "BLU"

    return "STRUK_BELANJA"


# -------------------- EKSTRAKTOR --------------------

def _ekstrak_bca(teks: str) -> dict | None:
    try:
        # Jumlah
        jumlah_match = re.search(r"Rp\.?\s*([\d.,]+)", teks, re.IGNORECASE)
        jumlah = re.sub(r"\D", "", jumlah_match.group(1)) if jumlah_match else "0"

        # Penerima
        penerima_match = re.search(r"\n([A-Z\s]+)\nRp", teks)
        penerima = penerima_match.group(1).strip() if penerima_match else "Tidak Ditemukan"

        return {"jumlah": jumlah, "penerima": penerima, "tipe": "BCA"}
    except Exception:
        return None


def _ekstrak_blu(teks: str) -> dict | None:
    try:
        # Jumlah
        jumlah_match = re.search(r"(?:Rp|IDR)\s*([\d.,]+)", teks, re.IGNORECASE)
        jumlah = re.sub(r"\D", "", jumlah_match.group(1)) if jumlah_match else "0"

        # Nama penerima
        penerima_match = re.search(r"Name\s*[:\-]?\s*([A-Z\s]+)", teks, re.IGNORECASE)
        if not penerima_match:
            penerima_match = re.search(r"(\b[A-Z][A-Z\s]{3,})\n", teks)
        penerima = penerima_match.group(1).strip() if penerima_match else "Tidak Ditemukan"

        return {"jumlah": jumlah, "penerima": penerima, "tipe": "BLU"}
    except Exception:
        return None


def parse_struk_belanja(teks: str) -> dict | None:
    try:
        total_match = re.search(r"(?:TOTAL|GRAND TOTAL|TOTAL BAYAR)\s*([\d.,]+)", teks, re.IGNORECASE)
        if total_match:
            jumlah = re.sub(r"\D", "", total_match.group(1))
        else:
            return None

        baris_pertama = teks.split("\n", 1)[0].strip()
        nama_toko = baris_pertama if 0 < len(baris_pertama) < 35 else "Struk Belanja"

        return {"jumlah": jumlah, "penerima": nama_toko, "tipe": "Belanja"}
    except Exception:
        return None


# -------------------- ROUTER --------------------
def ekstrak_info_transaksi(teks: str, tipe: str) -> dict | None:
    if tipe == "BCA":
        return _ekstrak_bca(teks)
    if tipe in ("BLU", "BCA_BLU"):
        return _ekstrak_blu(teks)
    if tipe == "STRUK_BELANJA":
        return parse_struk_belanja(teks)

    return None
