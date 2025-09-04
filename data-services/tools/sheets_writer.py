# tools/sheets_writer.py (Upgraded V2)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import locale
from dotenv import load_dotenv
load_dotenv() 

NAMA_FILE_KREDENSIAL = os.environ.get("NAMA_FILE_KREDENSIAL")
NAMA_FILE_SHEETS = os.environ.get("NAMA_FILE_SHEETS")
LOCALE_DATETIME = os.environ.get("LOCALE_DATETIME")
locale.setlocale(locale.LC_TIME, LOCALE_DATETIME)

def simpan_ke_sheets(data: dict):
    """
    Menyimpan data pengeluaran terstruktur, sekarang dengan kolom 'Catatan'.
    Me-return URL spreadsheet jika berhasil, atau None jika gagal.
    """
    print(f"📝 Menyimpan data ke Google Sheets...")
    try:
        # Otentikasi
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(NAMA_FILE_KREDENSIAL, scope)
        client = gspread.authorize(creds)

        # Buka Spreadsheet
        spreadsheet = client.open(NAMA_FILE_SHEETS)
        nama_bulan = datetime.now().strftime('%B')
        print(f"📅 Menggunakan sheet bulan: {nama_bulan}")
        
        try:
            sheet = spreadsheet.worksheet(nama_bulan)
        except gspread.WorksheetNotFound:
            print(f"Sheet '{nama_bulan}' tidak ditemukan, membuat sheet baru...")
            sheet = spreadsheet.add_worksheet(title=nama_bulan, rows="200", cols="20")
            sheet.append_row(['Tanggal', 'Jumlah', 'Tipe', 'Penerima/Toko', 'Catatan'])

        # Siapkan Data
        jumlah_bersih = int(re.sub(r'\D', '', str(data.get("jumlah", "0"))))
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        catatan = data.get("catatan", "")
        
        data_baru = [
            timestamp, 
            jumlah_bersih,
            data.get("tipe", "N/A"),
            data.get("penerima", "N/A"),
            catatan
        ]

        # Simpan Baris & Return URL
        sheet.append_row(data_baru)
        print(f"✅ Data berhasil disimpan! URL: {spreadsheet.url}")
        return spreadsheet.url

    except Exception as e:
        print(f"❌ Gagal menyimpan ke Google Sheets. Error: {e}")
        return None