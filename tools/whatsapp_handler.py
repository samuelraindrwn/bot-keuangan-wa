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


def _handle_image_message(request, twilio_sid, twilio_token):
    """Logic khusus untuk menangani pesan yang berisi gambar/struk."""
    gambar_url = request.form.get("MediaUrl0")
    user_caption = (request.form.get("Body") or "").strip()

    if not gambar_url:
        print("⚠️ Pesan media diterima, tapi URL gambar kosong (kemungkinan besar stiker).")
        return "Wih, stikernya keren! 😎 Tapi buat nyatet keuangan, kirim foto struk ya, bukan stiker."

    try:
        resp = requests.get(gambar_url, auth=(twilio_sid, twilio_token))
        if resp.status_code != 200:
            raise Exception(f"Twilio response {resp.status_code}: {resp.text}")
        print("✅ Gambar berhasil di-download ke memori.")
        image_data = resp.content

        # Cleaning gambar
        try:
            image = Image.open(io.BytesIO(image_data))
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            output_bytes_io = io.BytesIO()
            image.save(output_bytes_io, format="JPEG")
            cleaned_image_data = output_bytes_io.getvalue()
            print("✨ Gambar sudah bersih dan siap diproses!")
        except Exception as pil_err:
            debug_path = os.path.join(RESOURCE_DIR, "debug_media.bin")
            with open(debug_path, "wb") as f:
                f.write(image_data)
            raise Exception(f"PIL tidak bisa mengenali gambar. File disimpan di {debug_path}. Detail: {pil_err}")

        # OCR & parsing
        teks_hasil_ocr = baca_struk(cleaned_image_data)
        data_transaksi = parse_receipt(teks_hasil_ocr, cleaned_image_data, user_caption)

        if data_transaksi:
            if not data_transaksi.get("catatan") and not user_caption:
                return "Gambarnya udah kebaca, tapi catatannya apa nih? Balas pesan ini dengan catatannya ya."

            sheets_url = simpan_ke_sheets(data_transaksi)
            return _format_success_message(data_transaksi, sheets_url)

        return "Waduh, gw coba baca pake semua cara tapi infonya tetep nggak jelas. 😵‍💫 Coba foto ulang struknya lebih lurus & terang ya."

    except Exception as e:
        print(f"❌ Error saat proses gambar: {e}")
        return "Sorry, ada error internal pas lagi proses gambarnya. 😵"


def _handle_text_message(message_body):
    """Logic khusus untuk menangani pesan teks (manual input)."""
    print(f"[DEBUG] Body mentah dari Twilio: {repr(message_body)}")

    if not message_body:
        return "Pesannya kosong. Ketik `bantuan` buat lihat cara pakenya."

    body = message_body.strip()
    lower_body = body.lower()

    help_keywords = ["help", "tolong", "keyword", "halo", "bantuan", "info"]
    if lower_body in help_keywords:
        return (
            "Yo! 👋 Mau nyatet pengeluaran? Gini caranya:\n\n"
            "1️⃣ *Kirim Gambar + Caption*\n"
            "   Foto struk/bukti transfer + caption catatan.\n"
            "   Contoh: _(kirim foto struk Indomaret)_ lalu caption: `Belanja bulanan`\n\n"
            "2️⃣ *Kirim Teks Langsung*\n"
            "   Format: `jumlah#penerima#catatan`\n"
            "   Contoh: `25000#Gojek#transport ke kantor`\n\n"
            "Tinggal pilih cara paling pas buat lo. Sat-set kan? 😉"
        )

    # Format manual (2 atau 3 bagian)
    parts = body.split("#")
    if len(parts) >= 2:
        jumlah = parts[0].strip()
        penerima = parts[1].strip()
        catatan = parts[2].strip() if len(parts) >= 3 else "-"

        if not jumlah.isdigit():
            return "⚠️ Format salah. Bagian depan harus angka (contoh: `25000#Gojek#catatan`)."

        data_transaksi = {
            "jumlah": jumlah,
            "penerima": penerima,
            "tipe": "Catatan Manual",
            "catatan": catatan
        }
        sheets_url = simpan_ke_sheets(data_transaksi)
        return _format_success_message(data_transaksi, sheets_url)

    return "Pesan lo nggak kebaca. Ketik `bantuan` buat lihat cara pakenya."


def _format_success_message(data, url):
    """Membuat pesan balasan yang konsisten setelah berhasil disimpan."""
    if not url:
        return "Datanya berhasil dibaca, tapi gagal nyatet ke Google Sheets. Kayaknya ada masalah koneksi. 😥"

    jumlah_rp = data.get("jumlah", "0")
    penerima = data.get("penerima", "N/A")
    tipe_display = data.get("tipe", "Transaksi").replace("_", " ").title()
    catatan = data.get("catatan", "")

    try:
        jumlah_bersih = int(jumlah_rp)
        jumlah_display = f"Rp{jumlah_bersih:,}".replace(",", ".")
    except (ValueError, TypeError):
        jumlah_display = jumlah_rp

    pesan = (
        f"Sip! 📝\n"
        f"*{tipe_display}* sebesar *{jumlah_display}* ke *{penerima}* udah dicatat. ✅\n"
    )
    if catatan and catatan != "-":
        pesan += f"Catatan: _{catatan}_\n\n"
    else:
        pesan += "\n"

    pesan += f"Cek laporannya di sini:\n{url}"
    return pesan


def handle_whatsapp_message(request, twilio_sid, twilio_token):
    """Router utama untuk semua pesan masuk dari WhatsApp."""
    print("\n--- Pesan WhatsApp Baru Diterima ---")

    message_body = (request.form.get("Body") or "").strip()
    num_media = request.form.get("NumMedia", "0")

    # Kadang Twilio kirim ghost media (NumMedia=1 tapi URL kosong)
    media_url = request.form.get("MediaUrl0")
    is_real_media = num_media != "0" and media_url and media_url.strip()

    # Prioritaskan teks kalau ada
    if message_body:
        pesan_balasan = _handle_text_message(message_body)
    elif is_real_media:
        pesan_balasan = _handle_image_message(request, twilio_sid, twilio_token)
    else:
        pesan_balasan = "Pesannya kosong. Ketik `bantuan` buat lihat cara pakenya."

    print(f"✅ Pesan balasan dikirim: \"{pesan_balasan}\"")
    return pesan_balasan