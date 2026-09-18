import asyncio
import feedparser
import pytz
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ai_helper import generate_completion
from database import supabase

TARGET_CHANNEL = -1003931224797
TIMEZONE = pytz.timezone('Asia/Jakarta')

def fetch_forex_news():
    """Mengambil berita forex/emas terbaru dari RSS Feed (ForexLive/Investing)"""
    # Menggunakan RSS ForexLive khusus Technical Analysis & Gold
    feed_url = "https://www.forexlive.com/feed/technicalanalysis"
    try:
        feed = feedparser.parse(feed_url)
        news_items = []
        for entry in feed.entries[:3]: # Ambil 3 berita teratas
            news_items.append(f"- {entry.title}")
        return "\n".join(news_items)
    except Exception as e:
        print(f"Gagal mengambil RSS: {e}")
        return "Tidak ada berita fundamental terbaru yang signifikan saat ini."

async def check_content_history(topic_type):
    """Cek di database topik apa yang baru saja diposting agar tidak mengulang"""
    try:
        res = supabase.table('content_history').select('*').eq('topic_type', topic_type).order('created_at', desc=True).limit(1).execute()
        if res.data:
            return res.data[0]['topic_detail']
        return None
    except Exception as e:
        print(f"Peringatan: Tabel content_history sepertinya belum ada di Supabase. Error: {e}")
        return None

async def save_content_history(topic_type, topic_detail):
    """Simpan log topik ke database"""
    try:
        supabase.table('content_history').insert({
            'topic_type': topic_type,
            'topic_detail': topic_detail,
            'created_at': datetime.now(TIMEZONE).isoformat()
        }).execute()
    except Exception:
        pass


def generate_content_draft(topic_type):
    """Men-generate konten menggunakan AI dan mengembalikannya sebagai teks (Draft)"""
    print(f"\n[CONTENT AGENT] Mulai membuat draft konten: {topic_type}")
    
    live_price = fetch_live_gold_price()
    
    # 1. Mengingat (Memory) apa yang sudah dibahas
    history = get_recent_topics()
    context = ""
    if history:
        last_topic = history[0]
        if topic_type != "News Reminder":
            context = f"\n\nCatatan: Terakhir kali kamu membahas tentang '{last_topic}'. JANGAN bahas ini lagi, pilih sub-topik edukasi lain yang berbeda."

    # 2. Prompting Persona AI
    from brand_context import GOLDZONFIRE_CONTEXT
    system_prompt = f"""{GOLDZONFIRE_CONTEXT}

Kamu adalah 'Content Agent' resmi dari channel Telegram VIP & Free Goldzonfire.
Misi Utama: Mengedukasi, mengingatkan jadwal rilis berita fundamental (XAUUSD), dan menjaga engagement member.
Gaya bahasa: Professional, modern, clean, dan credible (sesuai Tone Brand).
Informasi Real-Time: Harga XAUUSD/Gold saat ini adalah {live_price}. (Jika relevan dengan konteks, sebutkan harga ini dengan natural).
Aturan Format (PENTING):
1. Gunakan dua bintang untuk teks tebal (contoh: **teks tebal**) dan satu bintang untuk miring.
2. Jangan pernah menggunakan format blockquote (>) karena akan berantakan di Telegram.
3. Konten harus TO THE POINT (jangan bertele-tele), maksimal 3-5 paragraf pendek.
4. Akhiri dengan semangat positif dari Goldzonfire."""

    # Jika butuh mengambil berita RSS
    content_type = topic_type
    if "Market Insight" in topic_type or "High Impact News" in topic_type:
        news_titles = fetch_forexlive_news()
        if news_titles:
            context += "\n\nBerita ForexLive hari ini:\n- " + "\n- ".join(news_titles)
            context += "\n(Gunakan berita di atas sebagai referensi analisis, tapi sesuaikan dengan gaya bahasamu)."

    user_prompt = f"Buatkan postingan Telegram untuk jadwal sekarang dengan tipe konten: {content_type}. {context}"
    
    # 3. Panggil API AI
    print("[CONTENT AGENT] Sedang meminta SumoPod AI untuk menulis teks...")
    post_text = generate_completion(system_prompt, user_prompt)
    return post_text

async def post_content_draft(client, post_text, content_type):
    """Memposting draft yang sudah disetujui ke Telegram"""
    try:
        await client.send_message(TARGET_CHANNEL, post_text, parse_mode='md')
        print(f"[CONTENT AGENT] Sukses memposting {content_type} ke Channel!")
        
        # Simpan sepenggal teks ke riwayat agar AI ingat
        topic_detail = post_text[:60] + "..." 
        await save_content_history(content_type, topic_detail)
        return True
    except Exception as e:
        print(f"[CONTENT AGENT] Error memposting ke Telegram: {e}")
        return False

async def generate_and_post_content(client, topic_type):
    """(Fungsi Otomatisasi Jadwal Lama) Men-generate konten dan mempostingnya langsung ke channel."""
    post_text = generate_content_draft(topic_type)
    await post_content_draft(client, post_text, topic_type)

def setup_content_agent(client):
    """Mendaftarkan jadwal Content Agent ke dalam sistem"""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    
    # Jadwal Posting (Berdasarkan Zona Waktu Jakarta / WIB)
    scheduler.add_job(generate_and_post_content, 'cron', hour=8, minute=0, args=[client, "Morning Market Update"])
    scheduler.add_job(generate_and_post_content, 'cron', hour=11, minute=0, args=[client, "Education"])
    scheduler.add_job(generate_and_post_content, 'cron', hour=12, minute=0, args=[client, "Market Insight"])
    scheduler.add_job(generate_and_post_content, 'cron', hour=17, minute=50, args=[client, "High Impact News"])
    scheduler.add_job(generate_and_post_content, 'cron', hour=20, minute=0, args=[client, "Trading Psychology"])
    
    scheduler.start()
    print("✅ Content Agent Scheduler berhasil diaktifkan!")
