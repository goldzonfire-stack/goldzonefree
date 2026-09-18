import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

AI_API_KEY = os.environ.get("AI_API_KEY")
AI_BASE_URL = os.environ.get("AI_BASE_URL")

if not AI_API_KEY or not AI_BASE_URL:
    raise ValueError("AI_API_KEY dan AI_BASE_URL harus diset di .env")

# Inisialisasi client OpenAI dengan SumoPod AI endpoint
ai_client = OpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL
)

def generate_completion(system_prompt: str, user_message: str, model="gpt-4o", temperature=0.7) -> str:
    """Fungsi helper dasar untuk memanggil AI."""
    response = ai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=1500,
        temperature=temperature
    )
    return response.choices[0].message.content
