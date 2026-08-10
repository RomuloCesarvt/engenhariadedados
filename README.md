# Lead Recon Engine - Arquitetura e Dashboard de Reconciliação de Leads

Solução de alto nível e implementação de referência para **monitoramento, reconciliação e validação do volume de leads por origem** (Meta Ads, Google Ads, RD Station, BeeViral e BI Interno/Planilhas) versus o CRM central **Construtor de Vendas (CV)**.

## 🚀 Destaques da Solução

- **Custo Zero de Infraestrutura**: Desenvolvida para rodar com **GitHub Actions** (compute sob demanda em Python), **Firebase Firestore** (plano gratuito serverless) e **Vercel** (hospedagem do Dashboard em Next.js).
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
├── .github/
│   └── workflows/
│       └── reconcile.yml             # Workflow GitHub Actions para execução sob demanda
├── engine/                           # Motor de Dados em Python
│   ├── config.py                     # Schemas Pydantic e Enums
│   ├── extractors/                   # Adaptadores de extração (Meta, Google, RD, BeeViral, Sheets, CV)
│   ├── normalizer.py                 # Sanitização de e-mails, telefones e taxonomia
│   ├── reconciler.py                 # Algoritmo Híbrido de Cruzamento de Leads
│   ├── exporter.py                   # Exportador JSON/CSV e Firebase Firestore
│   ├── main.py                       # CLI Entrypoint da análise sob demanda
│   └── tests/                        # Suite de testes com pytest
├── dashboard/                        # Web App Dashboard (Next.js 14, TailwindCSS, Lucide)
│   ├── src/app/                      # Páginas e Layout
│   ├── src/components/               # Componentes UI (Navbar, Cards, Tabelas, Modal Trigger)
│   ├── src/lib/                      # Serviços de dados
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

## 💻 Como Rodar o Dashboard Web Localmente

```bash
# 1. Entre no diretório do dashboard
cd dashboard

# 2. Instale as dependências
npm install

# 3. Inicie o servidor de desenvolvimento
npm run dev
```

Acesse em seu navegador em `http://localhost:3000`.

---

## 📊 Regras e Tipos de Divergência

| Tipo de Divergência | Significado e Diagnóstico |
| :--- | :--- |
| **`MISSING_IN_CV`** | Lead capturado na origem mas ausente no CRM Construtor de Vendas (CV). |
| **`ORIGIN_MISMATCH`** | Lead presente no CV, porém cadastrado com canal/origem incorreto. |
| **`LATENCY_DELAY`** | Lead integrado com atraso superior a 2 horas. |
| **`PENDING_SYNC`** | Lead capturado há menos de 15 minutos (janela de tolerância). |
