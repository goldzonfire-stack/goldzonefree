import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
# Kita menggunakan Service Role Key agar Agent bisa melakukan operasi baca/tulis tanpa RLS constraints (karena agent bertindak sebagai backend/admin)
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") 

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL dan Key harus diset di .env")

# Inisialisasi Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
