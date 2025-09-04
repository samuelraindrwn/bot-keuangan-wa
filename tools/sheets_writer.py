# tools/sheets_writer.py (Upgraded)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os

from dotenv import load_dotenv
load_dotenv() 


NAMA_FILE_KREDENSIAL = os.environ.get("NAMA_FILE_KREDENSIAL")
NAMA_FILE_SHEETS = os.environ.get("NAMA_FILE_SHEETS")

def simpan_ke_sheets(data: dict):
    """
    Fungsi baru untuk menyimpan data pengeluaran yang lebih terstruktur.
    'data' adalah dictionary hasil parsing.
    
    DIUBAH: Sekarang me-return URL spreadsheet jika berhasil, atau None jika gagal.
    """
    print(f"📝 Menyimpan data ke Google Sheets...")
    try:
        # --- Otentikasi ---
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(NAMA_FILE_KREDENSIAL, scope)
        client = gspread.authorize(creds)

        # --- Buka Spreadsheet ---
        spreadsheet = client.open(NAMA_FILE_SHEETS)
        nama_bulan = datetime.now().strftime('%B')
        
        try:
            sheet = spreadsheet.worksheet(nama_bulan)
        except gspread.WorksheetNotFound:
            print(f"Sheet '{nama_bulan}' tidak ditemukan, membuat sheet baru...")
            sheet = spreadsheet.add_worksheet(title=nama_bulan, rows="200", cols="20")
            sheet.append_row(['Tanggal', 'Jumlah', 'Tipe', 'Penerima/Toko', 'Catatan'])

        # --- Siapkan Data ---
        jumlah_bersih = int(re.sub(r'\D', '', data.get("jumlah", "0")))
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        data_baru = [
            timestamp, 
            jumlah_bersih,
            data.get("tipe", "N/A"),
            data.get("penerima", "N/A"),
            ""
        ]

        # --- Simpan Baris & Return URL (BARU) ---
        sheet.append_row(data_baru)
        print(f"✅ Data berhasil disimpan! URL: {spreadsheet.url}")
        return spreadsheet.url # <-- Perubahan di sini

    except Exception as e:
        print(f"❌ Gagal menyimpan ke Google Sheets. Error: {e}")
        return None # <-- Perubahan di sini