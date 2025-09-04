# services/whatsapp_handler.py (Hybrid AI Upgrade)
import os
import requests
from PIL import Image
import io
import re

from .ocr_reader import baca_struk
from .data_parser import parse_receipt
from .sheets_writer import simpan_ke_sheets

# Folder resource
RESOURCE_DIR = os.path.join("tools", "resource")
os.makedirs(RESOURCE_DIR, exist_ok=True)


def handle_whatsapp_message(request, twilio_sid, twilio_token):
    """Logic penanganan pesan WhatsApp dengan Parser Hybrid (Regex + AI Vision)"""

    print("\n--- Pesan WhatsApp Baru Diterima ---")

    if request.form.get("NumMedia") != "0":
        gambar_url = request.form.get("MediaUrl0")

        try:
            # Download gambar dengan auth Twilio
            resp = requests.get(gambar_url, auth=(twilio_sid, twilio_token))
            if resp.status_code != 200:
                raise Exception(f"Twilio response {resp.status_code}: {resp.text}")

            print("✅ Gambar berhasil di-download ke memori.")
            image_data = resp.content

        except Exception as e:
            print(f"❌ Gagal download gambar: {e}")
            return "Waduh, gagal ngambil gambarnya nih. Coba kirim ulang ya."

        try:
            # --- Proses gambar ---
            print("🧺 Mencuci dan menyetrika data gambar...")
            try:
                image = Image.open(io.BytesIO(image_data))
            except Exception as pil_err:
                # Simpan file mentah untuk debug jika PIL gagal
                debug_path = os.path.join(RESOURCE_DIR, "debug_media.bin")
                with open(debug_path, "wb") as f:
                    f.write(image_data)
                raise Exception(
                    f"PIL tidak bisa mengenali gambar. File mentah disimpan di {debug_path}. Detail: {pil_err}"
                )

            # Konversi gambar ke format RGB yang lebih umum
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            # Simpan gambar yang sudah bersih ke dalam memori (bytes)
            output_bytes_io = io.BytesIO()
            image.save(output_bytes_io, format="JPEG")
            cleaned_image_data = output_bytes_io.getvalue()
            print("✨ Gambar sudah bersih dan siap diproses!")

            # 1. Baca teks dari gambar (tetap perlu untuk Lapis 1: Regex)
            teks_hasil_ocr = baca_struk(cleaned_image_data)
            
            # 2. Panggil Orkestrator Hybrid kita
            # Dia butuh teks mentah (buat regex) dan data gambar (buat AI vision)
            data_transaksi = parse_receipt(teks_hasil_ocr, cleaned_image_data)

            if data_transaksi: # Cukup cek apakah data valid ditemukan
                sheets_url = simpan_ke_sheets(data_transaksi)

                if sheets_url:
                    jumlah_rp = data_transaksi.get("jumlah", "N/A")
                    penerima = data_transaksi.get("penerima", "N/A")
                    tipe_display = data_transaksi.get("tipe", "Transaksi").replace("_", " ").title()
                    
                    jumlah_bersih = int(jumlah_rp)

                    pesan_balasan = (
                        f"Sip! 📝\n{tipe_display} sebesar Rp{jumlah_bersih:,} ke {penerima} udah dicatat. ✅\n\n"
                        f"Cek laporannya di sini:\n{sheets_url}"
                    ).replace(",", ".")
                else:
                    pesan_balasan = "Datanya berhasil dibaca, tapi gagal nyatet ke Google Sheets. Kayaknya ada masalah koneksi. 😥"
            
            else:
                # LAPIS 3: Jawaban jujur kalau semua metode gagal
                pesan_balasan = (
                    "Waduh, udah gw coba baca pake semua cara tapi infonya tetep gak jelas. 😵‍💫 "
                    "Bisa tolong coba foto ulang struknya lebih lurus dan terang?"
                )

        except Exception as e:
            print(f"❌ Error saat proses gambar: {e}")
            pesan_balasan = "Sorry, ada error internal pas lagi proses gambarnya. 😵"

    else:
        pesan_balasan = "Bro, kirim gambar struk belanja atau bukti transfernya dong biar bisa dicatat. 📸"

    print(f"✅ Pesan balasan dikirim: \"{pesan_balasan}\"")
    return pesan_balasan