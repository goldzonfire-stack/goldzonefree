import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Masukkan API ID dan Hash dari my.telegram.org
API_ID = 36110950
API_HASH = '630e203cb6a13cd99c7fcd8e3eebad9f'

async def main():
    print("Membuat String Session...")
    print("Silakan masukkan nomor telepon dan kode OTP Telegram jika diminta.")
    
    # Membuat client dengan StringSession kosong (akan dibuat baru)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    
    await client.start()
    
    # Mengambil session string
    session_string = client.session.save()
    
    print("\n" + "="*50)
    print("BERHASIL! Copy teks panjang di bawah ini dan masukkan ke variable environment Railway (SESSION_STRING):")
    print("="*50 + "\n")
    print(session_string)
    print("\n" + "="*50)

if __name__ == '__main__':
    asyncio.run(main())
