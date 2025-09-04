
import re
import os
import json
import google.generativeai as genai

# --- Bagian Konfigurasi AI ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY belum diset di .env")
genai.configure(api_key=GOOGLE_API_KEY)
vision_model = genai.GenerativeModel('gemini-2.5-flash')


# =========================
# UTIL: NORMALISASI NOMINAL
# =========================
def _normalize_amount_id(s: str) -> str:
    """
    Normalisasi angka uang ke string integer rupiah.
    Contoh:
      "48.000,00" -> "48000"
      "10,000.00" -> "10000"
      "1.000.000" -> "1000000"
      "10000.00"  -> "10000"
      "10000"     -> "10000"
    """
    if s is None:
        return "0"
    s = str(s).strip()
    # Sisakan hanya digit dan pemisah
    s2 = re.sub(r"[^0-9\.,]", "", s)
    if not s2:
        return "0"

    # Jika ada titik & koma sekaligus -> pemisah desimal adalah yang paling kanan
    if "." in s2 and "," in s2:
        if s2.rfind(",") > s2.rfind("."):
            int_part = s2.split(",")[0]
        else:
            int_part = s2.split(".")[0]
        digits = re.sub(r"[^0-9]", "", int_part)
        return re.sub(r"^0+(?=\d)", "", digits) or "0"

    # Hanya koma
    if "," in s2:
        # Skenario desimal "...,dd" (hanya 1 koma dan 2 digit di akhir)
        if re.search(r",\d{2}$", s2) and s2.count(",") == 1:
            int_part = s2.split(",")[0]
            digits = re.sub(r"[^0-9]", "", int_part)
            return re.sub(r"^0+(?=\d)", "", digits) or "0"
        # Lainnya diasumsikan pemisah ribuan
        digits = re.sub(r"[^0-9]", "", s2)
        return re.sub(r"^0+(?=\d)", "", digits) or "0"

    # Hanya titik
    if "." in s2:
        if re.search(r"\.\d{2}$", s2) and s2.count(".") == 1:
            int_part = s2.split(".")[0]
            digits = re.sub(r"[^0-9]", "", int_part)
            return re.sub(r"^0+(?=\d)", "", digits) or "0"
        digits = re.sub(r"[^0-9]", "", s2)
        return re.sub(r"^0+(?=\d)", "", digits) or "0"

    # Tanpa pemisah
    digits = re.sub(r"[^0-9]", "", s2)
    return re.sub(r"^0+(?=\d)", "", digits) or "0"


# =================
# HEURISTIK DETEKSI
# =================
def _is_blu(text_lower: str) -> bool:
    return any(k in text_lower for k in [
        "no. ref blu", "ref blu", "aplikasi blu", "blu by bca digital", "\nblu", " blu ",
        "tipe transaksi", "kategori", "qris"
    ]) or ("transaksi berhasil" in text_lower and "qris" in text_lower)


def _is_bca_legacy(text_lower: str) -> bool:
    return "m-transfer" in text_lower and "berhasil" in text_lower


def _is_struk_belanja(text_lower: str) -> bool:
    return any(k in text_lower for k in [
        "subtotal", "sub total", "pajak", "ppn", "kembalian", "kasir", "no trx", "member", "dine in"
    ])


# ======================
# LAPIS 1: REGEX CEPAT
# ======================
def _parse_blu(text: str) -> dict | None:
    text_lower = text.lower()
    if not _is_blu(text_lower) and "transfer successful" not in text_lower:
        return None

    # Ambil nominal (Nominal/Total Rp ..., atau format IDR ...)
    m_amount = re.search(r"(?:Nominal|Total)\s*(?:\n|:)\s*Rp\s*([\d\.,]+)", text, re.IGNORECASE)
    if not m_amount:
        m_amount = re.search(r"\bIDR\s*([\d\.,]+)", text, re.IGNORECASE)
    if not m_amount:
        return None
    jumlah = _normalize_amount_id(m_amount.group(1))

    # Coba ambil penerima dari baris setelah nominal
    penerima = ""
    tail = text[m_amount.end():]
    for ln in [ln.strip() for ln in tail.splitlines()]:
        if not ln:
            continue
        if re.search(r"^(TANGERANG|TIPE TRANSAKSI|KATEGORI|NO\.?\s*REF|BENEFICIARY|IDR|BCA\s*-|Transfer Method)", ln, re.IGNORECASE):
            continue
        if re.search(r"^Rp\b", ln, re.IGNORECASE):
            continue
        penerima = ln
        break

    # Bukti transfer BCA versi Inggris: "Beneficiary Name"
    if not penerima:
        m_benef = re.search(r"Beneficiary Name\s*\n\s*([^\n]+)", text, re.IGNORECASE)
        if m_benef:
            penerima = m_benef.group(1).strip()

    return {"jumlah": jumlah, "penerima": penerima, "tipe": "Transfer BLU"}


def _parse_bca_legacy(text: str) -> dict | None:
    text_lower = text.lower()
    if not _is_bca_legacy(text_lower):
        return None
    try:
        penerima_match = re.search(r"\n([A-Z\s]+)\nRp", text)
        penerima = penerima_match.group(1).strip() if penerima_match else ""
        jumlah_match = re.search(r"Rp[\.\s]*([\d\.,]+)", text)
        jumlah = _normalize_amount_id(jumlah_match.group(1)) if jumlah_match else "0"
        if jumlah != "0":
            return {"jumlah": jumlah, "penerima": penerima, "tipe": "Transfer BCA"}
    except Exception:
        pass
    return None

def _extract_company_name(text: str) -> str | None:
    """
    Cari nama perusahaan (PT/CV) dari teks OCR.
    Ambil baris lengkap pertama yang mengandung PT atau CV.
    """
    for ln in text.splitlines():
        if re.match(r"^\s*(PT|CV)\b", ln.strip(), re.IGNORECASE):
            return ln.strip()
    return None

def _parse_struk(text: str) -> dict | None:
    text_lower = text.lower()
    if not _is_struk_belanja(text_lower):
        return None

    # Ambil jumlah total
    m_amount = (
        re.search(r"\bTotal(?: Belanja)?(?:\s*[:\-]?\s*Rp?)?\s*\n\s*([\d\.,]+)", text, re.IGNORECASE)
        or re.search(r"\bGrand\s*Total(?:\s*[:\-]?\s*Rp?)?\s*\n?\s*([\d\.,]+)", text, re.IGNORECASE)
    )
    if not m_amount:
        return None
    jumlah = _normalize_amount_id(m_amount.group(1))

    # Cari nama perusahaan
    penerima = _extract_company_name(text)
    if not penerima:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            first = lines[0]
            if re.search(r"(beepos|pos|npwp|alamat|jl\.|jl\s|jalan)", first, re.IGNORECASE) and len(lines) > 1:
                penerima = lines[1]
            else:
                penerima = first

    return {"jumlah": jumlah, "penerima": penerima, "tipe": "Struk Belanja"}


def _parse_with_regex(text: str) -> dict | None:
    """
    Orkestrator regex: coba BLU -> BCA Legacy -> Struk
    """
    return _parse_blu(text) or _parse_bca_legacy(text) or _parse_struk(text)


# ========================
# LAPIS 2: VISION (GEMINI)
# ========================
def _parse_with_vision_ai(image_bytes: bytes, fallback_text: str = "") -> dict | None:
    """
    Analisis gambar via AI Vision.
    - Tetap dinormalisasi dengan _normalize_amount_id.
    - Jika 'tipe' masih 'Lainnya', paksa klasifikasi dengan heuristic dari fallback_text.
    """
    print("🧠 Regex gagal, eskalasi ke AI Vision...")
    image_part = {"mime_type": "image/jpeg", "data": image_bytes}
    prompt = """
    Analisis gambar struk atau bukti transfer ini. Ekstrak informasi berikut secara akurat:
    1. `jumlah`: Total akhir pembayaran atau jumlah transfer. Jangan ambil subtotal.
    2. `penerima`: Nama toko, merchant, atau penerima transfer.
    3. `tipe`: Klasifikasikan sebagai "Struk Belanja", "Transfer BCA", "Transfer BLU", atau "Lainnya".
    4. `catatan`: Deskripsi, berita, atau catatan transfer jika ada. Jika tidak ada, kembalikan null.

    Berikan jawaban HANYA dalam format JSON yang valid. Jika tidak yakin, kembalikan null untuk field tersebut.
    Contoh: {"jumlah": "191475", "penerima": "Cafe Bee", "tipe": "Struk Belanja", "catatan": "Bayar kopi"}
    """
    try:
        response = vision_model.generate_content([prompt, image_part])
        cleaned = response.text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)

        if not isinstance(parsed, dict):
            return None

        # Normalisasi jumlah dari AI (sering keliru menjadi 4800000)
        if parsed.get("jumlah") is not None:
            parsed["jumlah"] = _normalize_amount_id(parsed["jumlah"])
            
        # Perbaiki tipe jika AI ragu
        t = (parsed.get("tipe") or "").lower()
        tl = (fallback_text or "").lower()
        if t not in {"struk belanja", "transfer bca", "transfer blu"}:
            if _is_blu(tl):
                parsed["tipe"] = "Transfer BLU"
            elif _is_bca_legacy(tl):
                parsed["tipe"] = "Transfer BCA"
            elif _is_struk_belanja(tl):
                parsed["tipe"] = "Struk Belanja"
            else:
                parsed["tipe"] = "Lainnya"
                
        company = _extract_company_name(fallback_text)
        if company:
            parsed["penerima"] = company

        return parsed if parsed.get("jumlah") and parsed.get("penerima") is not None else parsed
    except Exception as e:
        print(f"❌ Gagal saat memanggil AI Vision: {e}")
        return None


# ================
# ORKESTRATOR UTAMA
# ================
def parse_receipt(text_ocr: str, image_bytes: bytes, user_caption: str = "") -> dict | None:
    """
    Benteng 3 lapis: Regex cepat -> AI Vision -> Fallback heuristik.
    Sekarang lebih kebal terhadap salah-baca 48.000,00 menjadi 4800000,
    dan lebih jeli mengenali transaksi blu.
    """
    data = _parse_with_regex(text_ocr or "")

    if not data:
        data = _parse_with_vision_ai(image_bytes, fallback_text=text_ocr or "")

    if data:
        # Catatan prioritas dari user
        if user_caption:
            data["catatan"] = user_caption
        elif "catatan" not in data:
            data["catatan"] = None
        # Pastikan jumlah selalu dinormalisasi
        if data.get("jumlah") is not None:
            data["jumlah"] = _normalize_amount_id(data["jumlah"])
        # Perkuat tipe untuk blu jika terdeteksi dari OCR
        if _is_blu((text_ocr or "").lower()):
            data["tipe"] = "Transfer BLU"
        return data

    print("❌ Semua metode parsing gagal.")
    return None
