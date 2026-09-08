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
# Source channel diupdate ke ID terbaru
SOURCE_CHANNELS = [
    -1001168109129, # Channel 1
    -1001440024119  # Channel 2
]
TARGET_CHANNEL = -1003931224797

# === KONFIGURASI GAMBAR ===
IMAGE_URL = 'https://i.imgur.com/example.jpg'
IMAGE_PATH = 'design.png'
IMAGE_METHOD = 'LOCAL' 

if not SESSION_STRING:
    raise ValueError("SESSION_STRING tidak ditemukan! Harap set environment variable.")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# === STATUS SISTEM ===
# Mengontrol apakah bot saat ini memforward pesan atau tidak
IS_SYSTEM_ACTIVE = True 

# === KONFIGURASI FASTAPI ===
app = FastAPI(title="Telegram Forwarder API")

# Setup CORS agar Frontend Vercel bisa menembak API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Sangat aman diganti dengan URL Vercel spesifik nanti
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Telegram Forwarder Backend is Running!"}

@app.get("/api/status")
async def get_status():
    """Mengambil status bot saat ini (ON/OFF)"""
    return {"status": "ON" if IS_SYSTEM_ACTIVE else "OFF"}

@app.post("/api/toggle")
async def toggle_status():
    """Mengubah status bot dari ON ke OFF, atau sebaliknya"""
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
    
    if source_id == -1001168109129: # Channel 1 baru
        rr = "1:2"
    elif source_id == -1001440024119: # Channel 2 baru
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
    # Cek apakah sistem sedang dimatikan dari Vercel
    if not IS_SYSTEM_ACTIVE:
        print("Sinyal masuk diabaikan karena sistem dalam keadaan OFF.")
        return

    source_chat_id = event.chat_id
    message_text = event.raw_text
    print(f"Pesan baru diterima dari {source_chat_id}")
    
    signal_data = parse_signal(message_text, source_chat_id)
    if signal_data:
        print("Sinyal terdeteksi, memformat ulang...")
        formatted_message = format_message(signal_data)
        try:
            if IMAGE_METHOD == 'URL':
                await client.send_file(TARGET_CHANNEL, file=IMAGE_URL, caption=formatted_message)
            elif IMAGE_METHOD == 'LOCAL' and os.path.exists(IMAGE_PATH):
                await client.send_file(TARGET_CHANNEL, file=IMAGE_PATH, caption=formatted_message)
            else:
                await client.send_message(TARGET_CHANNEL, formatted_message)
            print(f"Sinyal berhasil diforward ke {TARGET_CHANNEL}")
        except Exception as e:
            print(f"Error saat mengirim pesan: {e}")
    else:
        print("Bukan pesan sinyal yang valid, abaikan.")

# Hook event start up FastAPI untuk menjalankan TelegramClient
@app.on_event("startup")
async def startup_event():
    print("Menjalankan Telegram Client...")
    await client.start()
    # Menjalankan task asinkron bot telegram agar tidak memblokir server FastAPI
    asyncio.create_task(client.run_until_disconnected())

if __name__ == "__main__":
    # Ini akan dijalankan oleh uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
