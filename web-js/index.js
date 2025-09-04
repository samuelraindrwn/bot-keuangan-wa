const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const client = new Client({
  authStrategy: new LocalAuth(),
});

client.on('qr', (qr) => {
  qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
  console.log('✅ Bot siap jalan!');
});

client.on('message', async (msg) => {
  console.log('📩 Pesan masuk:', msg.body, 'dari', msg.from);

  // ID grup target (ganti sesuai punya kamu)
  const targetGroupId = "120363422112527009@g.us";

  if (msg.from === targetGroupId) {
    try {
      // Payload dasar
      let payload = {
        sender: msg.from,        // 🔑 penting buat identifikasi siapa pending catatan
        message: msg.body || ""  // caption atau teks biasa
      };

      // Kalau pesan punya media (misalnya struk)
      if (msg.hasMedia) {
        const media = await msg.downloadMedia();
        payload.image = {
          mimetype: media.mimetype, // contoh: "image/jpeg"
          data: media.data          // base64 string
        };
      }

      // Kirim payload ke Python
      const response = await axios.post("http://127.0.0.1:5000/process", payload);

      const replyText = response.data.reply;
      if (replyText) {
        await msg.reply(replyText);
      }
    } catch (err) {
      console.error("❌ Error kirim ke Python:", err.message);
      await msg.reply("⚠️ Lagi ada error server, coba lagi nanti.");
    }
  }
});

client.initialize();
