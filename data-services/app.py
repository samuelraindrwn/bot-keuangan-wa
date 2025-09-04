from flask import Flask, request, jsonify
from tools.whatsapp_handler import handle_whatsapp_message

app = Flask(__name__)

@app.route("/process", methods=["POST"])
def process_message():
    data = request.json

    # Kirim langsung ke handler
    reply = handle_whatsapp_message(data)

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
