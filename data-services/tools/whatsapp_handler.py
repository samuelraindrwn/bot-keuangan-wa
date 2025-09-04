import os
import base64
from PIL import Image
import io

from .ocr_reader import baca_struk
from .data_parser import parse_receipt
from .sheets_writer import simpan_ke_sheets

# Folder resource
RESOURCE_DIR = os.path.join("tools", "resource")
os.makedirs(RESOURCE_DIR, exist_ok=True)

# Cache sederhana buat nyimpen transaksi pending per sender
PENDING_TRANSACTIONS = {}

def _handle_text_message(message_body, sender=None):
    """Logic khusus untuk menangani pesan teks (manual input atau catatan tambahan)."""
    if not message_body:
        return "Pesannya kosong. Ketik `bantuan` buat lihat cara pakenya."

    body = message_body.strip()
    lower_body = body.lower()

    # 🔑 Cek apakah ada transaksi pending untuk sender ini
    if sender and sender in PENDING_TRANSACTIONS:
        data_transaksi = PENDING_TRANSACTIONS.pop(sender)
        data_transaksi["catatan"] = body
        sheets_url = simpan_ke_sheets(data_transaksi)
        return _format_success_message(data_transaksi, sheets_url)

    # Keyword bantuan
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


def _handle_image_message(image_dict, user_caption="", sender=None):
    """Logic khusus untuk pesan gambar (via Node.js)."""
    try:
        image_data = base64.b64decode(image_dict["data"])
        image = Image.open(io.BytesIO(image_data))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        output_bytes_io = io.BytesIO()
        image.save(output_bytes_io, format="JPEG")
        cleaned_image_data = output_bytes_io.getvalue()

        # OCR & parsing
        teks_hasil_ocr = baca_struk(cleaned_image_data)
        data_transaksi = parse_receipt(teks_hasil_ocr, cleaned_image_data, user_caption)

        if data_transaksi:
            if not data_transaksi.get("catatan") and not user_caption:
                # simpan state pending
                if sender:
                    PENDING_TRANSACTIONS[sender] = data_transaksi
                return "Gambarnya udah kebaca, tapi catatannya apa nih? Balas pesan ini dengan catatannya ya."

            sheets_url = simpan_ke_sheets(data_transaksi)
            return _format_success_message(data_transaksi, sheets_url)

        return "Waduh, gw coba baca pake semua cara tapi infonya tetep nggak jelas. 😵‍💫 Coba foto ulang struknya lebih lurus & terang ya."

    except Exception as e:
        print(f"❌ Error saat proses gambar: {e}")
        return "Sorry, ada error internal pas lagi proses gambarnya. 😵"


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


def handle_whatsapp_message(payload):
    """Router utama (khusus Node.js flow)."""
    print("\n--- Pesan WhatsApp Baru Diterima ---")

    message_body = (payload.get("message") or "").strip()
    image_dict = payload.get("image")
    sender = payload.get("sender")

    # 🔑 Prioritaskan gambar
    if image_dict:
        return _handle_image_message(image_dict, message_body, sender)
    elif message_body:
        return _handle_text_message(message_body, sender)
    else:
        return "Pesannya kosong. Ketik `bantuan` buat lihat cara pakenya."
