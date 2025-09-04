# ocr_reader.py (No Change Needed)

import os
from google.cloud import vision

from dotenv import load_dotenv
load_dotenv() 

NAMA_FILE_KREDENSIAL = os.environ.get("NAMA_FILE_KREDENSIAL")

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = NAMA_FILE_KREDENSIAL

def baca_struk(image_bytes: bytes):
    """Membaca teks dari data bytes gambar menggunakan Google Vision API."""

    print(f"🔍 Membaca gambar dari memori...")
    client = vision.ImageAnnotatorClient()
    
    # Langsung gunakan bytes dari argumen
    image = vision.Image(content=image_bytes)
    
    response = client.text_detection(image=image)
    if response.error.message:
        # Tambahkan detail error dari Google ke pesan exception
        raise Exception(f'{response.error.message}\nError dari Google Vision API.')
    
    detected_text = response.full_text_annotation.text
    print("✅ Gambar berhasil dibaca dari memori!")
    return detected_text


if __name__ == "__main__":
    # Bagian testing ini perlu diubah jika ingin dijalankan lagi
    # Karena sekarang butuh data bytes, bukan path
    print("Untuk testing, jalankan app.py dan kirim gambar via WhatsApp.")
    
    # Contoh cara testing baru:
    # file_name = "contoh-struk.jpg"
    # file_gambar_tes = os.path.join(os.path.dirname(__file__), "resource", file_name)
    # with open(file_gambar_tes, 'rb') as f:
    #     image_data_test = f.read()
    #     hasil_teks = baca_struk(image_data_test)
    #     print(hasil_teks)
