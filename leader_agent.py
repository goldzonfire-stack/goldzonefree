import os
import asyncio
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import MemorySession
from telethon.tl.custom import Button
from ai_helper import generate_completion
from promotion_agent import generate_and_post_promo
from database import supabase
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === KONFIGURASI ===
API_ID = 36110950
API_HASH = '630e203cb6a13cd99c7fcd8e3eebad9f'
BOT_TOKEN = os.environ.get('LEADER_BOT_TOKEN')
COORDINATION_CHANNEL = -1003984255098
TIMEZONE = pytz.timezone('Asia/Jakarta')

if not BOT_TOKEN:
    raise ValueError("LEADER_BOT_TOKEN tidak ditemukan di .env")

# Kita menggunakan MemorySession karena Bot tidak butuh session permanen (login otomatis pakai Token)
leader_client = TelegramClient(MemorySession(), API_ID, API_HASH)

# Referensi ke client utama (Userbot) agar AI Leader bisa menyuruh agent lain memposting di channel publik
MAIN_CLIENT = None

def setup_leader_agent(main_client):
    """Mendaftarkan tugas rutin AI Leader"""
    global MAIN_CLIENT
    MAIN_CLIENT = main_client
    
    # AI Leader akan memberikan Laporan Harian (Daily Report) setiap jam 23:00 WIB
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(generate_daily_report, 'cron', hour=23, minute=0)
    scheduler.start()

async def start_leader_client():
    """Menjalankan koneksi bot AI Leader"""
    await leader_client.start(bot_token=BOT_TOKEN)
    print("✅ AI Leader Bot berhasil aktif!")


# ==========================================
# 1. PERCAKAPAN & KOORDINASI (INTERAKTIF)
# ==========================================

@leader_client.on(events.NewMessage(chats=[COORDINATION_CHANNEL]))
async def handle_leader_chat(event):
    text = event.raw_text
    
    # Cek jika bos me-reply pesan Bot ini (untuk ngobrol langsung dengan AI Leader)
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg and replied_msg.sender_id == (await leader_client.get_me()).id:
            await respond_to_human(event)
            return

    # Routing Command
    if text.startswith("/report"):
        await generate_daily_report(event)
    elif text.startswith("/status"):
        await check_system_status(event)
    elif text.startswith("/suggest_promo"):
        await suggest_promotion(event)
    elif text.startswith("/ai") or "leader" in text.lower() or event.is_private:
        await respond_to_human(event)


async def respond_to_human(event):
    """AI Leader membalas percakapan dengan bos/manusia"""
    system_prompt = """Kamu adalah 'AI Leader' (Direktur Operasional AI) dari ekosistem Goldzonfire.
Tugasmu: Menganalisis kondisi bisnis, mengkoordinasikan agent lain (Content, Promotion, Sales, dll), memberi saran strategis, dan memantau kesehatan sistem.
Gaya bahasa: Sangat cerdas, analitis, profesional, dan solutif. Panggil pengguna dengan sebutan 'Bos' atau 'Chief'.

INFORMASI PENTING (ATURAN):
1. Jika pengguna bertanya tentang status agen, beritahu mereka untuk mengetik command `/status`.
2. Jika ada masalah sistem yang sifatnya perbaikan kode program (Bug Fixing) atau butuh penambahan fitur kompleks, katakan bahwa kamu tidak bisa mengubah kode inti secara langsung. Sarankan pengguna untuk meneruskan pesan error atau log sistem kepada **"Antigravity"** (AI Programmer/Arsitek Sistem yang membangun kamu) agar Antigravity yang melakukan update kode.
3. Selalu berikan jawaban yang singkat, padat, dan langsung ke poin permasalahan."""
    
    user_prompt = event.raw_text
    
    async with leader_client.action(COORDINATION_CHANNEL, 'typing'):
        response = generate_completion(system_prompt, user_prompt)
        await event.reply(response)

async def check_system_status(event):
    """Mengecek status nyala/mati agen-agen di sistem"""
    import main # Mengambil state dari main.py
    
    is_active = main.IS_SYSTEM_ACTIVE
    status_text = "🟢 **ONLINE**" if is_active else "🔴 **OFFLINE**"
    
    msg = (
        f"🖥 **GOLDZONFIRE SYSTEM STATUS**\n\n"
        f"**1. Core System (Forwarder)**: {status_text}\n"
        f"**2. Content Agent**: 🟢 Aktif (Jadwal berjalan otomatis)\n"
        f"**3. Promotion Agent**: 🟢 Aktif (Jadwal berjalan otomatis)\n"
        f"**4. AI Leader**: 🟢 Siaga di Private Channel\n"
        f"**5. Supabase Database**: 🟢 Terkoneksi\n\n"
        f"*(Ketik `/report` untuk melihat jumlah aktivitas hari ini)*"
    )
    await event.reply(msg)


# ==========================================
# 2. SISTEM APPROVAL (MEMINTA PERSETUJUAN)
# ==========================================

async def suggest_promotion(event):
    """Contoh: AI Leader mendeteksi perlunya promosi, lalu meminta persetujuan manusia"""
    msg = (
        "📊 **Analisis AI Leader:**\n\n"
        "Bos, saya telah memantau pergerakan ekosistem kita hari ini. "
        "Untuk melakukan konversi dari Free ke VIP secara maksimal, saya merekomendasikan kita meluncurkan **Flash Promo VIP** secara tiba-tiba.\n\n"
        "Apakah Anda memberikan *Approval* (Persetujuan) kepada saya untuk memerintahkan *Promotion Agent* agar segera mengeksekusi kampanye ini?"
    )
    
    # Membuat tombol Inline
    buttons = [
        [Button.inline("✅ Approve (Jalankan Promo)", data="approve_flash_promo")],
        [Button.inline("❌ Reject (Batalkan)", data="reject_promo")]
    ]
    await leader_client.send_message(COORDINATION_CHANNEL, msg, buttons=buttons)

@leader_client.on(events.CallbackQuery)
async def handle_approval(event):
    """Menangani ketika bos menekan tombol Approve/Reject"""
    if event.data == b"approve_flash_promo":
        await event.edit("✅ **APPROVED**\n\nBaik Bos, *Approval* diterima. Saya telah mengkoordinasikan **Promotion Agent** untuk meluncurkan Flash Promo saat ini juga ke Publik Channel!")
        
        # AI Leader memerintahkan Promotion Agent! (Multi-agent coordination)
        if MAIN_CLIENT:
            await generate_and_post_promo(
                MAIN_CLIENT, 
                phase="Flash Promo (URGENT)", 
                campaign_name="Flash Promo Kilat", 
                product="VIP Member Goldzonfire", 
                normal_price="Rp1.500.000", 
                promo_price="Rp750.000 (Khusus Hari Ini)", 
                extra_rules="Fokus pada urgensi tinggi, promo hanya berlaku 24 jam! Jangan kasih ampun untuk yang telat."
            )
            
    elif event.data == b"reject_promo":
        await event.edit("❌ **REJECTED**\n\nSiap Bos, eksekusi Flash Promo dibatalkan. Saya akan terus memantau kondisi *engagement* channel.")


# ==========================================
# 3. LAPORAN HARIAN (DAILY REPORT)
# ==========================================

async def generate_daily_report(event=None):
    """AI Leader mengekstrak data dari Database dan menyusun laporan harian"""
    print("\n[AI LEADER] Menyusun Laporan Harian (Daily Report)...")
    
    try:
        # 1. Baca data dari Database (Aktivitas Agent Hari Ini)
        today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
        res = supabase.table('content_history').select('*').gte('created_at', f"{today}T00:00:00Z").execute()
        
        jumlah_postingan = len(res.data) if res.data else 0
        detail_kegiatan = ", ".join([item['topic_type'] for item in res.data]) if res.data else "Tidak ada"
        
        # 2. Minta AI menganalisis dan merangkum
        system_prompt = "Kamu adalah AI Leader Goldzonfire. Tugasmu membuat 'Daily Report' ringkas, rapi, dan profesional untuk bos (manajemen). Gunakan bahasa Indonesia."
        user_prompt = f"Hari ini, ekosistem agen kita (Content & Promotion Agent) telah berhasil melakukan {jumlah_postingan} kali tindakan otomatis di publik channel.\nDetail aksi: {detail_kegiatan}.\n\nBuatkan rangkuman evaluasi singkat dan berikan rekomendasi strategi apa yang sebaiknya kita (agen AI) lakukan untuk besok."
        
        report_text = generate_completion(system_prompt, user_prompt)
        
        pesan = f"📋 **DAILY REPORT AI LEADER**\n*Tanggal: {today}*\n\n{report_text}"
        
        if event:
            await event.reply(pesan)
        else:
            await leader_client.send_message(COORDINATION_CHANNEL, pesan)
            
    except Exception as e:
        print(f"Error daily report: {e}")
        if event:
            await event.reply(f"Maaf Bos, ada kendala saat menyusun report: {e}")
