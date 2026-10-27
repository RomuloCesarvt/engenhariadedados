# Lead Recon Engine - Arquitetura e Dashboard de Reconciliação de Leads

Solução de alto nível e implementação de referência para **monitoramento, reconciliação e validação do volume de leads por origem** (Meta Ads, Google Ads, RD Station, BeeViral e BI Interno/Planilhas) versus o CRM central **Construtor de Vendas (CV)**.

## 🚀 Destaques da Solução

- **Custo Zero de Infraestrutura**: roda inteiro na **Vercel** (dashboard Next.js + API Python/FastAPI como funções serverless), com **Upstash Redis** (plano gratuito) para o estado do monitor e **GitHub Actions** para manter o monitor ativo com o dashboard fechado.
- **Algoritmo Híbrido de Reconciliação**:
  1. Match por **ID de Integração Nativo** (`gclid`, `fbclid`, `bee_id`, `rd_id`) $\rightarrow$ `MATCH_OK`.
  2. Fallback por **E-mail Sanitizado** e **Telefone (E.164)**.
  3. Detecção de atribuição incorreta ($\rightarrow$ `ORIGIN_MISMATCH`).
  4. Identificação de leads ausentes no CRM ($\rightarrow$ `MISSING_IN_CV`).
  5. Monitoramento de latência de integração ($\rightarrow$ `LATENCY_DELAY`).
- **Análise Sob Demanda**: Execução acionável via botão no Dashboard ou disparada via API/Webhook.

---

## 📁 Estrutura do Repositório

```
Engenharia de dados/
├── app.py                            # API FastAPI (Vercel): /api/reconcile, /api/monitor/*, /api/report/latest
├── vercel.json                       # Projeto do motor na Vercel (função Python + cron diário)
├── requirements.txt                  # Dependências do motor na Vercel
├── .github/
│   └── workflows/
│       ├── reconcile.yml             # Workflow GitHub Actions para execução sob demanda
│       └── monitor-tick.yml          # Avança o monitor ao vivo a cada 5 min (dashboard fechado)
├── engine/                           # Motor de Dados em Python
│   ├── config.py                     # Schemas Pydantic e Enums
│   ├── extractors/                   # Adaptadores de extração (Meta, Google, RD, BeeViral, Sheets, CV)
│   ├── normalizer.py                 # Sanitização de e-mails, telefones e taxonomia
│   ├── reconciler.py                 # Algoritmo Híbrido de Cruzamento de Leads
│   ├── pipeline.py                   # Extração + reconciliação (usado pela CLI e pela API)
│   ├── lead_monitor.py               # Ciclo do monitor ao vivo (estado serializável)
│   ├── store.py                      # Persistência do estado (Upstash Redis / memória local)
│   ├── exporter.py                   # Exportador JSON/CSV e Firebase Firestore
│   ├── main.py                       # CLI Entrypoint da análise sob demanda
│   └── tests/                        # Suite de testes com pytest
├── dashboard/                        # Web App Dashboard (Next.js 14, TailwindCSS, Lucide)
│   ├── src/app/                      # Páginas, Layout e proxy /api/engine/* para o motor
│   ├── src/components/               # Componentes UI (Navbar, Cards, Tabelas, Modal Trigger)
│   ├── src/middleware.ts             # Senha de acesso ao dashboard
│   ├── src/lib/                      # Cliente da API do motor
│   └── src/types/                    # Interfaces TypeScript
└── README.md
```

---

## 🛠️ Como Executar a Engine Python Localmente

```bash
# 1. Entre no diretório raiz do projeto
cd "c:\Users\RomuloMeloMouraLeite\.gemini\antigravity\scratch\Engenharia de dados"

# 2. Instale os requisitos (opcional)
pip install -r engine/requirements.txt

# 3. Execute o suite de testes unitários
python -m pytest engine/tests/

# 4. Rode a análise de reconciliação sob demanda
python engine/main.py --start-date 2026-07-20 --end-date 2026-07-27
```

---

## 💻 Como Rodar Tudo Localmente (API + Dashboard)

```bash
# Terminal 1 — API do motor (sem ENGINE_API_KEY definida, não exige chave)
pip install -r engine/requirements.txt
uvicorn app:app --port 8765 --reload

# Terminal 2 — Dashboard (usa ENGINE_URL=http://localhost:8765 por padrão)
cd dashboard
npm install
npm run dev
```

Acesse em seu navegador em `http://localhost:3000`. Sem credenciais de API em `engine/.env`,
o motor usa dados de demonstração (`ALLOW_SIMULATION=1`, padrão local).

---

## ☁️ Deploy na Vercel

São **dois projetos Vercel** apontando para este mesmo repositório:

| Projeto | Root Directory | Framework | Função |
| :--- | :--- | :--- | :--- |
| `engenhariadedados-engine` | `.` (raiz) | FastAPI | API Python: extração das 5 fontes + CV, reconciliação e monitor |
| `engenhariadedados` | `dashboard` | Next.js | Interface; chama o motor por um proxy no servidor |

### Variáveis de ambiente — projeto do **motor**

| Variável | Para quê |
| :--- | :--- |
| `ENGINE_API_KEY` | Chave exigida pela API (a mesma vai no dashboard). **Obrigatória**. |
| `ALLOW_SIMULATION` | `0` — impede que dados fictícios apareçam como reais. |
| `CV_CRM_URL`, `CV_CRM_EMAIL`, `CV_CRM_TOKEN` | CRM Construtor de Vendas |
| `META_ACCESS_TOKEN`, `META_PAGE_ID` | Meta Ads |
| `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID` | Google Ads (extração real ainda não implementada) |
| `RD_STATION_API_TOKEN` | RD Station |
| `BEEVIRAL_API_KEY` | BeeViral |
| `SHEETS_BI_CSV_URL` | Planilha BI (link CSV publicado) |
| `KV_REST_API_URL`, `KV_REST_API_TOKEN` | Upstash Redis — criados ao conectar a integração (veja abaixo) |

### Variáveis de ambiente — projeto do **dashboard**

`ENGINE_URL` (URL de produção do motor), `ENGINE_API_KEY` (mesma chave do motor) e
`DASHBOARD_PASSWORD` (senha de acesso; o site recusa tudo sem ela, pois exibe e-mails e telefones de leads).

### Estado do monitor ao vivo

Funções serverless não guardam memória entre chamadas. No projeto do motor, em **Storage → Create → Upstash Redis**
(plano gratuito), conecte o banco ao projeto — a Vercel injeta `KV_REST_API_URL` e `KV_REST_API_TOKEN`.
Sem o banco o monitor funciona, mas perde o histórico a cada atualização.

### Manter o monitor ativo com o dashboard fechado

O plano Hobby da Vercel só permite cron diário (`vercel.json` já tem um). Para checagens a cada 5 minutos,
cadastre em **GitHub → Settings → Secrets and variables → Actions** os secrets `ENGINE_URL` e `ENGINE_API_KEY`;
o workflow `monitor-tick.yml` faz o resto.

---

## 📊 Regras e Tipos de Divergência

| Tipo de Divergência | Significado e Diagnóstico |
| :--- | :--- |
| **`MISSING_IN_CV`** | Lead capturado na origem mas ausente no CRM Construtor de Vendas (CV). |
| **`ORIGIN_MISMATCH`** | Lead presente no CV, porém cadastrado com canal/origem incorreto. |
| **`LATENCY_DELAY`** | Lead integrado com atraso superior a 2 horas. |
| **`PENDING_SYNC`** | Lead capturado há menos de 15 minutos (janela de tolerância). |
