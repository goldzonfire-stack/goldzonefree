import os
import re
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# === KONFIGURASI API ===
API_ID = 36110950
API_HASH = '630e203cb6a13cd99c7fcd8e3eebad9f'

SESSION_STRING = os.environ.get('SESSION_STRING', '')

# === KONFIGURASI CHANNEL ===
SOURCE_CHANNELS = [
    -1001168109129, # Channel 1
    -1001440024119  # Channel 2
]
TARGET_CHANNEL = -1003931224797

# === KONFIGURASI GAMBAR ===
IMAGE_URL = 'https://i.imgur.com/example.jpg'
IMAGE_PATH = 'design.png'
IMAGE_METHOD = 'LOCAL' 

# Variabel cache untuk mempercepat pengiriman gambar (menghilangkan delay)
CACHED_IMAGE = None

# Penyimpanan sementara untuk mapping Message ID agar bisa me-reply
# Format: {(source_chat_id, source_message_id): target_message_id}
msg_mapping = {}

if not SESSION_STRING:
    raise ValueError("SESSION_STRING tidak ditemukan! Harap set environment variable.")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# === STATUS SISTEM ===
IS_SYSTEM_ACTIVE = True 

# === KONFIGURASI FASTAPI ===
app = FastAPI(title="Telegram Forwarder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Telegram Forwarder Backend is Running!"}

@app.get("/api/status")
async def get_status():
    return {"status": "ON" if IS_SYSTEM_ACTIVE else "OFF"}

@app.post("/api/toggle")
async def toggle_status():
    global IS_SYSTEM_ACTIVE
    IS_SYSTEM_ACTIVE = not IS_SYSTEM_ACTIVE
    return {"status": "ON" if IS_SYSTEM_ACTIVE else "OFF"}

def parse_signal(text, source_id):
    """Mengekstrak informasi dari teks sinyal"""
    pair_match = re.search(r'([A-Z]{6})', text)
    action_match = re.search(r'(?i)(Buy|Sell)', text)
    entry_match = re.search(r'(?i)Price\s*Now\s*:\s*([0-9.]+)', text)
    sl_match = re.search(r'(?i)SL\s*:\s*([0-9.]+)', text)
    tp_match = re.search(r'(?i)TP\s*:\s*([0-9.]+)', text)
    
    if not (pair_match and action_match and entry_match and sl_match and tp_match):
        return None
        
    pair = pair_match.group(1).upper()
    action = action_match.group(1).upper()
    entry = entry_match.group(1)
    sl = sl_match.group(1)
    tp = tp_match.group(1)
    
    if source_id == -1001168109129: # Channel 1
        rr = "1:2"
    elif source_id == -1001440024119: # Channel 2
        rr = "1:1"
    else:
        rr = "1:1"
        
    return {
        "pair": pair,
        "action": action,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "rr": rr
    }

def parse_reply(text, source_id):
    """Mengekstrak informasi reply TP/SL"""
    text_lower = text.lower()
    
    # Cek Take Profit
    if 'take profit successfully hit' in text_lower or '+50 pips hit' in text_lower or 'tp' in text_lower or 'take profit' in text_lower:
        pips = 100 if source_id == -1001168109129 else 50
        return f"**FREE SIGNAL: +{pips} PIPS TP HIT!✅**"
        
    # Cek Stop Loss
    if 'stop loss hit' in text_lower or 'closed at sl' in text_lower or 'sl' in text_lower or 'stop loss' in text_lower:
        return "**FREE SIGNAL: -50 PIPS SL HIT! ❌**"
        
    return None

def format_message(data):
    """Mengubah data menjadi format channel utama"""
    msg = f"🚨 {data['pair']} {data['action']} 🚨\n\n"
    msg += f"⚪️ ENTRY: {data['entry']}\n"
    msg += f"🔴 STOP LOSS: {data['sl']}\n"
    msg += f"🟢 TAKE PROFIT: {data['tp']}\n\n"
    msg += f"⚖️ RISK : REWARD: {data['rr']}\n"
    return msg

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    global CACHED_IMAGE
    
    if not IS_SYSTEM_ACTIVE:
        return

    source_chat_id = event.chat_id
    source_msg_id = event.message.id
    message_text = event.raw_text
    
    # 1. CEK JIKA PESAN ADALAH REPLY (UPDATE TP/SL)
    if event.message.is_reply:
        reply_to_source_id = event.message.reply_to_msg_id
        target_msg_id = msg_mapping.get((source_chat_id, reply_to_source_id))
        
        reply_format = parse_reply(message_text, source_chat_id)
        if reply_format and target_msg_id:
            try:
                # Mengirim sebagai reply di target channel
                await client.send_message(TARGET_CHANNEL, reply_format, reply_to=target_msg_id)
                print(f"Reply TP/SL berhasil diforward ke {TARGET_CHANNEL}")
            except Exception as e:
                print(f"Error mengirim reply: {e}")
        return # Selesai memproses reply, jangan lanjut ke bawah

    # 2. CEK JIKA PESAN ADALAH SINYAL BARU
    signal_data = parse_signal(message_text, source_chat_id)
    if signal_data:
        formatted_message = format_message(signal_data)
        msg_obj = None
        
        try:
            if IMAGE_METHOD == 'URL':
                msg_obj = await client.send_file(TARGET_CHANNEL, file=IMAGE_URL, caption=formatted_message)
            elif IMAGE_METHOD == 'LOCAL' and os.path.exists(IMAGE_PATH):
                # Memperbaiki delay dengan caching gambar. 
                # Gambar hanya di-upload 1x, setelahnya bot mereuse File ID dari Telegram.
                if CACHED_IMAGE:
                    msg_obj = await client.send_file(TARGET_CHANNEL, file=CACHED_IMAGE, caption=formatted_message)
                else:
                    msg_obj = await client.send_file(TARGET_CHANNEL, file=IMAGE_PATH, caption=formatted_message)
                    CACHED_IMAGE = msg_obj.photo # Simpan ID gambar untuk dikirim berikutnya lebih cepat
            else:
                msg_obj = await client.send_message(TARGET_CHANNEL, formatted_message)
                
            if msg_obj:
                # Menyimpan ID pesan agar bisa di-reply jika nanti ada update TP/SL
                msg_mapping[(source_chat_id, source_msg_id)] = msg_obj.id
                
            print(f"Sinyal berhasil diforward ke {TARGET_CHANNEL}")
        except Exception as e:
            print(f"Error saat mengirim sinyal: {e}")

@app.on_event("startup")
async def startup_event():
    print("Menjalankan Telegram Client...")
    await client.start()
    asyncio.create_task(client.run_until_disconnected())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
