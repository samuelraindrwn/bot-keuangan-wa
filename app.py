from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

# Import handler WhatsApp
from services.whatsapp_handler import handle_whatsapp_message

# Inisialisasi Flask
app = Flask(__name__)

# Ambil kredensial Twilio
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

if not TWILIO_SID or not TWILIO_TOKEN:
    raise RuntimeError("❌ TWILIO_ACCOUNT_SID atau TWILIO_AUTH_TOKEN belum diset di .env")


@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    """Endpoint untuk pesan WhatsApp dari Twilio"""
    response = MessagingResponse()
    pesan_balasan = handle_whatsapp_message(request, TWILIO_SID, TWILIO_TOKEN)
    response.message(pesan_balasan)
    return str(response)


if __name__ == "__main__":
    app.run(debug=True)
