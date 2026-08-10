"""
Teste de conectividade ao vivo de TODAS as APIs configuradas.
Verifica quais estão funcionando e quais estão falhando.
"""
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import httpx

print("=" * 70)
print("🔍 DIAGNÓSTICO AO VIVO DE TODAS AS APIs")
print("=" * 70)

results = {}

# ━━━ 1. CRM CONSTRUTOR DE VENDAS (CV) ━━━
print("\n[1/5] 🏢 CRM CONSTRUTOR DE VENDAS (CV)...")
cv_url = os.getenv("CV_CRM_URL", "")
cv_token = os.getenv("CV_CRM_TOKEN", "")
cv_email = os.getenv("CV_CRM_EMAIL", "")
print(f"  URL: {cv_url}")
print(f"  Token: {cv_token[:10]}..." if cv_token else "  Token: VAZIO")

if cv_url and cv_token and cv_token != "seu_token_cv_aqui":
    base = cv_url.rstrip("/")
    # Tenta diferentes endpoints comuns do CV
    endpoints = [
        f"{base}/api/v2/leads",
        f"{base}/api/v1/leads",
        f"{base}/api/leads",
        f"{base}/api/v2/empreendimentos",
    ]
    headers = {"token": cv_token, "Content-Type": "application/json"}
    if cv_email:
        headers["email"] = cv_email
    
    for endpoint in endpoints:
        try:
            r = httpx.get(endpoint, headers=headers, params={"limite": 1}, timeout=15)
            status = r.status_code
            body_preview = r.text[:300]
            print(f"  → {endpoint}")
            print(f"    Status: {status}")
            print(f"    Body: {body_preview}")
            if status == 200:
                results["cv_crm"] = {"status": "OK", "endpoint": endpoint}
                break
        except Exception as e:
            print(f"  → {endpoint} → ERRO: {e}")
    if "cv_crm" not in results:
        results["cv_crm"] = {"status": "FALHOU", "detalhe": "Nenhum endpoint respondeu 200"}
else:
    results["cv_crm"] = {"status": "NÃO CONFIGURADO"}
    print("  ⚠️  Credenciais de placeholder ou vazias")

# ━━━ 2. META ADS ━━━
print("\n[2/5] 📘 META ADS (Facebook/Instagram)...")
meta_token = os.getenv("META_ACCESS_TOKEN", "")
meta_page = os.getenv("META_PAGE_ID", "me")
print(f"  Token: {meta_token[:15]}..." if meta_token else "  Token: VAZIO")
print(f"  Page ID: {meta_page}")

if meta_token:
    try:
        # Primeiro verifica se o token é válido
        r = httpx.get(
            "https://graph.facebook.com/v18.0/me",
            params={"access_token": meta_token, "fields": "id,name"},
            timeout=10
        )
        print(f"  → /me Status: {r.status_code}")
        print(f"  → Body: {r.text[:300]}")
        if r.status_code == 200:
            me_data = r.json()
            results["meta_ads"] = {"status": "TOKEN_VALIDO", "nome": me_data.get("name"), "id": me_data.get("id")}
            
            # Tenta buscar pages
            r2 = httpx.get(
                "https://graph.facebook.com/v18.0/me/accounts",
                params={"access_token": meta_token},
                timeout=10
            )
            print(f"  → /me/accounts Status: {r2.status_code}")
            print(f"  → Body: {r2.text[:300]}")
        else:
            results["meta_ads"] = {"status": "TOKEN_INVALIDO", "erro": r.text[:200]}
    except Exception as e:
        results["meta_ads"] = {"status": "ERRO", "detalhe": str(e)}
        print(f"  → ERRO: {e}")
else:
    results["meta_ads"] = {"status": "NÃO CONFIGURADO"}

# ━━━ 3. RD STATION ━━━
print("\n[3/5] 💜 RD STATION MARKETING...")
rd_token = os.getenv("RD_STATION_API_TOKEN", "")
print(f"  Token: {rd_token[:10]}..." if rd_token else "  Token: VAZIO")

if rd_token:
    try:
        headers = {"Authorization": f"Bearer {rd_token}", "Accept": "application/json"}
        # Testa endpoint de conversions
        r = httpx.get("https://api.rdstation.com/platform/conversions", headers=headers, timeout=10)
        print(f"  → /platform/conversions Status: {r.status_code}")
        print(f"  → Body: {r.text[:300]}")
        
        # Tenta também contacts
        r2 = httpx.get("https://api.rdstation.com/platform/contacts", headers=headers, timeout=10)
        print(f"  → /platform/contacts Status: {r2.status_code}")
        print(f"  → Body: {r2.text[:300]}")
        
        results["rd_station"] = {"status": "OK" if r.status_code == 200 or r2.status_code == 200 else f"HTTP_{r.status_code}"}
    except Exception as e:
        results["rd_station"] = {"status": "ERRO", "detalhe": str(e)}
        print(f"  → ERRO: {e}")
else:
    results["rd_station"] = {"status": "NÃO CONFIGURADO"}

# ━━━ 4. BEEVIRAL ━━━
print("\n[4/5] 🐝 BEEVIRAL (Indicação)...")
bee_key = os.getenv("BEEVIRAL_API_KEY", "")
print(f"  Key: {bee_key[:15]}..." if bee_key else "  Key: VAZIA")

if bee_key:
    # Testa múltiplas URLs possíveis
    bee_urls = [
        "https://api.beeviral.app/v1/referrals",
        "https://api.beeviral.com.br/api/v1/indicacoes",
        "https://api.beeviral.com.br/api/v1/leads",
        "https://api.beeviral.com.br/api/v1/referrals",
    ]
    for url in bee_urls:
        try:
            headers = {"Authorization": f"Bearer {bee_key}", "token": bee_key, "Accept": "application/json"}
            r = httpx.get(url, headers=headers, timeout=10)
            print(f"  → {url} Status: {r.status_code} Body: {r.text[:200]}")
            if r.status_code == 200:
                results["beeviral"] = {"status": "OK", "endpoint": url}
                break
        except Exception as e:
            print(f"  → {url} ERRO: {e}")
    if "beeviral" not in results:
        results["beeviral"] = {"status": "FALHOU", "detalhe": "Nenhum endpoint respondeu 200"}
else:
    results["beeviral"] = {"status": "NÃO CONFIGURADO"}

# ━━━ 5. GOOGLE ADS ━━━
print("\n[5/5] 🟢 GOOGLE ADS...")
gads_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
gads_customer = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
print(f"  Developer Token: {gads_token[:10]}..." if gads_token else "  Developer Token: VAZIO")
print(f"  Customer ID: {gads_customer}")

if gads_customer == "1234567890":
    results["google_ads"] = {"status": "PLACEHOLDER", "detalhe": "Customer ID é placeholder 1234567890"}
    print("  ⚠️  Customer ID é placeholder (1234567890)")
elif gads_token:
    results["google_ads"] = {"status": "TOKEN_PRESENTE", "detalhe": "Mas o extrator não faz chamada HTTP real — precisa implementar"}
else:
    results["google_ads"] = {"status": "NÃO CONFIGURADO"}

# ━━━ FIREBASE ━━━
print("\n[EXTRA] 🔥 FIREBASE FIRESTORE...")
fb_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
print(f"  Credentials Path: {fb_path or 'NÃO CONFIGURADO'}")
if fb_path and os.path.exists(fb_path):
    results["firebase"] = {"status": "ARQUIVO_ENCONTRADO"}
else:
    results["firebase"] = {"status": "NÃO CONFIGURADO"}
    print("  ⚠️  Sem arquivo de credenciais do Firebase")

# ━━━ RESUMO FINAL ━━━
print("\n" + "=" * 70)
print("📊 RESUMO DO DIAGNÓSTICO")
print("=" * 70)
for api, info in results.items():
    status = info.get("status", "?")
    emoji = "✅" if status == "OK" or status == "TOKEN_VALIDO" else "⚠️" if "PLACEHOLDER" in status or "PRESENTE" in status else "❌"
    print(f"  {emoji} {api.upper():20s} → {status}")
    for k, v in info.items():
        if k != "status":
            print(f"     {k}: {v}")
print("=" * 70)
