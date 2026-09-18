import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ai_helper import generate_completion
import pytz

TARGET_CHANNEL = -1003931224797
TIMEZONE = pytz.timezone('Asia/Jakarta')

def get_promotion_prompt(phase, campaign_name, product, normal_price, promo_price, extra_rules=""):
    """Menyusun Prompt Khusus Berdasarkan Framework AIDA dan Aturan Goldzonfire"""
    
    system_prompt = """Kamu adalah 'Promotion Agent' untuk channel Telegram Goldzonfire.
Tugas utamamu: Mengubah audience Free Channel menjadi klien berbayar menggunakan framework copywriting AIDA (Attention -> Interest -> Trust -> Desire -> Action).
Gaya bahasa: Persuasif, eksklusif, profesional, elegan, dan tidak memaksa (tidak murahan).
ATURAN MUTLAK (SANGAT PENTING): 
- JANGAN PERNAH mengarang, memalsukan, atau membuat-buat data performa trading (seperti persentase win rate, profit bulan lalu, atau jumlah pips palsu). 
- Jika ingin membangun 'Trust', gunakan logika, psikologi trading, manajemen risiko, atau kualitas edukasi/setup yang didapat di VIP.
Format: Gunakan bold (**) untuk penekanan dan pembagian struktur. Jangan gunakan blockquote (>).
Call to Action (CTA): Arahkan ke kontak Admin (@AdminGoldzonfire) atau link website resmi."""

    user_prompt = f"""Buatkan konten promosi untuk fase: {phase}.
Detail Campaign:
- Nama Campaign: {campaign_name}
- Produk: {product}
- Harga Normal: {normal_price}
- Harga Promo: {promo_price}
{extra_rules}

Susun pesan ini sedemikian rupa agar menonjolkan AIDA. Sesuaikan nuansa urgensinya dengan fase "{phase}" ini."""

    return system_prompt, user_prompt

async def generate_and_post_promo(client, phase, campaign_name, product, normal_price, promo_price, extra_rules=""):
    """Fungsi eksekusi memanggil SumoPod AI dan memposting ke Telegram"""
    print(f"\n[PROMOTION AGENT] Menulis konten promosi untuk fase: {phase} ({campaign_name})")
    
    system_prompt, user_prompt = get_promotion_prompt(phase, campaign_name, product, normal_price, promo_price, extra_rules)
    
    # 1. Panggil API AI
    post_text = generate_completion(system_prompt, user_prompt)
    
    # 2. Posting ke Telegram
    try:
        await client.send_message(TARGET_CHANNEL, post_text, parse_mode='md')
        print(f"[PROMOTION AGENT] Promosi '{phase}' berhasil diposting!")
    except Exception as e:
        print(f"[PROMOTION AGENT] Error posting promosi: {e}")


# --- KUMPULAN PENJADWALAN CAMPAIGN (SCHEDULER) ---

def setup_promotion_agent(client):
    """Mendaftarkan jadwal otomatis Promotion Agent"""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    
    # === CAMPAIGN: WEEKEND VIP PROMO ===
    # Start: Friday, End: Sunday
    weekend_args = [
        client, 
        "", # Phase diisi di bawah
        "Weekend VIP Promo", 
        "Goldzonfire VIP Monthly", 
        "Rp1.500.000", 
        "Rp975.000",
        "Periode: Jumat sampai Minggu."
    ]
    
    # 1. Announcement (Jumat Jam 16:00 WIB)
    announcement_args = weekend_args.copy()
    announcement_args[1] = "Announcement (Baru dimulai hari Jumat)"
    scheduler.add_job(generate_and_post_promo, 'cron', day_of_week='fri', hour=16, minute=0, args=announcement_args)
    
    # 2. Reminder (Sabtu Jam 13:00 WIB)
    reminder_args = weekend_args.copy()
    reminder_args[1] = "Reminder (Mengingatkan di hari Sabtu)"
    scheduler.add_job(generate_and_post_promo, 'cron', day_of_week='sat', hour=13, minute=0, args=reminder_args)
    
    # 3. Last Day (Minggu Jam 10:00 WIB)
    lastday_args = weekend_args.copy()
    lastday_args[1] = "Last Day (Mengingatkan ini hari terakhir)"
    scheduler.add_job(generate_and_post_promo, 'cron', day_of_week='sun', hour=10, minute=0, args=lastday_args)
    
    # 4. Campaign End (Minggu Jam 20:00 WIB)
    end_args = weekend_args.copy()
    end_args[1] = "Campaign End (Kesempatan terakhir, tinggal beberapa jam/menit lagi tutup)"
    scheduler.add_job(generate_and_post_promo, 'cron', day_of_week='sun', hour=20, minute=0, args=end_args)

    scheduler.start()
    print("✅ Promotion Agent Scheduler berhasil diaktifkan!")

# === FUNGSI MANUAL (UNTUK VERCEL) ===
async def manual_trigger_campaign(client, campaign_type, product, normal_price, promo_price, urgency):
    """Fungsi ini bisa dieksekusi sewaktu-waktu (Flash Promo / Copy Trade Promo) melalui API Vercel"""
    await generate_and_post_promo(client, urgency, campaign_type, product, normal_price, promo_price)
