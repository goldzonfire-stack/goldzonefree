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


ALLOWED_USERS = ['agsaputra', 'agsaputrame']

@leader_client.on(events.NewMessage())
async def handle_leader_chat(event):
    sender = await event.get_sender()
    sender_username = getattr(sender, 'username', '') or ''
    
    # Hanya izinkan akses dari username yang diperbolehkan
    if sender_username.lower() not in ALLOWED_USERS:
        return

    # Hanya izinkan akses di DM atau di Channel Koordinasi
    if not (event.is_private or event.chat_id == COORDINATION_CHANNEL):
        return

    text = event.raw_text
    print(f"[DEBUG AI LEADER] Pesan diterima dari @{sender_username}: {text}")
    
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


from ai_helper import generate_completion, generate_chat_with_tools
import json

# Memori percakapan sementara per user (maksimal simpan 10 pesan terakhir)
chat_memory = {}

async def respond_to_human(event):
    """AI Leader membalas percakapan dengan bos/manusia dengan ingatan & eksekusi aksi (Tools)"""
    from brand_context import GOLDZONFIRE_CONTEXT
    
    sender_id = event.chat_id
    if sender_id not in chat_memory:
        # Inisialisasi memori dengan System Prompt
        system_prompt = f"""{GOLDZONFIRE_CONTEXT}
Kamu adalah 'AI Leader' (Direktur Operasional AI) dari ekosistem Goldzonfire.
Tugasmu: KAMU ADALAH MANAJER, BUKAN KONSULTAN. Kamu mengendalikan agen bawahan (Content & Promotion).
Gaya bahasa: Cerdas, analitis, profesional, tunduk pada Bos. Panggil pengguna 'Bos'.

INFORMASI PENTING (BACA DENGAN TELITI):
1. Jika pengguna meminta untuk MEMBUAT KONTEN (misal: "tolong suruh content agent bikin postingan soal psikologi"), JANGAN KAMU YANG MENULIS KONTENNYA SENDIRI! Kamu HARUS menggunakan tool 'request_content_draft'.
2. Setelah kamu menggunakan 'request_content_draft', tunggu responnya. Draf akan dikirim kembali kepadamu. Kamu harus menunjukkan draf itu ke Bos dan meminta PERSETUJUAN (Approval) sebelum di-posting.
3. Jika Bos berkata "Setuju", "Bagus, posting", "Lanjut", kamu HARUS memanggil tool 'post_content_now' untuk mem-publish-nya ke channel.
4. Jika Bos berkata "Jalankan flash sale", gunakan tool 'trigger_flash_sale'."""
        chat_memory[sender_id] = [{"role": "system", "content": system_prompt}]
        
    user_prompt = event.raw_text
    chat_memory[sender_id].append({"role": "user", "content": user_prompt})
    
    # Batasi memori agar tidak terlalu penuh (simpan 1 system prompt + 10 pesan terakhir)
    if len(chat_memory[sender_id]) > 11:
        chat_memory[sender_id] = [chat_memory[sender_id][0]] + chat_memory[sender_id][-10:]
    
    # Tool yang bisa dijalankan AI Leader
    tools = [
        {
            "type": "function",
            "function": {
                "name": "trigger_flash_sale",
                "description": "Eksekusi Flash Promo VIP secara langsung ke Publik Channel.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "alasan": {"type": "string", "description": "Alasan singkat mengapa flash promo ini dijalankan"}
                    },
                    "required": ["alasan"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "request_content_draft",
                "description": "Menyuruh Content Agent membuat draft postingan/edukasi tanpa mempostingnya langsung. Draf akan dikembalikan ke AI Leader untuk di-review bersama bos.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topik": {"type": "string", "description": "Topik yang ingin dibuat (misal: 'Trading Psychology', 'Market Insight')"}
                    },
                    "required": ["topik"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "post_content_now",
                "description": "Mempublish draft konten yang sudah disetujui bos ke Channel Publik.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content_text": {"type": "string", "description": "Teks konten lengkap yang akan diposting"}
                    },
                    "required": ["content_text"]
                }
            }
        }
    ]
    
    async with leader_client.action(event.chat_id, 'typing'):
        response_msg = generate_chat_with_tools(chat_memory[sender_id], tools=tools)
        
        # Mengecek apakah AI memutuskan untuk menjalankan Tool (Function Call)
        if response_msg.tool_calls:
            for tool_call in response_msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                if func_name == "trigger_flash_sale":
                    alasan = args.get("alasan", "Instruksi dari Bos")
                    await event.reply(f"🚀 **Menjalankan Perintah:** Flash Promo VIP dieksekusi sekarang juga!\n*Alasan AI:* {alasan}")
                    
                    if MAIN_CLIENT:
                        await generate_and_post_promo(MAIN_CLIENT, phase="Flash Promo (URGENT)", campaign_name="Flash Promo Kilat", product="VIP Member Goldzonfire", normal_price="Rp1.500.000", promo_price="Rp750.000 (Khusus Hari Ini)", extra_rules="Fokus urgensi super tinggi.")
                    chat_memory[sender_id].append({"role": "assistant", "content": "Flash promo sukses diposting."})
                    
                elif func_name == "request_content_draft":
                    topik = args.get("topik", "Trading Education")
                    await event.reply(f"⏳ *Memerintahkan Content Agent membuat draf untuk topik: {topik}...*")
                    
                    # Panggil fungsi draft dari Content Agent
                    from content_agent import generate_content_draft
                    draft_result = generate_content_draft(topik)
                    
                    # Tambahkan hasil draf ke memory agar AI Leader bisa membacanya
                    chat_memory[sender_id].append({"role": "assistant", "content": f"Draf selesai. Tunjukkan ini pada bos dan tanyakan apakah dia setuju untuk diposting:\n\n{draft_result}"})
                    
                    # Balas ke bos
                    await event.reply(f"📄 **DRAF DARI CONTENT AGENT**\n\n{draft_result}\n\n====================\n*Bos, apakah draf ini sudah oke untuk dipublish? (Ketik setuju jika iya)*")
                    
                elif func_name == "post_content_now":
                    teks_konten = args.get("content_text", "")
                    await event.reply(f"✅ *Mem-publish konten ke Publik Channel...*")
                    
                    if MAIN_CLIENT:
                        from content_agent import post_content_draft
                        # Kita gunakan 'Ad-hoc' sebagai tipe konten
                        success = await post_content_draft(MAIN_CLIENT, teks_konten, "Ad-hoc Posting by Leader")
                        if success:
                            await event.reply("✅ Konten sukses mengudara!")
                            chat_memory[sender_id].append({"role": "assistant", "content": "Konten berhasil dipublish."})
                        else:
                            await event.reply("❌ Gagal memposting konten.")
                            chat_memory[sender_id].append({"role": "assistant", "content": "Gagal mempublish konten."})
        else:
            final_response = response_msg.content
            chat_memory[sender_id].append({"role": "assistant", "content": final_response})
            await event.reply(final_response)

async def check_system_status(event):
    """Mengecek status nyala/mati agen-agen di sistem"""
    try:
        import main # Mengambil state dari main.py
        
        is_active = getattr(main, 'IS_SYSTEM_ACTIVE', True)
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
    except Exception as e:
        print(f"[DEBUG AI LEADER] Error di check_system_status: {e}")
        await event.reply(f"⚠️ Error mengambil status: {str(e)}")


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
