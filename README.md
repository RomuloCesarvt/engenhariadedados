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
- **Auditoria de Vendas (Vendas x Leads), por empreendimento**: cruza a base de vendas com a base
  de leads para provar, cliente a cliente, se as vendas declaradas como "online" realmente vieram
  de mídia digital. Cada empreendimento recebe uma conferência fechada — leads, vendas e divergências
  do produto, sem misturar obras.
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
│   ├── sales_auditor.py              # Cruzamento da base de Vendas x base de Leads
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

## 📈 BI de Leads Online e Vendas

O dashboard abre no BI: leads online, vendas, funil e qualidade dos dados por período,
empreendimento e praça — calculado sobre **bases salvas** das integrações.

### Telas

| Tela | O que responde |
| :--- | :--- |
| **Visão geral** | Quantos leads online, de que canal, quanto virou venda e o quanto dá para confiar na origem |
| **Analista** | Achados do período (alertas, oportunidades, destaques) e, na aba **Vendas online × leads**, as vendas online do mês pela regra do time Moura Leite — com a planilha do período para baixar |
| **Empreendimentos** | Cada produto com leads, canais, funil, vendas, VGV e custo por lead |
| **Funil e vendas** | Até onde os leads chegam (MQL → SAL → SQL → visita → atendimento → venda) e de onde vêm as vendas |
| **Conferências** | BeeViral × CV (cada indicação chegou? foi creditada?) e Meta/Google × CV (a plataforma diz X, o CV recebeu Y) |
| **Bases e integrações** | Estado, idade e registros de cada base, com o link para resolver credenciais |
| **Planilha de vendas** | Conferência do relatório comercial contra a base de leads |

Todo indicador é clicável e abre a **lista de leads** por trás do número, com a evidência
da classificação e o link para abrir o lead no CV — sem nome, e-mail ou telefone.

### Bases salvas (`engine/bases.py`)

Cada fonte é baixada e gravada em `output/bases/<base>.json` com data e estado. O BI lê as
bases (resposta em milissegundos) e um agendador as atualiza a cada hora enquanto a API roda.
**Uma atualização que falha nunca apaga dados bons**: a base anterior é mantida e o estado
mostra o erro e a data dos dados em uso.

### Como a origem de cada lead é classificada (`engine/taxonomy.py`)

A decisão usa a evidência mais forte disponível e registra qual foi usada:

| Ordem | Evidência | Confiança | Exemplo |
| :---: | :--- | :--- | :--- |
| 1 | UTM gravada no CV (`campos_adicionais`) | Alta | `utm_source=meta ads`, `utm_medium=ig` |
| 2 | Mídia registrada no CV | Média | `Facebook Ads`, `Instagram Ads`, `Google` |
| 3 | Tag do atendimento da IA | Baixa | `mia-organico` |
| 4 | Origem genérica do CV | Baixa | `Instagram`, `Busca Orgânica` |

Grupos: **Online — mídia paga** (Meta, Google, TikTok), **Online — orgânico** (WhatsApp
orgânico, site, chat, redes sociais, e-mail), **Indicação digital** (BeeViral),
**Offline / comercial** (painéis de corretor/imobiliária/PDV, indicação pessoal, mídia
offline) e **Não rastreado** — lead sem nenhuma evidência. "Não rastreado" nunca é somado a
um canal: aparece como indicador de qualidade de dados.

> WhatsApp é a mídia mais frequente do CV e a mais ambígua. Com UTM de anúncio, conta como o
> anúncio (Meta/Google/TikTok); com a tag `mia-organico`, como WhatsApp orgânico; sem nenhum
> dos dois, fica em "WhatsApp sem rastreio".

### Origem descoberta na RD Station (`engine/origem_rd.py`)

Boa parte dos leads entra no CV pela integração da RD **sem mídia, sem UTM e sem origem**: no
CV eles ficam em "Sem origem registrada" e somem dos indicadores de canal. A RD guarda as
conversões desses contatos, e é por elas que a origem é recuperada:

| Primeira conversão na RD | Vira |
| :--- | :--- |
| E-mail que também está num formulário da Meta, ou nome de conversão de anúncio | Campanha paga (Meta) |
| URL da primeira sessão com `gclid` ou UTM de mídia paga | Campanha paga (Google/Meta) |
| `form…`, `lp…`, `site…`, `fale-conosco` | Site / landing page |
| Disparo de WhatsApp, lista ou base importada | Remarketing do comercial (não é online) |
| Só a integração da assistente virtual, ou nada | Continua sem origem |

O resultado fica na base `origem_rd` (uma chamada por lead, em lotes por rodada) e é aplicado
na classificação do lead em todo o BI, com a evidência dizendo que veio da RD. Quando a RD
também não sabe, **nada é inventado**: o lead continua em "Sem origem registrada".

### Funil pelo histórico, não pela situação atual

A maioria dos leads está hoje "Cancelado", o que apagaria o funil. A etapa alcançada vem das
**tags e tarefas**, que acumulam a trajetória: `Tentativa de Contato (SAL)`,
`Lead Oportunidade (SQL)`, tarefa `Visita agendada`, `Atendimento Realizado` e a data da venda.

### Datas

Leads são contados pela **data de cadastro**; vendas, pela **data da venda**. A conversão por
coorte (leads do período que já viraram venda) é mostrada separada e com aviso quando o período
é recente demais para ter amadurecido.

### Meta e Google por conta de anúncio

Cada conta de anúncio corresponde a um empreendimento (`ML - Jardim dos Ipês III`,
`ML - Central Parque Avaré 2`...). O investimento e os leads que a plataforma reporta são
atribuídos ao empreendimento pelo **nome da conta**, e comparados com os leads classificados
como Meta/Google no CV — daí saem o percentual que chegou ao CRM e o **custo por lead real**.

---

## 🔌 Integrações e Credenciais

**Regra do sistema: dado simulado nunca se passa por real.** Cada fonte registra, em toda
análise, se entregou dados reais, se falhou ou se não está configurada — e o motivo. Uma
integração com problema aparece como erro, com o link direto para resolver; ela só é trocada
por dados fictícios com `ALLOW_SIMULATED_DATA=true` (modo demonstração), e mesmo assim o
dashboard exibe o aviso de dados simulados.

O estado de cada integração aparece na tela **Integrações** do dashboard (com o botão
*Testar integrações agora*), no resumo da CLI e no campo `sources` do relatório.

| Integração | O que é lido | Onde obter a credencial |
| :--- | :--- | :--- |
| **CV CRM — Empreendimentos** | Catálogo oficial (`/api/cvio/empreendimento`) | Painel do CV → `https://SUAEMPRESA.cvcrm.com.br/gestor` |
| **CV CRM — Leads** | Leads (`/api/cvio/lead`) — exige `CV_CRM_EMAIL` | Idem; e-mail do usuário dono do token |
| **Base de Vendas** | Reservas (`/api/cvio/reserva`) ou planilha carregada no dashboard | Permissão de Reservas no token do CV |
| **BeeViral** | Indicações (API v2, paginada) e o campo *Empreendimento de interesse* | https://account.beeviral.app/ |
| **Meta Ads** | Formulários da página → leads de cada formulário | Token permanente: https://business.facebook.com/settings/system-users |
| **RD Station** | Contatos de uma segmentação (OAuth2 com renovação) | App e client_id: https://appstore.rdstation.com/pt-BR/publisher |
| **Google Ads** | Formulários de lead (`lead_form_submission_data`) | Developer token: https://ads.google.com/aw/apicenter · OAuth: https://console.cloud.google.com/apis/credentials · Refresh token: https://developers.google.com/oauthplayground/ |
| **Planilhas BI** *(opcional)* | Leads presenciais | `SHEETS_BI_FILE_PATH` |
| **Firebase** *(opcional)* | Histórico na nuvem | https://console.firebase.google.com/ |

A lista completa de variáveis, com os links, está em [`engine/.env.example`](engine/.env.example).

### Empreendimentos com os nomes oficiais do CV

O CV nomeia os empreendimentos como `Cidade - Nome - Código`
(ex.: `Avaré - Central Parque II - 13900`). Todo nome livre — de planilha, campanha ou campo
de formulário — é convertido para esse nome oficial antes da conferência:

- a **cidade desempata** homônimos (`Novo Horizonte` existe em Cerqueira César e Itatinga);
- **etapa em algarismo equivale ao romano** (`Central Parque Avaré 2` → `Central Parque II`);
- **abreviações** são expandidas (`Jd. dos Ipês III` → `Jardim dos Ipês III`);
- respostas como `Outros empreendimentos` **não viram produto** — o lead fica sem empreendimento.

### Janela de leads da auditoria de vendas

Uma venda do período pode ter vindo de um lead captado meses antes. Por isso a análise busca
leads desde a venda mais antiga menos a janela de atribuição (180 dias por padrão); a
reconciliação de leads x CV continua usando apenas o período escolhido.

### Quando o CV não pode ser lido

Sem os leads do CV não há como afirmar que um lead "faltou" no CRM. Nessa situação nenhum
lead é marcado como `MISSING_IN_CV`, o relatório sai com `cv_available: false` e as telas de
diagnóstico explicam o motivo em vez de mostrar percentuais.

### API da Engine

```bash
# a partir da raiz do repositório
uvicorn engine.api:app --port 8001
```

| Endpoint | Descrição |
| :--- | :--- |
| `GET /api/integrations` | Estado das integrações na última análise (`?live=true` testa cada API agora) |
| `GET /api/analista/vendas-online` | A última análise gravada do período (vendas × leads online, casos e resumo por produto) |
| `POST /api/analista/vendas-online` | Refaz a análise do período e gera a planilha, em segundo plano |
| `GET /api/analista/vendas-online/relatorio` | Baixa a planilha do período (`.xlsx`) |
| `GET /api/analista/origem-rd` | Quantos leads sem origem no CV já tiveram a origem recuperada na RD |
| `POST /api/sales/upload` | Recebe a planilha de vendas (CSV/XLSX) |
| `GET /api/sales/upload/latest` | Dados da planilha de vendas carregada mais recentemente |

---

## 💻 Como Rodar o Dashboard Web Localmente

```bash
# 1. Entre no diretório do dashboard
cd dashboard

# 2. Instale as dependências
npm install

# 3. Inicie o servidor de desenvolvimento na porta reservada do BI
npm run dev
```

Acesse sempre em `http://127.0.0.1:3001`. O endereço explícito evita que `localhost` tente conectar por IPv6 (`::1`), já que o servidor local escuta em IPv4 (`127.0.0.1`).

No Windows, tambem e possivel abrir `Abrir BI Moura Leite.cmd` na raiz do projeto. O inicializador sobe a engine em `127.0.0.1:8001`, sobe o dashboard em `127.0.0.1:3001` e abre o navegador. Antes de iniciar, ele verifica a identidade dos dois servicos e interrompe com uma mensagem clara se outro sistema estiver usando uma das portas. Assim, o BI nunca migra silenciosamente para outra porta nem exibe outro projeto no mesmo endereco.

---

## 📊 Regras e Tipos de Divergência

| Tipo de Divergência | Significado e Diagnóstico |
| :--- | :--- |
| **`MISSING_IN_CV`** | Lead capturado na origem mas ausente no CRM Construtor de Vendas (CV). |
| **`ORIGIN_MISMATCH`** | Lead presente no CV, porém cadastrado com canal/origem incorreto. |
| **`LATENCY_DELAY`** | Lead integrado com atraso superior a 2 horas. |
| **`PENDING_SYNC`** | Lead capturado há menos de 15 minutos (janela de tolerância). |


---

## 🧭 Duas análises de venda, duas perguntas

| | Vendas × leads | Analista → Vendas online × leads |
| :--- | :--- | :--- |
| Pergunta | Há **algum sinal** de que essa pessoa veio do digital? | Quais vendas **são venda online**? |
| Uso | Varredura do dia a dia, venda a venda, incluindo pistas fracas | Fechamento do mês, que vira a planilha da gestão |
| Régua | Sinais de todas as bases, separados por força da evidência | Quem vendeu (time Moura Leite) + lead online na janela ou Vendas SDR |

> **"Contam como online" (Vendas × leads) é só o lead vinculado à reserva.** Quando o lead online
> da pessoa existe mas a reserva não está vinculada a lead nenhum, a venda aparece em **"Online
> sem o lead vinculado"**.

---

## 🗓️ Vendas online — o relatório mensal (`engine/vendas_online.py`)

**Regra:** é venda online a venda feita pelo **time Moura Leite** (especialistas e corretores do
time, lista em `TIME_MOURA_LEITE`) em que o cliente tem **lead online na janela** ou que está
registrada como **Vendas SDR**.

Se o cliente veio do online mas **comprou com outro corretor**, o mérito é do corretor: a venda não
conta como online e aparece à parte ("Lead online, venda por outro corretor"), com o histórico do
lead — atendimento do SDR ou da assistente, registro do corretor antes da conversão — e uma coluna
para a avaliação conjunta de SDR e comercial. O CV não mostra o atendimento feito fora dele, por
isso esses casos não são julgados automaticamente.

**Como cada venda é lida**

1. **Quem comprou** — titular e demais associados da reserva, lidos do CV venda a venda.
2. **Quais leads são dessa pessoa** — cruzamento com todos os leads do CV por quatro chaves:
   lead vinculado à reserva, e-mail, telefone (DDD + 8 dígitos, só com nome compatível) e nome
   completo único na base.
3. **Origem do lead** — a do CV e, quando o CV não tem, a descoberta na RD Station. Cadastro
   manual de corretor, disparo de WhatsApp e ativação da base não são lead online.
4. **Janela** — conversão nos 90 dias antes da venda; na safra de um lançamento (até 90 dias
   depois da primeira venda), desde o início da pré-campanha. Lançamento e pré-campanha são lidos
   dos dados (primeira venda do produto e o mês em que a captação dispara).

Vendas **distratadas depois continuam na análise** (estavam vendidas na data da venda).

**A planilha** (`engine/relatorio_vendas.py`): *Leia primeiro*, *Resumo por produto*, *Vendas
online*, *Lead online, outro corretor*, *Por corretor do time*, *Todas as vendas* e *Como foi
feito*. Todo número dos quadros é fórmula sobre *Todas as vendas*, e nenhum texto vindo dos dados
entra no Excel como fórmula.

**Cache**: compradores das reservas, pré-cadastros e histórico dos leads ficam em
`output/analises/`. A primeira análise de um período lê o CV; as seguintes são instantâneas.

---

## 🧾 Auditoria de Vendas — "o online foi mesmo 3?"

O relatório comercial informa o total de vendas e quantas vieram do online — por exemplo,
**5 vendas, 3 online**. Esse número é uma *declaração*: depende do corretor ter marcado a
origem certa na hora do cadastro. O módulo de auditoria ignora essa declaração na hora de
contar e **refaz a atribuição do zero**, procurando cada comprador na base unificada de leads
(Meta Ads, Google Ads, RD Station, BeeViral, Planilhas e CV CRM).

### Como cada venda é cruzada

A busca do comprador na base de leads segue uma hierarquia de chaves, da mais forte para a mais fraca:

| Ordem | Chave | Observação |
| :---: | :--- | :--- |
| 1 | **CPF/CNPJ** | Chave mais confiável; comparada apenas por dígitos. |
| 2 | **ID de integração** | `gclid`, `fbclid`, `bee_id`, `rd_id`. |
| 3 | **E-mail** | Sanitizado e validado. |
| 4 | **Telefone** | Normalizado para E.164 (DDI 55). |
| 5 | **Nome** | Sem acentos e sem pontuação. Confiança baixa — sempre sinalizado no relatório. |

Duas regras temporais evitam atribuição falsa:

- O lead precisa ter sido criado **antes da venda** (tolerância de 24h para cadastro retroativo).
- O lead precisa estar dentro da **janela de atribuição** (padrão de 180 dias, ajustável).

Quando vários leads batem com o mesmo comprador, vence o de canal digital, depois o de chave
mais forte, depois o da própria plataforma de mídia e, por fim, o mais recente.

### Vereditos possíveis

| Veredito | Significado |
| :--- | :--- |
| **`ONLINE_CONFIRMED`** | Declarada online e com lead digital anterior — confirmada. |
| **`ONLINE_UNPROVEN`** | Declarada online, sem nenhum lead digital — **infla o online do relatório**. |
| **`ONLINE_NOT_DECLARED`** | Declarada offline, mas o comprador tem lead digital — **online subnotificado**. |
| **`OFFLINE_CONFIRMED`** | Declarada offline e sem lead digital — coerente. |
| **`CHANNEL_MISMATCH`** | Online confirmado, porém creditado ao canal errado. |
| **`LEAD_AFTER_SALE`** | O único lead do comprador foi criado depois da venda — não comprova origem. |

> **Atenção ao total que "bate".** O online declarado pode empatar com o comprovado e ainda assim
> estar errado: um falso online e um online não declarado se anulam no total. Por isso o relatório
> traz também a **acurácia da atribuição** — o percentual de vendas cuja origem declarada bate
> integralmente com a comprovada.

### De onde vem a base de vendas

A extração tenta, nesta ordem:

1. **API do CV CRM** — `GET /api/v1/comercial/reservas`, com as mesmas credenciais da reconciliação.
2. **Planilha local** — CSV ou XLSX apontado por `SALES_FILE_PATH` ou por `--sales-file`.
   Cabeçalhos reconhecidos: `cliente`/`nome_cliente`, `cpf`, `email`, `telefone`, `origem`,
   `data_venda`, `valor`, `empreendimento`, `unidade`.
3. **Simulação**, para demonstrar a tela sem credenciais.

### Conferência por empreendimento

Somar tudo esconde justamente o erro que se quer achar: um empreendimento com online inflado
e outro com online subnotificado se anulam no total da incorporadora. Por isso **o relatório
nunca entrega só o consolidado** — cada produto recebe seu próprio fechamento:

```
🏗️  CONFERÊNCIA POR EMPREENDIMENTO
  !! Residencial Sol: 8 leads | 3 vendas | online 2 declarado x 2 comprovado | conversão 37.5%
       - 1 venda(s) declarada(s) como online sem nenhum lead digital na base
       - 1 venda(s) marcada(s) como offline vieram de mídia digital
  !! Condomínio Horizonte: 7 leads | 2 vendas | online 1 declarado x 1 comprovado | conversão 28.6%
       - 1 venda(s) cujo comprador entrou por campanha de OUTRO empreendimento
```

Por empreendimento o relatório traz: leads captados (abertos por canal), leads no CV, vendas,
VGV, online declarado x comprovado, taxa de conversão lead→venda, acurácia da atribuição e a
lista de inconsistências em texto corrido, pronta para levar à reunião.

#### Como o empreendimento de cada registro é descoberto

| Base | Origem da informação |
| :--- | :--- |
| **Vendas** | Coluna `empreendimento` / `produto` da reserva ou da planilha. |
| **Leads do CV** | Campo do próprio CRM. |
| **Leads de mídia** | Campo explícito quando existe; senão, o nome do empreendimento citado **no nome da campanha**. |

O catálogo de nomes oficiais nasce das vendas e do CRM — são eles que permitem reconhecer
`"Search - Residencial Sol - Apartamentos SP"` como o empreendimento *Residencial Sol*.
A comparação ignora acentos, pontuação e palavras genéricas (`residencial`, `condomínio`,
`torre`, `jardim`...), de modo que `"Res. Vista Mar"` casa com `"Campanha Vista Mar 2026"`.
Quando dois empreendimentos disputam o mesmo texto, **nenhum é atribuído** — errar o produto
é pior do que deixar em branco.

Leads cujo produto não pôde ser identificado são contados à parte (`leads_sem_empreendimento`)
e seguem valendo como prova de origem de uma venda; apenas não entram na contagem por produto.
Esse número é, em si, um diagnóstico: campanha que não nomeia o empreendimento impede a
conferência por obra.

#### Cliente que migra de produto

É comum o comprador entrar por uma campanha e fechar em outro empreendimento. Nesse caso a
venda **continua contando como online** — o lead veio de mídia paga, isso é fato — mas é
marcada como `cross_empreendimento`, porque a verba que gerou o lead foi investida em outra
obra. O relatório mostra quantas vendas estão nessa situação para que o crédito seja lançado
no produto certo.

### Como rodar

```bash
# Auditoria junto com a reconciliação de leads (padrão)
python engine/main.py --start-date 2026-07-20 --end-date 2026-08-05

# Auditando uma planilha de vendas exportada do BI
python engine/main.py --sales-file "C:/caminho/vendas_julho.xlsx"

# Ajustando a janela de atribuição (ciclo de venda mais longo)
python engine/main.py --attribution-window 365

# Conferindo apenas um empreendimento
python engine/main.py --empreendimento "Residencial Sol"

# Descobrindo quais empreendimentos existem nas bases
python engine/main.py --listar-empreendimentos

# Pulando o cruzamento de vendas
python engine/main.py --skip-sales-audit
```

> O filtro `--empreendimento` restringe as **vendas** conferidas, mas mantém os leads de todos
> os produtos disponíveis para match — senão um comprador que entrou por outra campanha viraria
> falsamente uma "venda sem lead".

Saídas geradas: o bloco `sales_audit` dentro de `output/latest_report.json` e a planilha
`output/latest_sales_audit.csv` (uma linha por venda, com veredito e evidência).
No Dashboard, a tela **Auditar Vendas** abre com o seletor de empreendimento: a aba *Consolidado*
dá o panorama e o quadro comparativo de todos os produtos, e cada empreendimento abre sua própria
conferência — leads por canal, declarado x comprovado, inconsistências e a lista venda a venda,
com exportação em CSV.

### Endpoints

| Endpoint | Descrição |
| :--- | :--- |
| `POST /api/reconcile` | Reconciliação + auditoria de vendas. Aceita `salesFile`, `attributionWindowDays` e `skipSalesAudit`. |
| `GET /api/sales-audit/latest` | Apenas o bloco de auditoria de vendas do relatório mais recente. |
| `GET /api/empreendimentos` | Empreendimentos do relatório mais recente, com leads, vendas e situação. |
