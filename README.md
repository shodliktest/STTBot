# SHodlik AI STT — Telegram Object Storage Edition

## Arxitektura
- **Firebase/Firestore:** faqat config, kichik statistika, users va `audio_index` xaritasi.
- **Private Telegram channel:** original audio/voice va script JSON fayllari.
- `SHA-256(audio)` — deduplication kaliti.
- Firebase `audio_index/{sha256}` ichida Telegram `message_id`/`file_id` reference saqlanadi.
- Katta transcript matnlari Firestore'ga yozilmaydi.

## Required Streamlit Secrets
```toml
BOT_TOKEN = "..."
ADMIN_ID = 1416457518
TELEGRAM_DB_CHANNEL_ID = -1001234567890
WHISPER_MODEL = "base"

[firebase]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

The bot must be an administrator of the private Telegram database channel with permission to post messages.

## Deployment
Use the root `main.py` as the Streamlit entry point.
