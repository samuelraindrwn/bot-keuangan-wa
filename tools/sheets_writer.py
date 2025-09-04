# sheets_writer.py (Upgraded)
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
    'data' adalah dictionary hasil parsing, 
    contoh: {'jumlah': '150000', 'penerima': 'Budi', 'tipe': 'BCA'}
    """
    print(f"📝 Menyimpan data ke Google Sheets...")
    try:
        # --- Otentikasi (Tetap sama) ---
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(NAMA_FILE_KREDENSIAL, scope)
        client = gspread.authorize(creds)

        # --- Buka Spreadsheet dan Sheet (Tetap sama) ---
        spreadsheet = client.open(NAMA_FILE_SHEETS)
        nama_bulan = datetime.now().strftime('%B')
        
        try:
            sheet = spreadsheet.worksheet(nama_bulan)
        except gspread.WorksheetNotFound:
            print(f"Sheet '{nama_bulan}' tidak ditemukan, membuat sheet baru...")
            sheet = spreadsheet.add_worksheet(title=nama_bulan, rows="200", cols="20")
            # --- Header Baru yang Lebih Detail ---
            # Pastikan header ini sesuai dengan data yang akan dimasukkan
            sheet.append_row(['Tanggal', 'Jumlah', 'Tipe', 'Penerima/Toko', 'Catatan'])

        # --- Siapkan Data untuk Disimpan (BARU) ---
        # Membersihkan format jumlah dan konversi ke integer
        jumlah_bersih = int(re.sub(r'\D', '', data.get("jumlah", "0")))
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # --- Baris Baru Sesuai Data yang Diekstrak ---
        data_baru = [
            timestamp, 
            jumlah_bersih,
            data.get("tipe", "N/A"),
            data.get("penerima", "N/A"),
            "" # Kolom 'Catatan' dikosongkan dulu, bisa dikembangkan nanti
        ]

        # --- Simpan Baris Baru (Tetap sama) ---
        sheet.append_row(data_baru)
        
        print(f"✅ Data berhasil disimpan ke sheet '{nama_bulan}'!")
        return True

    except Exception as e:
        print(f"❌ Gagal menyimpan ke Google Sheets. Error: {e}")
        raise e
