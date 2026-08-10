import os
import sys
import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

beeviral_key = os.getenv("BEEVIRAL_API_KEY")
routes = [
    "https://api.beeviral.com.br/api/v1/indicacoes",
    "https://api.beeviral.com.br/api/v1/leads",
    "https://api.beeviral.com.br/api/v1/referrals",
    "https://api.beeviral.com.br/api/v1/campanhas",
    "https://api.beeviral.com.br/api/indicacoes",
]

print("=== TESTANDO ROTAS DO BEEVIRAL ===")
for url in routes:
    try:
        headers = {"Authorization": f"Bearer {beeviral_key}", "token": beeviral_key, "Accept": "application/json"}
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"URL: {url} -> Status: {r.status_code} | Body: {r.text[:150]}")
    except Exception as e:
        print(f"URL: {url} -> Erro: {e}")
