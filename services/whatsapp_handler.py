import os
import requests
from PIL import Image
import io
import re

from tools.ocr_reader import baca_struk
from tools.data_parser import klasifikasi_transaksi, ekstrak_info_transaksi
from tools.sheets_writer import simpan_ke_sheets

# Folder resource
RESOURCE_DIR = os.path.join("tools", "resource")
os.makedirs(RESOURCE_DIR, exist_ok=True)


def handle_whatsapp_message(request, twilio_sid, twilio_token):
    """Logic penanganan pesan WhatsApp"""

    print("\n--- Pesan WhatsApp Baru Diterima ---")

    if request.form.get("NumMedia") != "0":
        gambar_url = request.form.get("MediaUrl0")

        try:
            # Download gambar dengan auth Twilio
            resp = requests.get(gambar_url, auth=(twilio_sid, twilio_token))
            if resp.status_code != 200:
                raise Exception(f"Twilio response {resp.status_code}: {resp.text}")

            print("✅ Gambar berhasil di-download ke memori.")
            print("Content-Type:", resp.headers.get("Content-Type"))
            print("Size:", len(resp.content))
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
                debug_path = os.path.join(RESOURCE_DIR, "debug_media.bin")
                with open(debug_path, "wb") as f:
                    f.write(image_data)
                raise Exception(
                    f"PIL tidak bisa mengenali gambar. File mentah disimpan di {debug_path}. Detail: {pil_err}"
                )

            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            output_bytes_io = io.BytesIO()
            image.save(output_bytes_io, format="JPEG")
            cleaned_image_data = output_bytes_io.getvalue()
            print("✨ Gambar sudah bersih dan siap diproses!")

            # OCR
            teks_hasil_ocr = baca_struk(cleaned_image_data)

            # Klasifikasi & ekstrak data
            tipe_transaksi = klasifikasi_transaksi(teks_hasil_ocr)
            data_transaksi = ekstrak_info_transaksi(teks_hasil_ocr, tipe_transaksi)

            if data_transaksi and data_transaksi.get("jumlah", "0") != "0":
                simpan_ke_sheets(data_transaksi)

                jumlah_rp = data_transaksi.get("jumlah", "N/A")
                penerima = data_transaksi.get("penerima", "N/A")
                tipe_display = data_transaksi.get("tipe", "Transaksi").replace("_", " ").title()

                jumlah_bersih = int(re.sub(r"\D", "", jumlah_rp))
                pesan_balasan = (
                    f"Sip! 📝\n{tipe_display} sebesar Rp{jumlah_bersih:,} ke {penerima} udah dicatat. ✅"
                ).replace(",", ".")
            else:
                pesan_balasan = (
                    f"Aku liat ini kayak bukti {tipe_transaksi.replace('_',' ').title()}, "
                    f"tapi gagal ngambil infonya. Coba foto lebih jelas ya. 😥"
                )

        except Exception as e:
            print(f"❌ Error saat proses gambar: {e}")
            pesan_balasan = "Sorry, ada error internal pas lagi proses gambarnya. 😵"

    else:
        pesan_balasan = "Bro, kirim gambar struk belanja atau bukti transfernya dong biar bisa dicatat. 📸"

    print(f"✅ Pesan balasan dikirim: \"{pesan_balasan}\"")
    return pesan_balasan
