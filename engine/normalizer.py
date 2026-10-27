"""
Módulo de Normalização e Sanitização de Leads (E-mails, Telefones, Datas e Taxonomia).
"""

import re
import unicodedata
from functools import lru_cache
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from engine.config import OriginChannel, LeadRecord, CVLeadRecord, SaleRecord


def clean_email(email: Optional[str]) -> Optional[str]:
    if not email or not isinstance(email, str):
        return None
    email_clean = email.strip().lower()
    # Validação simples de sintaxe de email
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_clean):
        return email_clean
    return None


def clean_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    # Extrai apenas dígitos
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return None
    # Se tiver 10 ou 11 dígitos (BR sem DDI), adiciona 55
    if len(digits) in (10, 11):
        return f"55{digits}"
    # Se já tiver 12 ou 13 dígitos começando com 55
    if len(digits) in (12, 13) and digits.startswith("55"):
        return digits
    return digits


def normalize_channel_alias(channel_raw: str) -> OriginChannel:
    ch = str(channel_raw).strip().lower().replace(" ", "_")
    if ch in ["meta", "facebook", "instagram", "fb", "meta_ads", "facebook_ads"]:
        return OriginChannel.META_ADS
    elif ch in ["google", "google_ads", "gads", "adwords"]:
        return OriginChannel.GOOGLE_ADS
    elif ch in ["rd", "rd_station", "rdstation", "rd_marketing"]:
        return OriginChannel.RD_STATION
    elif ch in ["beeviral", "bee", "indicação", "indicacao"]:
        return OriginChannel.BEEVIRAL
    elif ch in ["sheets", "planilha", "bi", "bi_interno", "excel", "estande_vendas", "feirão_imobiliário"]:
        return OriginChannel.SHEETS_BI
    elif ch in ["cv", "cv_crm", "construtor_de_vendas"]:
        return OriginChannel.CV_CRM

    # Textos livres de mídia do CV: "Instagram Ads", "pesquisa / cpc | altavista", "ig"
    texto = unicodedata.normalize("NFKD", str(channel_raw)).encode("ascii", "ignore").decode().lower()
    tokens = set(re.split(r"[^a-z0-9]+", texto))
    if any(p in texto for p in ("facebook", "instagram", "meta")) or tokens & {"fb", "ig"}:
        return OriginChannel.META_ADS
    if any(p in texto for p in ("google", "adwords", "pesquisa")) or tokens & {"gads"}:
        return OriginChannel.GOOGLE_ADS
    if any(p in texto for p in ("rd station", "rdstation", "rd_station")):
        return OriginChannel.RD_STATION
    if "beeviral" in texto or "indica" in texto:
        return OriginChannel.BEEVIRAL
    return OriginChannel.SHEETS_BI


def parse_datetime(dt_val: Any) -> datetime:
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        try:
            # Tenta ISO 8601
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            pass
        # Tenta formatos comuns no Brasil
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(dt_val, fmt)
            except ValueError:
                continue
    return datetime.now(timezone.utc)


# Palavras genéricas em nome de empreendimento: não distinguem um produto do outro.
EMPREENDIMENTO_STOPWORDS = {
    "residencial", "condominio", "edificio", "ed", "res", "cond", "empreendimento",
    "empreendimentos", "lancamento", "obra", "fase", "loteamento", "parceria",
    "do", "da", "de", "dos", "das", "o", "a", "e", "em",
}

# Numerais romanos diferenciam etapas ("Central Parque" x "Central Parque II").
ROMANOS = {"ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}

# Etapa escrita em algarismo equivale ao romano: "Central Parque Avaré 2" = "Central Parque II".
# Só vale para números curtos — códigos como "13700" continuam ignorados.
ALGARISMO_ROMANO = {"2": "ii", "3": "iii", "4": "iv", "5": "v", "6": "vi", "7": "vii", "8": "viii", "9": "ix", "10": "x"}

# Respostas de formulário que não apontam produto nenhum
EMPREENDIMENTO_GENERICO_TOKENS = {"outros", "outro", "outras", "nenhum", "todos", "qualquer", "nao", "sei", "definido", "indefinido"}

# Abreviações comuns em planilhas e formulários ("Jd. dos Ipês III")
ABREVIACOES = {"jd": "jardim", "jdm": "jardim", "pq": "parque", "vl": "vila", "sta": "santa", "sto": "santo"}

# Rótulo usado quando não dá para dizer a que empreendimento o registro pertence.
EMPREENDIMENTO_DESCONHECIDO = "Não identificado"


# Produtos que a Moura Leite analisa como um só empreendimento: trecho do nome -> nome oficial exibido
EMPREENDIMENTOS_UNIFICADOS = {
    "mirante dos ramos": "Tatuí - Reserva dos Ramos Residencial - 14704",
}


def unificar_empreendimento(name):
    """Troca o nome pelo empreendimento unificado (ex.: Mirante dos Ramos conta como Reserva dos Ramos)."""
    chave = normalize_empreendimento(name) or ""
    for trecho, destino in EMPREENDIMENTOS_UNIFICADOS.items():
        if trecho in chave:
            return destino
    return name


def normalize_empreendimento(name):
    """Chave de comparação de empreendimento: sem acento, minúsculo, sem pontuação."""
    if not name:
        return None
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9 ]", " ", text).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


# Como cada equipe escreve o produto fora do CV (contas de anúncio, campanhas, planilhas).
# Só entra aqui o apelido que identifica UM produto: as contas "Avaré 2 - Central" e
# "Avaré 2 - Reserva", por exemplo, rodam a mesma campanha da cidade e anunciam os dois produtos.
APELIDOS = (
    (r"\balta vista\b", "altavista"),
    # Campanha "reserva-2_google-pmax_black-friday": é o Reserva Central Parque II, em Avaré
    (r"\breserva 2\b", "reserva central parque ii avare"),
)


def cidades_do_catalogo(catalogo):
    """(cidade sem acento, cidade como está no CV), da maior para a menor: 'Avaré' antes de 'Itu'."""
    cidades = {str(e).split(" - ")[0].strip() for e in catalogo if " - " in str(e)}
    return tuple(sorted(((normalize_empreendimento(c), c) for c in cidades if c), key=lambda c: -len(c[0])))


def cidade_no_texto(texto, cidades):
    """
    A cidade do catálogo citada num texto livre (nome de conta, campanha ou palavra buscada).

    Serve para o que não identifica produto: "avare_google-pmax_lancamento" é campanha da cidade e
    anuncia mais de um produto, então o número fica na praça, não num produto escolhido a dedo.
    """
    alvo = normalize_empreendimento(texto) or ""
    for sem_acento, nome in cidades:
        if sem_acento and re.search(rf"\b{re.escape(sem_acento)}\b", alvo):
            return nome
    return None


def _tokens_empreendimento(texto):
    # Memorizado: o mesmo texto sempre dá os mesmos tokens (era o maior custo do BI e das conferências)
    return _tokens_memo("" if texto is None else str(texto))


@lru_cache(maxsize=200_000)
def _tokens_memo(texto):
    key = normalize_empreendimento(texto)
    if not key:
        return frozenset()
    for apelido, oficial in APELIDOS:
        key = re.sub(apelido, oficial, key)
    tokens = set()
    for t in key.split():
        t = ABREVIACOES.get(t, t)
        t = ALGARISMO_ROMANO.get(t, t)
        if t in EMPREENDIMENTO_STOPWORDS or t.isdigit():
            continue
        if len(t) > 2 or t in ROMANOS:
            tokens.add(t)
    return frozenset(tokens)


def is_generic_empreendimento(name) -> bool:
    """True para respostas como "Outros empreendimentos", que não identificam produto."""
    tokens = _tokens_empreendimento(name)
    return not tokens or tokens <= EMPREENDIMENTO_GENERICO_TOKENS


def split_empreendimento(name):
    """
    Separa nome e cidade de um empreendimento. O CV usa o padrão
    "Cidade - Nome - Código" (ex.: "Botucatu - Reserva Central Parque - 13600").
    Retorna (tokens_do_nome, tokens_da_cidade).
    """
    return _split_memo(str(name or ""))


@lru_cache(maxsize=50_000)
def _split_memo(name):
    partes = [p.strip() for p in re.split(r"\s+-\s+", name) if p.strip()]
    # "Tatuí - Mirante dos Ramos - Comercial 14703": o último trecho com número é o código do CV
    if len(partes) >= 3 and re.search(r"\d", partes[-1]):
        partes = partes[:-1]
    if len(partes) >= 3:
        cidade, nome = partes[0], " ".join(partes[1:])
    elif len(partes) == 2 and not partes[1].replace(" ", "").isdigit():
        cidade, nome = partes[0], partes[1]
    else:
        cidade, nome = "", " ".join(partes)

    tokens_nome = _tokens_empreendimento(nome)
    tokens_cidade = _tokens_empreendimento(cidade) - tokens_nome
    if not tokens_nome:
        # Nome feito só de palavras genéricas: usa o texto inteiro
        tokens_nome, tokens_cidade = _tokens_empreendimento(name), frozenset()
    return tokens_nome, tokens_cidade


def empreendimento_tokens(name):
    """Tokens que identificam o produto (sem cidade, código e palavras genéricas)."""
    return split_empreendimento(name)[0]


def match_empreendimento(text, catalogo):
    """
    Procura, dentro de um texto livre (nome de campanha, campo de interesse),
    qual empreendimento do catálogo está sendo citado.

    Todos os tokens do NOME precisam aparecer no texto; a cidade só desempata
    ("Novo Horizonte" existe em Cerqueira César e em Itatinga). Vence quem casa
    mais tokens. Empate não resolve (retorna None) — atribuir o lead ao produto
    errado é pior do que deixá-lo sem empreendimento.
    """
    if not catalogo:
        return None
    return _match_memo("" if text is None else str(text), tuple(catalogo))


@lru_cache(maxsize=200_000)
def _match_memo(text, catalogo):
    text_tokens = _tokens_empreendimento(text)
    if not text_tokens or not catalogo:
        return None

    melhor, melhor_score, empatado = None, (0, 0), False
    for oficial in catalogo:
        tokens_nome, tokens_cidade = split_empreendimento(oficial)
        if not tokens_nome or not tokens_nome <= text_tokens:
            continue
        score = (len(tokens_nome), len(tokens_cidade & text_tokens))
        if score > melhor_score:
            melhor, melhor_score, empatado = oficial, score, False
        elif score == melhor_score and unificar_empreendimento(oficial) != unificar_empreendimento(melhor):
            empatado = True

    return None if empatado else unificar_empreendimento(melhor)


def resolve_empreendimento(raw_dict, campaign_name=None, catalogo=None):
    """
    Descobre o empreendimento de um registro, em cascata:
      1. Campo explícito no payload (`empreendimento`, `produto`, `obra`...).
      2. Nome do empreendimento citado dentro do nome da campanha.
    Retorna None quando nada identifica o produto.
    """
    raw_dict = raw_dict or {}
    explicito = (
        raw_dict.get("empreendimento")
        or raw_dict.get("produto")
        or raw_dict.get("obra")
        or raw_dict.get("nome_empreendimento")
        or raw_dict.get("development")
    )
    if explicito and str(explicito).strip() and not is_generic_empreendimento(explicito):
        return unificar_empreendimento(str(explicito).strip())

    texto = campaign_name or raw_dict.get("campaign_name") or raw_dict.get("campanha")
    return match_empreendimento(texto, catalogo or [])


def normalize_lead(
    raw_dict: Dict[str, Any],
    channel: OriginChannel,
    catalogo_empreendimentos: Optional[list] = None,
) -> LeadRecord:
    email_raw = raw_dict.get("email") or raw_dict.get("e-mail") or raw_dict.get("user_email")
    phone_raw = raw_dict.get("phone") or raw_dict.get("telefone") or raw_dict.get("celular") or raw_dict.get("whatsapp")
    lead_id = str(raw_dict.get("id") or raw_dict.get("lead_id") or raw_dict.get("conversion_id") or f"gen_{hash(str(raw_dict))}")

    created_at_raw = raw_dict.get("created_at") or raw_dict.get("created_time") or raw_dict.get("data_cadastro")
    
    integration_id = (
        raw_dict.get("gclid")
        or raw_dict.get("fbclid")
        or raw_dict.get("bee_id")
        or raw_dict.get("rd_id")
        or raw_dict.get("integration_id")
    )

    campaign_name = raw_dict.get("campaign_name") or raw_dict.get("campanha")

    return LeadRecord(
        source_lead_id=lead_id,
        email=email_raw,
        email_clean=clean_email(email_raw),
        phone=phone_raw,
        phone_clean=clean_phone(phone_raw),
        origin_channel=channel,
        campaign_name=campaign_name,
        empreendimento=resolve_empreendimento(raw_dict, campaign_name, catalogo_empreendimentos),
        created_at=parse_datetime(created_at_raw),
        utm_source=raw_dict.get("utm_source"),
        utm_medium=raw_dict.get("utm_medium"),
        utm_campaign=raw_dict.get("utm_campaign"),
        integration_id=str(integration_id) if integration_id else None,
        raw_payload=raw_dict,
    )


def normalize_cv_lead(
    raw_dict: Dict[str, Any],
    catalogo_empreendimentos: Optional[list] = None,
) -> CVLeadRecord:
    email_raw = raw_dict.get("email") or raw_dict.get("e-mail")
    phone_raw = raw_dict.get("telefone") or raw_dict.get("celular") or raw_dict.get("phone")
    cv_id = str(
        raw_dict.get("id") or raw_dict.get("idlead") or raw_dict.get("id_lead") or raw_dict.get("cv_id")
    )
    created_at_raw = (
        raw_dict.get("data_cadastramento")
        or raw_dict.get("data_cad")
        or raw_dict.get("data_cadastro")
        or raw_dict.get("created_at")
    )

    origem_cv = str(raw_dict.get("origem") or raw_dict.get("fonte") or "desconhecido").strip()
    midia_cv = raw_dict.get("midia") or raw_dict.get("canal")

    return CVLeadRecord(
        cv_id=cv_id,
        email=email_raw,
        email_clean=clean_email(email_raw),
        phone=phone_raw,
        phone_clean=clean_phone(phone_raw),
        origem_cv=origem_cv,
        midia_cv=str(midia_cv) if midia_cv else None,
        empreendimento=resolve_empreendimento(raw_dict, None, catalogo_empreendimentos),
        created_at=parse_datetime(created_at_raw),
        id_externo=str(raw_dict.get("id_externo")) if raw_dict.get("id_externo") else None,
        raw_payload=raw_dict,
    )


# ==============================================================================
# NORMALIZAÇÃO DE VENDAS
# ==============================================================================

# Canais considerados "venda online" (mídia digital). Os demais são presenciais/offline.
ONLINE_CHANNELS = {
    OriginChannel.META_ADS,
    OriginChannel.GOOGLE_ADS,
    OriginChannel.RD_STATION,
    OriginChannel.BEEVIRAL,
}

# Termos que, no campo de origem da venda, indicam explicitamente venda online.
ONLINE_KEYWORDS = (
    "online", "on-line", "digital", "internet", "site", "web", "portal",
    "facebook", "instagram", "meta", "google", "ads", "adwords", "rd", "rdstation",
    "beeviral", "indica", "whatsapp", "landing", "mídia paga", "midia paga",
)

# Termos que indicam explicitamente venda presencial/offline.
OFFLINE_KEYWORDS = (
    "estande", "stand", "plantão", "plantao", "presencial", "loja", "feirão",
    "feirao", "evento", "corretor", "imobiliária", "imobiliaria", "parceiro",
    "carteira", "passagem", "telefone", "balcão", "balcao", "espontâneo", "espontaneo",
)


def normalize_name(name):
    """
    Normaliza um nome para comparação: sem acentos, minúsculo, sem pontuação
    e sem espaços duplicados. Usado apenas como chave de match de baixa confiança.
    """
    if not name:
        return None
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9 ]", " ", text).lower()
    text = re.sub(r"\s+", " ", text).strip()
    # Nome com uma única palavra é ambíguo demais para servir de chave
    if not text or len(text.split()) < 2:
        return None
    return text


def clean_document(doc: Optional[str]) -> Optional[str]:
    """Extrai apenas os dígitos de um CPF/CNPJ. Retorna None se não tiver tamanho válido."""
    if not doc:
        return None
    digits = re.sub(r"\D", "", str(doc))
    if len(digits) in (11, 14):
        return digits
    return None


def is_online_channel(channel: Optional[OriginChannel]) -> bool:
    """Indica se o canal de origem é considerado mídia digital (venda online)."""
    return channel in ONLINE_CHANNELS


def classify_declared_origin(origin_raw: Optional[str]) -> bool:
    """
    Decide se a origem declarada na venda é 'online'.
    Palavras-chave explícitas têm prioridade; no silêncio, cai na taxonomia de canais.
    """
    if not origin_raw:
        return False
    text = str(origin_raw).strip().lower()
    if any(term in text for term in OFFLINE_KEYWORDS):
        return False
    if any(term in text for term in ONLINE_KEYWORDS):
        return True
    return is_online_channel(normalize_channel_alias(text))


# Termos que identificam um canal específico no campo de origem da venda.
# Diferente de normalize_channel_alias, aqui não existe canal padrão: uma origem
# genérica como "Online" ou "Mídia Paga" não declara canal nenhum.
DECLARED_CHANNEL_TERMS = (
    (OriginChannel.META_ADS, ("facebook", "instagram", "meta", "fb ", "fbads", "face")),
    (OriginChannel.GOOGLE_ADS, ("google", "adwords", "gads", "youtube")),
    (OriginChannel.RD_STATION, ("rd station", "rdstation", "rd_station", "rd marketing")),
    (OriginChannel.BEEVIRAL, ("beeviral", "bee viral", "indica")),
    (OriginChannel.SHEETS_BI, ("estande", "stand", "plantão", "plantao", "feirão", "feirao",
                               "evento", "presencial", "planilha", "loja", "balcão", "balcao")),
)


def resolve_declared_channel(origin_raw):
    """
    Retorna o canal declarado pela venda, ou None quando a origem é genérica
    ("Online", "Mídia Paga", "Desconhecido"). Sem canal declarado não faz sentido
    acusar divergencia de canal na auditoria.
    """
    if not origin_raw:
        return None
    text = str(origin_raw).strip().lower()
    for channel, terms in DECLARED_CHANNEL_TERMS:
        if any(term in text for term in terms):
            return channel
    return None


def normalize_sale(raw_dict: Dict[str, Any]) -> SaleRecord:
    """Normaliza uma linha de venda/reserva vinda do CV CRM, de planilha ou de BI."""
    email_raw = (
        raw_dict.get("email")
        or raw_dict.get("e-mail")
        or raw_dict.get("email_cliente")
        or raw_dict.get("cliente_email")
    )
    phone_raw = (
        raw_dict.get("telefone")
        or raw_dict.get("celular")
        or raw_dict.get("phone")
        or raw_dict.get("whatsapp")
        or raw_dict.get("cliente_telefone")
    )
    doc_raw = (
        raw_dict.get("cpf")
        or raw_dict.get("documento")
        or raw_dict.get("cpf_cnpj")
        or raw_dict.get("document")
        or raw_dict.get("cliente_documento")
    )
    sale_id = str(
        raw_dict.get("id")
        or raw_dict.get("idreserva")
        or raw_dict.get("id_reserva")
        or raw_dict.get("venda_id")
        or raw_dict.get("sale_id")
        or f"sale_{abs(hash(str(raw_dict)))}"
    )
    client_name = (
        raw_dict.get("cliente")
        or raw_dict.get("nome")
        or raw_dict.get("nome_cliente")
        or raw_dict.get("client_name")
    )
    sale_date_raw = (
        raw_dict.get("data_venda")
        or raw_dict.get("data")
        or raw_dict.get("data_reserva")
        or raw_dict.get("data_contrato")
        or raw_dict.get("sale_date")
        or raw_dict.get("created_at")
    )

    origin_raw = str(
        raw_dict.get("origem")
        or raw_dict.get("canal")
        or raw_dict.get("midia")
        or raw_dict.get("fonte")
        or raw_dict.get("declared_channel")
        or "desconhecido"
    ).strip()

    value_raw = raw_dict.get("valor") or raw_dict.get("valor_contrato") or raw_dict.get("value")
    try:
        value = float(str(value_raw).replace("R$", "").replace(".", "").replace(",", ".").strip()) if value_raw else None
    except (TypeError, ValueError):
        value = None

    integration_id = (
        raw_dict.get("gclid")
        or raw_dict.get("fbclid")
        or raw_dict.get("bee_id")
        or raw_dict.get("rd_id")
        or raw_dict.get("id_externo")
        or raw_dict.get("integration_id")
    )

    declared_channel = resolve_declared_channel(origin_raw)

    return SaleRecord(
        sale_id=sale_id,
        client_name=str(client_name) if client_name else None,
        document=str(doc_raw) if doc_raw else None,
        document_clean=clean_document(doc_raw),
        email=email_raw,
        email_clean=clean_email(email_raw),
        phone=phone_raw,
        phone_clean=clean_phone(phone_raw),
        sale_date=parse_datetime(sale_date_raw),
        value=value,
        declared_channel_raw=origin_raw,
        declared_channel=declared_channel,
        declared_is_online=classify_declared_origin(origin_raw),
        empreendimento=raw_dict.get("empreendimento") or raw_dict.get("produto"),
        unidade=str(raw_dict.get("unidade")) if raw_dict.get("unidade") else None,
        integration_id=str(integration_id) if integration_id else None,
        raw_payload=raw_dict,
    )
