# services/hybrid_parser.py (Upgraded)
import re
import os
import json
import google.generativeai as genai

# --- Bagian Konfigurasi AI ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY belum diset di .env")
genai.configure(api_key=GOOGLE_API_KEY)
vision_model = genai.GenerativeModel('gemini-1.5-flash')

# --- LAPIS 1: SI CEPAT (REGEX PRESISI TINGGI) ---
def _bersihkan_nominal(s: str) -> str:
    s = s.strip()
    last_comma = s.rfind(',')
    last_dot = s.rfind('.')
    if last_comma > last_dot:
        main_part = s.split(',')[0]
        return re.sub(r'[^0-9]', '', main_part)
    elif last_dot > last_comma:
        main_part = s.split('.')[0]
        return re.sub(r'[^0-9]', '', main_part)
    else:
        return re.sub(r'[^0-9]', '', s)

def _parse_with_regex(text: str) -> dict | None:
    # Fungsi ini tidak diubah, tetap fokus pada kecepatan
    text_lower = text.lower()
    if "m-transfer" in text_lower and "berhasil" in text_lower:
        try:
            penerima_match = re.search(r"\n([A-Z\s]+)\nRp", text)
            penerima = penerima_match.group(1).strip()
            jumlah_match = re.search(r"Rp[\.\s]*([\d,]+\.\d{2})", text)
            if not jumlah_match:
                jumlah_match = re.search(r"Rp[\.\s]*([\d,]+)", text)
            jumlah = _bersihkan_nominal(jumlah_match.group(1))
            if jumlah != "0":
                print("✅ Terdeteksi oleh Regex Cepat: BCA Legacy")
                return {"jumlah": jumlah, "penerima": penerima, "tipe": "Transfer BCA"}
        except Exception:
            pass

    if "transaksi berhasil" in text_lower and "nominal" in text_lower:
        try:
            penerima_match = re.search(r"\n([A-Z\s]{4,})\n\s*(?:BCA|No\. Rek)", text)
            penerima = penerima_match.group(1).strip()
            jumlah_match = re.search(r"Nominal\s*\n\s*Rp\s*([\d.,]+)", text, re.IGNORECASE)
            jumlah = _bersihkan_nominal(jumlah_match.group(1))
            if jumlah != "0":
                print("✅ Terdeteksi oleh Regex Cepat: BLU")
                return {"jumlah": jumlah, "penerima": penerima, "tipe": "Transfer BLU"}
        except Exception:
            pass

    return None

# --- LAPIS 2: SI PINTAR (AI VISION) ---
def _parse_with_vision_ai(image_bytes: bytes) -> dict | None:
    """Menganalisis gambar langsung menggunakan AI Vision."""
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
        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        print(f"✅ AI Vision berhasil menganalisis. Respon: {cleaned_response}")
        parsed_data = json.loads(cleaned_response)
        if parsed_data and parsed_data.get("jumlah") and parsed_data.get("penerima"):
            return parsed_data
        return None
    except Exception as e:
        print(f"❌ Gagal saat memanggil AI Vision: {e}")
        return None

# --- Fungsi Utama (Orkestrator) ---
def parse_receipt(text_ocr: str, image_bytes: bytes, user_caption: str = "") -> dict | None:
    """
    Orkestrator utama yang menjalankan strategi benteng 3 lapis.
    BARU: Menerima 'user_caption' untuk prioritas catatan.
    """
    data = _parse_with_regex(text_ocr)
    if not data:
        data = _parse_with_vision_ai(image_bytes)
    
    if data:
        if user_caption:
            data['catatan'] = user_caption
        elif 'catatan' not in data:
            data['catatan'] = None
        return data
        
    print("❌ Semua metode parsing gagal.")
    return None