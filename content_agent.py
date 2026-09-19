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
            news_items.append(entry.title)
        return news_items
    except Exception as e:
        print(f"Gagal mengambil RSS: {e}")
        return ["Tidak ada berita fundamental terbaru yang signifikan saat ini."]

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


def fetch_live_gold_price():
    """Mengambil harga emas real-time (XAUUSD) menggunakan yfinance"""
    try:
        import yfinance as yf
        gold = yf.Ticker("GC=F")
        price = gold.history(period="1d")['Close'].iloc[-1]
        return f"${price:.2f}/oz"
    except Exception as e:
        print(f"Gagal mengambil harga emas: {e}")
        return "Harga tidak tersedia saat ini"

def generate_content_draft(topic_type):
    """Men-generate konten menggunakan AI dan mengembalikannya sebagai teks (Draft)"""
    print(f"\n[CONTENT AGENT] Mulai membuat draft konten: {topic_type}")
    
    live_price = fetch_live_gold_price()
    
    # Deteksi Waktu Asli
    from datetime import datetime
    import pytz
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    hari_ini = now.strftime("%A")
    jam_ini = now.hour
    
    if 5 <= jam_ini < 11:
        sapaan = "pagi"
    elif 11 <= jam_ini < 15:
        sapaan = "siang"
    elif 15 <= jam_ini < 18:
        sapaan = "sore"
    else:
        sapaan = "malam"
        
    is_weekend = hari_ini in ["Saturday", "Sunday"]
    market_status = "TUTUP (Fokus Edukasi/Insight Minggu Depan)" if is_weekend else "BUKA"
    
    # 1. Mengingat (Memory) apa yang sudah dibahas
    context = f"Info Waktu: Saat ini hari {hari_ini}, jam {now.strftime('%H:%M')} WIB ({sapaan}). Market XAUUSD: {market_status}."

    # 2. Hierarchy Skill (Prompting Spesifik agar tidak pusing)
    skill_context = ""
    if "Market" in topic_type or "News" in topic_type:
        skill_context = """
[SKILL: MARKET CONTENT]
- FOKUS MUTLAK HANYA PADA XAUUSD (GOLD). Abaikan instrumen lain.
- Jika market tutup (Sabtu/Minggu), JANGAN berikan sinyal atau update harga harian, fokuslah pada RECAP minggu lalu atau INSIGHT untuk minggu depan.
- Jika ada berita, pastikan korelasinya langsung ke pergerakan Emas (USD, Inflasi, The Fed). Jika tidak berdampak ke Emas, tidak usah dibahas.
"""
    elif "Education" in topic_type or "Psychology" in topic_type:
        skill_context = """
[SKILL: TRADING EDUCATION & PSYCHOLOGY]
- Berikan edukasi berbobot namun mudah dimengerti trader pemula/Gen-Z.
- Bahas topik seperti Risk Management, FOMO, Disiplin, dan Psikologi.
- Jangan menggurui secara kaku, posisikan sebagai mentor asik.
"""
    elif "Community" in topic_type:
        skill_context = """
[SKILL: COMMUNITY ENGAGEMENT]
- Buat interaksi (pertanyaan, polling imajinatif, atau diskusi).
- Bikin trader merasa dilibatkan.
"""
    
    # 3. Prompting Persona AI
    from brand_context import GOLDZONFIRE_CONTEXT
    system_prompt = f"""{GOLDZONFIRE_CONTEXT}
Kamu adalah 'Content Agent' resmi dari channel Telegram VIP & Free Goldzonfire.
ROLE: Content Strategist & Automation Agent.
Misi Utama: Mengedukasi, mengingatkan berita (XAUUSD), dan menjaga engagement.

Aturan Penting (HARD RULES):
1. Sesuaikan SAPAAN dengan waktu saat ini (sekarang {sapaan}). JANGAN sapa 'pagi' jika ini sore.
2. Market saat ini {market_status}. Jangan suruh orang entry jika market tutup!
3. Gaya bahasa: Asik, kasual ala anak muda (Gen-Z/Millennial), profesional, dan BANYAK MENGGUNAKAN EMOJI (🔥🚀📈). Jangan kaku!
4. FOKUS HANYA XAUUSD.
5. Format: Gunakan bold (**teks**) untuk penekanan. Jangan gunakan blockquote (>).

{skill_context}
"""

    content_type = topic_type
    if "Market Insight" in topic_type or "News" in topic_type:
        news_titles = fetch_forex_news()
        if news_titles:
            context += "\n\nBerita Fundamental ForexLive:\n- " + "\n- ".join(news_titles)
            context += "\n(Gunakan berita di atas HANYA jika berdampak pada XAUUSD)."

    user_prompt = f"Buatkan postingan Telegram. Tipe konten: {content_type}. {context}\n\nLive Price XAUUSD saat ini (jika market buka): {live_price}"
    
    print("[CONTENT AGENT] Sedang meminta SumoPod AI untuk menulis teks...")
    post_text = generate_completion(system_prompt, user_prompt)
    return post_text

async def post_content_draft(client, post_text, content_type):
    """Memposting draft yang sudah disetujui ke Telegram"""
    try:
        from database import supabase
        await client.send_message(TARGET_CHANNEL, post_text, parse_mode='md')
        print(f"[CONTENT AGENT] Sukses memposting {content_type} ke Channel!")
        
        # Simpan sepenggal teks ke riwayat agar AI ingat
        topic_detail = post_text[:60] + "..." 
        try:
            supabase.table('content_history').insert({
                'topic_type': content_type,
                'topic_detail': topic_detail,
                'created_at': datetime.now(TIMEZONE).isoformat()
            }).execute()
        except:
            pass
        return True
    except Exception as e:
        print(f"[CONTENT AGENT] Error memposting ke Telegram: {e}")
        return False

async def generate_and_post_content(client, topic_type):
    post_text = generate_content_draft(topic_type)
    await post_content_draft(client, post_text, topic_type)

def setup_content_agent(client):
    """Mendaftarkan jadwal Content Agent ke dalam sistem dengan pemisahan Weekday/Weekend"""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    
    # WEEKDAY (Senin - Jumat): Market Buka
    scheduler.add_job(generate_and_post_content, 'cron', day_of_week='mon-fri', hour=8, minute=0, args=[client, "Morning Market Update"])
    scheduler.add_job(generate_and_post_content, 'cron', day_of_week='mon-fri', hour=12, minute=0, args=[client, "Market Insight"])
    scheduler.add_job(generate_and_post_content, 'cron', day_of_week='mon-fri', hour=17, minute=50, args=[client, "High Impact News (XAUUSD)"])
    
    # WEEKEND (Sabtu - Minggu): Market Tutup, Fokus Edukasi & Recap
    scheduler.add_job(generate_and_post_content, 'cron', day_of_week='sat-sun', hour=10, minute=0, args=[client, "Weekly Recap / Next Week Insight"])
    scheduler.add_job(generate_and_post_content, 'cron', day_of_week='sat-sun', hour=16, minute=0, args=[client, "Community Engagement (Poll/Quiz)"])
    
    # SETIAP HARI: Edukasi & Psikologi
    scheduler.add_job(generate_and_post_content, 'cron', hour=11, minute=0, args=[client, "Trading Education"])
    scheduler.add_job(generate_and_post_content, 'cron', hour=20, minute=0, args=[client, "Trading Psychology"])
    
    scheduler.start()
    print("✅ Content Agent Scheduler berhasil diaktifkan!")
