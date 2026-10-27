"""
Vendas online do período: as que o CV já conta como online, e as que são online mas não estão
registradas assim.

A regra é a da planilha de vendas online revisada com a gestão:
  1. o tipo "Vendas SDR" no CV conta direto: foi o próprio SDR que passou o cliente ao
     especialista, e isso o CV registra;
  2. TODA outra venda passa pela leitura da conversa (engine/leitura_conversa.py) — inclusive as
     que o CV já conta como online porque o lead vinculado à reserva veio do online. Ter mídia
     online por trás só diz que a venda PODERIA ser SDR; quem decide é a conversa. Só é venda
     online quando o cliente conversou com a GlorIA ou o SDR, quis seguir com a gente e comprou
     com o time Moura Leite. Se conversou e comprou com outro corretor, é venda que estamos
     perdendo; se não respondeu, não quis ou já estava com outro corretor, não era venda nossa —
     mesmo que o CV a conte como online;
  3. a leitura só decide quando há o que ler: conversão online na janela e nenhum corretor
     atendendo antes dela. Sem isso a venda não é online, e o motivo fica dito no resultado;
  4. o analista confere a leitura na tela e pode corrigir; a correção vale para a tela e a planilha.

Como cada venda é lida:
  1. quem comprou (titular e associados da reserva) é cruzado com TODOS os leads do CV por
     quatro chaves: lead vinculado à reserva, e-mail, telefone (com nome compatível) e nome
     completo único na base;
  2. cada lead ganha uma origem — a do CV e, quando o CV não tem, a descoberta na RD Station;
  3. a conversão online precisa estar na janela: 90 dias antes da venda ou, na safra de um
     lançamento, desde o início da pré-campanha do produto;
  4. o histórico do lead fica registrado como fato — atendimento do SDR ou da assistente virtual,
     e registro do corretor anterior à conversão — sem virar veredito: o CV não mostra o
     atendimento feito fora dele.

Os dados que a base salva não tem (compradores da reserva, pré-cadastro e o histórico completo
do lead) são lidos do CV pela API e guardados em disco: a mesma venda nunca é consultada duas vezes.
"""

import json
import os
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

from engine import bases, leitura_conversa, origem_rd
from engine.bi import praca_do_empreendimento
from engine.extractors.cv_crm import RESERVAS_PATH, CVCRMExtractor, valor_monetario
from engine.normalizer import clean_email, normalize_empreendimento, normalize_name, unificar_empreendimento
from engine.taxonomy import classificar_lead_cv

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output", "analises"))
SIMULTANEAS = int(os.getenv("VENDAS_ONLINE_SIMULTANEAS", "10"))

DIAS_JANELA = 90        # conversão online até 90 dias antes da venda
DIAS_SAFRA = 90         # vendas da safra do lançamento: até 90 dias depois da primeira venda
DIAS_CORRETOR = 180     # quanto tempo antes da conversão um registro do comercial ainda aparece

# Quem vende pelo time Moura Leite. O CV não tem esse campo: a lista foi tirada das vendas
# registradas como "Vendas SDR" e "Venda Time Moura Leite". Mudou o time, muda aqui.
TIME_MOURA_LEITE = (
    "Eduardo Oliveira Gonçalves", "Carlos Alberto Alves Santos", "Patrick Hernani Iaiz",
    "Gustavo Jesus Santos", "Jessica Catarina da Silva Santos",
    "Elisangela Lourenço de Vecchi", "José Cláudio Pereira", "Claudia Grandini Hunnicutt",
    "Thais Maria Machado Medeiros Cardenas", "Karen Roberta da Silveira",
)

# Resultado de cada venda. Os textos são os da planilha: os quadros contam por eles.
RESULTADO = {
    "online_cv_sdr": "Online no CV (venda SDR)",
    "online_cv_lead": "Online no CV (lead online, e a conversa confirma)",
    "caso": "PARA INVESTIGAR",
    "perda": "Atendemos, mas comprou com outro corretor",
    "nao_nossa": "Veio do online, mas não era venda nossa",
    "ja_atendia": "Conversão online, mas o corretor já atendia",
    "fora_janela": "Conversão online fora da janela",
    "sem_conversao": "Sem conversão online",
}
# Muda quando a regra muda: análise gravada com outra versão precisa ser refeita
VERSAO_REGRA = 4
# A pré-campanha de um lançamento começa no mês em que a captação dispara: pelo menos 20 leads
# do produto e 5× a mediana dos 6 meses anteriores, nos 12 meses antes da primeira venda.
MIN_LEADS_PRE_CAMPANHA = 20
SALTO_PRE_CAMPANHA = 5
MESES_PRE_CAMPANHA = 12

# Canais do CV que NÃO são lead online: cadastro do comercial e remarketing da base.
NAO_ONLINE = ("comercial", "indicacao_pessoal", "whatsapp_organico", "whatsapp_nao_rastreado",
              "campanha_ativacao", "nao_rastreado")

CATEGORIA_ORIGEM = {
    "meta": "Campanha paga (Meta/Google)", "google": "Campanha paga (Meta/Google)",
    "tiktok": "Campanha paga (Meta/Google)", "midia_paga": "Campanha paga (Meta/Google)",
    "site": "Orgânico (site, chat, redes, e-mail)", "chat": "Orgânico (site, chat, redes, e-mail)",
    "redes_sociais": "Orgânico (site, chat, redes, e-mail)", "email_rd": "Orgânico (site, chat, redes, e-mail)",
    "whatsapp_organico": "WhatsApp (remarketing do comercial)",
    "whatsapp_nao_rastreado": "WhatsApp (remarketing do comercial)",
    "beeviral": "Indicação BeeViral",
    "midia_offline": "Mídia offline (outdoor, panfleto, rádio)",
    "campanha_ativacao": "Ativação da base (remarketing do comercial)",
    "nao_rastreado": "Sem origem registrada",
    "comercial": "Cadastro manual (corretor, imobiliária, PDV, gestor)",
    "indicacao_pessoal": "Indicação pessoal (cadastro manual)",
}

CANAL_VENDA = {
    "Vendas SDR": "SDR", "Venda Imobiliária": "Imobiliária", "Venda Time Moura Leite": "Corretor (Time Moura Leite)",
    "Venda Interna": "Venda Interna", "Venda Espontânea (Time)": "Corretor (Espontânea)", None: "Sem tipo de venda",
}

# Marcas da tratativa nas interações, tarefas, tags e situação do lead
RE_SDR_HUMANO = re.compile(r"mensagem de sal|^\s*sal\s*\d|ticket id|whatsapp sdr", re.I)
RE_ASSISTENTE = re.compile(r"\[m\.i\.a\]|relato enviado pel|assistente virtual", re.I)
RE_SDR_TAG = re.compile(r"\(sal|\(sql\)|tentativa de contato|mia-qualificado|mia-transferido|lead oportunidade", re.I)
RE_TAG_HUMANO = re.compile(r"\(sal|\(sql\)|tentativa de contato|lead oportunidade", re.I)
RE_SDR_SIT = re.compile(r"\(sal|sql|tentativa de contato|atendimento ia|novo lead", re.I)
RE_ATRIB = re.compile(r"mantendo a atribui[cç][aã]o para o atendente:\s*([^\.\n]+)", re.I)
RE_ATEND_EMAIL = re.compile(r"Atendente:\s*([a-z\.]+)@\w", re.I)
RE_JA_CORRETOR = re.compile(r"j[aá] se cadastrou com outro corretor|atendid[oa] por (outro )?corretor", re.I)
RE_FILA_VENDAS = re.compile(r"transferido para fila de vendas|transferido para fila de gestor|transferido diretamente para o atendente", re.I)

PARTICULAS = {"de", "da", "do", "das", "dos", "e"}

# Toda venda tem as mesmas colunas: a que não tem lead online fica com esses campos vazios.
SEM_LEAD_ONLINE: Dict[str, Any] = {
    "primeira_conv_online": None, "dias_online_antes_venda": None, "online_90_dias": False,
    "leads_janela": [], "chaves_ligacao": [], "lead_ref": None, "regra_janela": None, "safra_lancamento": False,
    "data_lancamento": None, "inicio_pre_campanha": None, "conv_ref": None, "dias_conv_venda": None,
    "sdr_eventos": [], "sdr_tags": [], "sdr_situacao": [], "sdr_humano": False, "sdr_assistente": False,
    "sdr_sql": False, "corretor_antes": [],
}


def _sem_prefixo(corretor: Any) -> str:
    return _sem_acento(re.sub(r"^\s*especialista\s*-\s*", "", str(corretor or ""), flags=re.I))


def do_time(corretor: Any) -> bool:
    """O corretor da venda é do time Moura Leite (com ou sem o prefixo "Especialista")."""
    return _sem_prefixo(corretor) in {_sem_acento(n) for n in TIME_MOURA_LEITE}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _data(valor: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def _sem_acento(texto: Any) -> str:
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower().strip()


def _nome_item(valor: Any) -> Any:
    return valor.get("nome") if isinstance(valor, dict) else valor


def _chave_telefone(valor: Any) -> Optional[str]:
    """DDD + 8 dígitos finais: o mesmo número com ou sem DDI e com ou sem o nono dígito."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    if len(digitos) >= 12 and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) == 11 and digitos[2] == "9":
        digitos = digitos[:2] + digitos[3:]
    return digitos if len(digitos) == 10 else None


@lru_cache(maxsize=50_000)
def _nucleo(nome: Any) -> str:
    """'Tatuí - Reserva dos Ramos Residencial - 14704' -> 'reserva dos ramos residencial'."""
    partes = [p.strip() for p in re.split(r"\s+-\s+", str(nome or "")) if p.strip()]
    if len(partes) >= 3 and re.fullmatch(r"[\d\s]+", partes[-1]):
        partes = partes[1:-1]
    elif len(partes) >= 2:
        partes = partes[1:]
    return normalize_empreendimento(" ".join(partes)) or ""


@lru_cache(maxsize=200_000)
def _mesmo_produto(interesse: Any, produto: str) -> bool:
    """O interesse do lead é neste produto (Mirante dos Ramos conta como Reserva dos Ramos)."""
    if not interesse:
        return False
    if unificar_empreendimento(interesse) == unificar_empreendimento(produto):
        return True
    a, b = _nucleo(interesse), _nucleo(produto)
    return bool(a and b and (a in b or b in a))


# ---------------------------------------------------------------------------
# Leitura do CV (com cache em disco)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _host() -> str:
    return (CVCRMExtractor().api_url or "").rstrip("/")


def link_reserva(idreserva: Any) -> Optional[str]:
    """Mesma URL que o relatório de vendas do CV usa no nome do cliente."""
    host = _host()
    return f"{host}/gestor/relatorios/associado/html?q[1|r.idreserva]={idreserva}" if host else None


def link_lead(idlead: Any) -> Optional[str]:
    host = _host()
    return f"{host}/gestor/comercial/leads/{idlead}/administrar" if host else None


def _caminho(nome: str) -> str:
    return os.path.join(CACHE_DIR, f"{nome}.json")


def _ler_cache(nome: str) -> Dict[str, Any]:
    caminho = _caminho(nome)
    if not os.path.exists(caminho):
        return {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def _gravar_cache(nome: str, dados: Dict[str, Any]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = _caminho(nome) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)
    os.replace(tmp, _caminho(nome))


def _buscar_no_cv(pedidos: List[Tuple[str, str]], extrair: Callable[[Any], Any]) -> Dict[str, Any]:
    """Busca em paralelo no CV. Devolve {chave: dado}; o que não responder fica de fora."""
    import httpx

    ex = CVCRMExtractor()
    if not (ex.api_url and ex.token):
        raise RuntimeError("Credenciais do CV não configuradas (CV_CRM_URL / token).")
    saida: Dict[str, Any] = {}
    with httpx.Client(timeout=60, limits=httpx.Limits(max_connections=SIMULTANEAS)) as client:

        def um(pedido: Tuple[str, str]) -> Tuple[str, Any]:
            chave, url = pedido
            for tentativa in range(4):
                try:
                    res = client.get(ex.api_url + url, headers=ex._headers())
                    if res.status_code == 200:
                        return chave, extrair(res.json())
                    if res.status_code in (400, 404):
                        return chave, None
                except Exception:  # noqa: BLE001 — erro de rede: tenta de novo
                    pass
                time.sleep(2 * (tentativa + 1))
            return chave, None

        with ThreadPoolExecutor(SIMULTANEAS) as pool:
            for chave, dado in pool.map(um, pedidos):
                saida[chave] = dado
    return saida


def _completar_cache(nome: str, pedidos: List[Tuple[str, str]], extrair: Callable[[Any], Any]) -> Dict[str, Any]:
    """Lê do cache o que já foi buscado e vai ao CV só pelo que falta."""
    guardado = _ler_cache(nome)
    faltam = [p for p in pedidos if p[0] not in guardado]
    if faltam:
        guardado.update(_buscar_no_cv(faltam, extrair))
        _gravar_cache(nome, guardado)
    return guardado


# ---------------------------------------------------------------------------
# Universo: as vendas do período
# ---------------------------------------------------------------------------


def vendas_do_periodo(inicio: date, fim: date, empreendimentos: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Reservas vendidas no período.

    A venda distratada depois continua aqui: ela aconteceu na data da venda e o distrato é
    posterior. No CV ela deixa de ser "vendida" e passa à situação "Distrato".
    """
    escolhidos = set(empreendimentos or [])
    saida = []
    for r in bases.registros("cv_reservas"):
        dv = _data(r.get("data_venda"))
        vendida = bool(r.get("vendida")) or r.get("situacao") == "Distrato"
        if not (vendida and dv and inicio <= dv <= fim):
            continue
        if escolhidos and r.get("empreendimento") not in escolhidos:
            continue
        saida.append(r)
    return saida


# ---------------------------------------------------------------------------
# Lançamentos: lidos dos dados, não escritos à mão
# ---------------------------------------------------------------------------


def lancamentos(produtos: List[str]) -> Dict[str, Dict[str, Any]]:
    """Data da 1ª venda de cada produto e o mês em que a pré-campanha começou a trazer leads."""
    primeira_venda: Dict[str, date] = {}
    for r in bases.registros("cv_reservas"):
        emp, dv = r.get("empreendimento"), _data(r.get("data_venda"))
        if r.get("vendida") and dv and emp in produtos:
            if emp not in primeira_venda or dv < primeira_venda[emp]:
                primeira_venda[emp] = dv

    # Leads por mês de cada produto, para achar quando a captação começou
    por_produto_mes: Dict[Tuple[str, str], int] = {}
    todos = list(bases.registros("cv_indice")) + list(bases.registros("cv_leads"))
    for l in todos:
        d = _data(l.get("data_cad"))
        if not d:
            continue
        interesses = l.get("empreendimento")
        for item in (interesses if isinstance(interesses, list) else [interesses]):
            nome = _nome_item(item)
            for produto in produtos:
                if _mesmo_produto(nome, produto):
                    chave = (produto, f"{d:%Y-%m}")
                    por_produto_mes[chave] = por_produto_mes.get(chave, 0) + 1

    saida = {}
    for produto, lancamento in primeira_venda.items():
        contagem = {mes: n for (p, mes), n in por_produto_mes.items() if p == produto}
        saida[produto] = {"lancamento": lancamento, "inicio_pre_campanha": _inicio_pre_campanha(contagem, lancamento),
                          "safra_ate": lancamento + timedelta(days=DIAS_SAFRA)}
    return saida


def _meses_antes(mes: str, quantos: int) -> List[str]:
    ano, m = int(mes[:4]), int(mes[5:])
    saida = []
    for _ in range(quantos):
        ano, m = (ano - 1, 12) if m == 1 else (ano, m - 1)
        saida.append(f"{ano:04d}-{m:02d}")
    return saida


def _inicio_pre_campanha(contagem: Dict[str, int], lancamento: date) -> Optional[date]:
    """Primeiro mês em que a captação do produto dispara: o começo da pré-campanha."""
    limite = lancamento - timedelta(days=31 * MESES_PRE_CAMPANHA)
    candidatos = sorted(m for m in contagem if f"{limite:%Y-%m}" <= m <= f"{lancamento:%Y-%m}")
    for mes in candidatos:
        anteriores = sorted(contagem.get(m, 0) for m in _meses_antes(mes, 6))
        mediana = (anteriores[2] + anteriores[3]) / 2
        if contagem[mes] >= MIN_LEADS_PRE_CAMPANHA and contagem[mes] >= SALTO_PRE_CAMPANHA * max(mediana, 1):
            return date(int(mes[:4]), int(mes[5:]), 1)
    return None


# ---------------------------------------------------------------------------
# Leads de quem comprou
# ---------------------------------------------------------------------------


def _indice_de_leads() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, List[str]]], Dict[str, int]]:
    leads = {str(l["idlead"]): l for l in bases.registros("cv_indice") if l.get("idlead")}
    leads.update({str(l["idlead"]): l for l in bases.registros("cv_leads") if l.get("idlead")})
    indice: Dict[str, Dict[str, List[str]]] = {"email": {}, "fone": {}, "nome": {}}
    nomes: Dict[str, int] = {}
    for lid, l in leads.items():
        nome = normalize_name(l.get("nome"))
        if nome:
            nomes[nome] = nomes.get(nome, 0) + 1
        for tipo, valor in (("email", clean_email(l.get("email"))), ("fone", _chave_telefone(l.get("telefone"))),
                            ("nome", nome)):
            if valor and (tipo != "nome" or len(valor.split()) >= 2):
                indice[tipo].setdefault(valor, []).append(lid)
    return leads, indice, nomes


def _pessoas_da_reserva(bruta: Dict[str, Any]) -> List[Tuple[Any, Any, Any]]:
    """(nome, e-mail, telefone) de cada comprador: titular e associados."""
    saida = []
    for a in bruta.get("associados_array") or []:
        saida.append((a.get("nome"), a.get("email"), a.get("telefone") or a.get("celular")))
    associados = bruta.get("associados")
    if isinstance(associados, dict):
        for a in associados.values():
            if isinstance(a, dict):
                saida.append((a.get("nome"), a.get("email"), a.get("telefone")))
                saida.append((a.get("nome"), a.get("email"), a.get("celular")))
    titular = bruta.get("titular") or {}
    if titular:
        saida.append((titular.get("nome"), titular.get("email"), titular.get("celular") or titular.get("telefone")))
    return saida


def _compatibilidade_nome(nome_lead: Any, compradores: List[Any]) -> str:
    """mesma pessoa (primeiro nome igual) · familiar (só sobrenome em comum) · nome diferente."""
    def tokens(texto: Any) -> List[str]:
        return [x for x in _sem_acento(texto).replace(".", " ").split() if x not in PARTICULAS and len(x) >= 2]

    lead = tokens(nome_lead)
    if not lead:
        return "sem nome no lead"
    melhor = "nome diferente"
    for comprador in compradores:
        c = tokens(comprador)
        if not c:
            continue
        if lead[0] == c[0]:
            return "mesma pessoa"
        if set(lead[1:]) & set(c[1:]):
            melhor = "familiar (sobrenome em comum)"
    return melhor


def _eventos_do_lead(lead: Dict[str, Any], ate: date, eh_corretor: Callable[[Any], bool]) -> Tuple[list, list, Any]:
    """Marcas de tratativa no lead até a data da venda: SDR humano, assistente e atribuição a corretor."""
    eventos = []
    for i in lead.get("interacao") or []:
        dt, texto = _data(i.get("data_cad")), str(i.get("descricao") or "")
        if not dt or dt > ate:
            continue
        atribuido = RE_ATRIB.search(texto)
        por_email = RE_ATEND_EMAIL.search(texto)
        if atribuido or por_email:
            quem = atribuido.group(1).strip() if atribuido else por_email.group(1).replace(".", " ").title()
            eventos.append((dt, "corretor_atribuido" if eh_corretor(quem) else "sdr", f"Atendente SDR: {quem}"))
            continue
        if RE_JA_CORRETOR.search(texto):
            eventos.append((dt, "corretor_atribuido", "Interação: lead já atendido/cadastrado por corretor"))
        elif RE_FILA_VENDAS.search(texto):
            eventos.append((dt, "assistente", "Assistente virtual repassou o lead para a fila de vendas"))
        elif RE_SDR_HUMANO.search(texto):
            eventos.append((dt, "sdr", "SDR enviou mensagem de SAL / atendimento"))
        elif RE_ASSISTENTE.search(texto):
            eventos.append((dt, "assistente", "Atendimento da assistente virtual"))
    for t in lead.get("tarefa") or []:
        dt, nome = _data(t.get("data_cad")), str(t.get("nome") or "")
        if not dt or dt > ate:
            continue
        if re.search(r"visita agendada pela assistente", nome, re.I):
            eventos.append((dt, "assistente", "Assistente virtual agendou visita"))
        elif re.search(r"\bsal\b", nome, re.I):
            eventos.append((dt, "sdr", f"Tarefa de SAL do SDR: {nome[:50]}"))
    tags = sorted({str(_nome_item(t)) for t in lead.get("tags") or [] if RE_SDR_TAG.search(str(_nome_item(t)))})
    return eventos, tags, _nome_item(lead.get("situacao"))


def _ultimo_lead(pessoa_leads: List[Dict[str, Any]], ate: date) -> Optional[Dict[str, Any]]:
    """Lead com a conversão (cadastro ou reconversão) mais recente até a data da venda."""
    def ultima(p: Dict[str, Any]) -> Optional[date]:
        datas = [x for x in (p["data_cad"], p["ult_conv"]) if x and x <= ate]
        return max(datas) if datas else None

    candidatos = [p for p in pessoa_leads if ultima(p)]
    return max(candidatos, key=ultima) if candidatos else None


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------


def coletar(vendas: List[Dict[str, Any]], progresso: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Compradores de cada reserva, pré-cadastros e histórico completo dos leads candidatos."""
    def aviso(texto: str) -> None:
        if progresso:
            progresso(texto)

    ids = [str(v["idreserva"]) for v in vendas]
    aviso(f"Lendo no CV os compradores de {len(ids)} venda(s)...")
    brutas = _completar_cache(
        "reservas", [(i, f"{RESERVAS_PATH}/{i}") for i in ids],
        lambda j: next(iter(j.values())) if isinstance(j, dict) and j else None,
    )
    brutas = {i: brutas.get(i) for i in ids}

    pres = sorted({str(b.get("idprecadastro")) for b in brutas.values() if b and b.get("idprecadastro")})
    aviso(f"Lendo {len(pres)} pré-cadastro(s)...")
    precadastros = _completar_cache(
        "precadastros", [(p, f"/api/v1/comercial/precadastro/{p}") for p in pres],
        lambda j: (j.get("precadastros") or [None])[0],
    )

    leads, indice, _ = _indice_de_leads()
    candidatos: Dict[str, Dict[str, List[str]]] = {}
    for rid, b in brutas.items():
        if not b:
            continue
        achados: Dict[str, set] = {}
        for l in b.get("leads_associados") or []:
            achados.setdefault(str(l.get("idlead")), set()).add("lead_associado")
        for nome, email, fone in _pessoas_da_reserva(b):
            for tipo, valor in (("email", clean_email(email)), ("fone", _chave_telefone(fone)),
                                ("nome", normalize_name(nome))):
                for lid in (indice[tipo].get(valor) or []) if valor else []:
                    achados.setdefault(lid, set()).add(tipo)
        candidatos[rid] = {k: sorted(v) for k, v in achados.items()}

    completos = {str(l["idlead"]) for l in bases.registros("cv_leads") if l.get("idlead")}
    faltam = sorted({lid for c in candidatos.values() for lid in c if lid not in completos})
    aviso(f"Lendo o histórico de {len(faltam)} lead(s) fora da base de 13 meses...")
    cheios = _completar_cache("leads", [(l, f"/api/cvio/lead?idlead={l}") for l in faltam],
                              lambda j: (j.get("leads") or [None])[0])
    return {"brutas": brutas, "precadastros": precadastros, "candidatos": candidatos, "leads_extras": cheios}


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------


def _corretores_conhecidos() -> Callable[[Any], bool]:
    nomes = set()
    for r in bases.registros("cv_reservas"):
        if r.get("corretor"):
            nomes.add(_sem_acento(re.sub(r"^Especialista - ", "", str(r["corretor"]))))

    def eh_corretor(nome: Any) -> bool:
        n = _sem_acento(nome)
        if len(n.split()) < 2:
            return False
        return any(c == n or c.startswith(n) or n.startswith(c) for c in nomes)

    return eh_corretor


def analisar(
    inicio: date,
    fim: date,
    empreendimentos: Optional[List[str]] = None,
    inicio_leads: Optional[date] = None,
    progresso: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Uma linha por venda do período, com a classificação e tudo que a sustenta.

    inicio_leads: conversões anteriores a essa data não entram na janela. Sem ela, vale só a
    janela de atribuição (90 dias ou pré-campanha), de qualquer ano.
    """
    vendas = vendas_do_periodo(inicio, fim, empreendimentos)
    inicio_leads = inicio_leads or date.min
    dados = coletar(vendas, progresso)
    brutas, precadastros = dados["brutas"], dados["precadastros"]
    candidatos, leads_extras = dados["candidatos"], dados["leads_extras"]

    leads, _, cont_nome = _indice_de_leads()
    leads.update({k: v for k, v in leads_extras.items() if v})
    eh_corretor = _corretores_conhecidos()
    origens_rd = origem_rd.por_lead()
    produtos = sorted({v.get("empreendimento") for v in vendas if v.get("empreendimento")})
    info_lancamentos = lancamentos(produtos)

    if progresso:
        progresso(f"Analisando {len(vendas)} venda(s)...")

    resultados: List[Dict[str, Any]] = []
    for venda in vendas:
        rid = str(venda["idreserva"])
        bruta = brutas.get(rid) or {}
        dv = _data(venda.get("data_venda"))
        dres = _data(venda.get("data"))
        produto = venda.get("empreendimento")
        tipo = venda.get("tipo_venda") or (bruta.get("tipovenda") or None)
        pc = precadastros.get(str(venda.get("idprecadastro"))) if venda.get("idprecadastro") else None
        d_pre = _data((pc or {}).get("data_cad"))
        titular = bruta.get("titular") or {}
        cliente = titular.get("nome") or next((a.get("nome") for a in bruta.get("associados_array") or [] if a.get("nome")), None)
        compradores = [cliente] + [a.get("nome") for a in bruta.get("associados_array") or []]

        pessoa_leads: List[Dict[str, Any]] = []
        for lid, chaves in (candidatos.get(rid) or {}).items():
            l = leads.get(lid)
            if not l:
                continue
            if chaves == ["nome"] and cont_nome.get(normalize_name(l.get("nome")), 0) != 1:
                continue
            parentesco = _compatibilidade_nome(l.get("nome"), compradores)
            # Ligação só por telefone exige nome compatível: evita telefone de corretor ou número reaproveitado
            if set(chaves) <= {"fone"} and parentesco == "nome diferente":
                continue
            c = classificar_lead_cv(l)
            eventos, tags_sdr, situacao = _eventos_do_lead(l, dv, eh_corretor)
            gerado = c.canal not in NAO_ONLINE
            categoria = CATEGORIA_ORIGEM.get(c.canal, c.canal_label)
            rd = origens_rd.get(lid) if c.canal == "nao_rastreado" else None
            if rd and rd.get("canal"):  # origem descoberta nas conversões da RD Station
                gerado, categoria = rd["online"], rd["categoria"]
            interesses = l.get("empreendimento")
            do_lancamento = produto in info_lancamentos and any(
                _mesmo_produto(_nome_item(e), produto)
                for e in (interesses if isinstance(interesses, list) else [interesses])
            )
            pessoa_leads.append({
                "id": lid, "chaves": chaves, "online": gerado, "categoria": categoria,
                "origem_rd": rd["detalhe"] if rd and rd.get("canal") else None,
                "lead_do_lancamento": do_lancamento, "parentesco": parentesco, "nome_lead": l.get("nome"),
                "midia_cv": _nome_item(l.get("midia_principal")) or ", ".join(
                    str(_nome_item(m)) for m in l.get("midias") or []) or None,
                "origem_cv": _nome_item(l.get("origem")),
                "utm": " / ".join(x for x in (c.utm_source, c.utm_medium) if x) or None,
                "campanha": c.campanha, "canal": c.canal_label, "grupo": c.grupo,
                "evidencia": (rd["detalhe"] if rd and rd.get("canal") else c.evidencia),
                "data_cad": _data(l.get("data_cad")), "ult_conv": _data(l.get("ultima_data_conversao")),
                "eventos": eventos, "tags_sdr": tags_sdr, "situacao": situacao,
                "link": l.get("link_interesses") or l.get("link_interacoes"),
            })

        online_antes = [p for p in pessoa_leads if p["online"] and p["data_cad"] and p["data_cad"] <= dv]
        vinculados = [p for p in pessoa_leads if "lead_associado" in p["chaves"]]
        item: Dict[str, Any] = {
            "idreserva": rid, "produto": produto, "praca": praca_do_empreendimento(produto), "data_venda": dv,
            "situacao_atual": venda.get("situacao"), "data_distrato": _data(venda.get("data_distrato")),
            "link_reserva": link_reserva(rid),
            "data_reserva": dres, "tipo_venda": tipo or "Sem tipo", "canal": CANAL_VENDA.get(tipo, tipo),
            "corretor": venda.get("corretor"), "imobiliaria": venda.get("imobiliaria"),
            "valor": (venda.get("valor_contrato") or venda.get("vgv_tabela")
                      or valor_monetario((bruta.get("condicoes") or {}).get("valor_contrato")) or 0.0),
            "cliente": cliente,
            "unidade": " ".join(str(x) for x in (venda.get("bloco"), venda.get("unidade")) if x).strip(),
            "data_precadastro": d_pre, "corretor_precadastro": ((pc or {}).get("corretor") or {}).get("nome"),
            "tem_lead": bool(pessoa_leads), "tem_lead_online": bool(online_antes), "leads": pessoa_leads,
            "origem_ultimo_lead": (_ultimo_lead(pessoa_leads, dv) or {}).get("categoria"),
            # Como a venda está no CV: o BI gerencial conta a venda como online pela origem do lead vinculado
            "leads_vinculados": [p["id"] for p in vinculados],
            "origem_vinculado": next((p["categoria"] for p in vinculados if p["online"]),
                                     next((p["categoria"] for p in vinculados), "Sem lead vinculado à venda")),
            "venda_online_cv": CANAL_VENDA.get(tipo, tipo) == "SDR" or any(p["online"] for p in vinculados),
            "do_time": do_time(venda.get("corretor")),
            "tipo_sdr": tipo == "Vendas SDR",
            **SEM_LEAD_ONLINE,
        }

        if online_antes:
            item.update(_janela_e_historico(online_antes, pessoa_leads, dv, dres, d_pre,
                                            info_lancamentos.get(produto), inicio_leads))
        # A conversa é lida em toda venda que não é "Vendas SDR" no CV e tem o que ler: conversão
        # na janela e nenhum corretor atendendo antes. Vale também para as que o CV já conta como
        # online pelo lead vinculado — ter mídia online não basta, a conversa é que decide.
        item["leitura_auto"] = (
            leitura_conversa.ler(item, [leads.get(i) for i in item["leads_janela"]])
            if not item["tipo_sdr"] and item["online_90_dias"] and not item["corretor_antes"] else None
        )
        resultados.append(item)

    return _montar(resultados, inicio, fim, inicio_leads, produtos, info_lancamentos)


def _janela_e_historico(online_antes, pessoa_leads, dv, dres, d_pre, lancamento, inicio_leads) -> Dict[str, Any]:
    """Janela de atribuição e o histórico do lead (atendimento e registros do corretor), como fatos."""
    primeira = min(p["data_cad"] for p in online_antes)
    data_lancamento = (lancamento or {}).get("lancamento")
    pre_inicio = (lancamento or {}).get("inicio_pre_campanha")
    safra = bool(data_lancamento and data_lancamento - timedelta(days=7) <= dv <= data_lancamento + timedelta(days=DIAS_SAFRA))

    def na_janela(p: Dict[str, Any], x: Optional[date]) -> bool:
        if not x or x > dv or x < inicio_leads:
            return False
        if (dv - x).days <= DIAS_JANELA:
            return True
        return bool(safra and p["lead_do_lancamento"] and pre_inicio and x >= pre_inicio)

    leads_janela = [p for p in online_antes if any(na_janela(p, x) for x in (p["data_cad"], p["ult_conv"]))]
    janela = sorted({x for p in leads_janela for x in (p["data_cad"], p["ult_conv"]) if na_janela(p, x)})
    conv_ref = min(janela) if janela else None
    regra = ("pré-lançamento" if conv_ref and (dv - conv_ref).days > DIAS_JANELA else "90 dias") if conv_ref else None

    todos_ev = [(dt, tp, txt, p["id"]) for p in pessoa_leads for (dt, tp, txt) in p["eventos"]]
    base_sdr = (conv_ref or primeira) - timedelta(days=7)
    sdr_ev = sorted(e for e in todos_ev if e[1] in ("sdr", "assistente") and e[0] >= base_sdr)
    tags = sorted({t for p in online_antes for t in p["tags_sdr"]})
    sit_sdr = sorted({p["situacao"] for p in online_antes if p["situacao"] and RE_SDR_SIT.search(p["situacao"])})
    humano = bool([e for e in sdr_ev if e[1] == "sdr"] or [t for t in tags if RE_TAG_HUMANO.search(t)] or sit_sdr)
    assistente = bool([e for e in sdr_ev if e[1] == "assistente"] or [t for t in tags if t.lower().startswith("mia")])
    tem_sql = any("sql" in t.lower() for t in tags) or any("sql" in s.lower() for s in sit_sdr)
    inicio_corretor = d_pre or dres

    # O que o CV registra do corretor antes da conversão online. É fato, não prova: o atendimento
    # feito fora do CV não aparece aqui.
    corretor_antes = []
    if conv_ref:
        for p in pessoa_leads:
            if (not p["online"] and not str(p["categoria"]).startswith("Sem origem") and p["data_cad"]
                    and conv_ref - timedelta(days=DIAS_CORRETOR) <= p["data_cad"] < conv_ref):
                corretor_antes.append((p["data_cad"], f"Lead do comercial ({p['categoria']}) cadastrado em "
                                                      f"{p['data_cad']:%d/%m/%Y}"))
        if d_pre and d_pre < conv_ref:
            corretor_antes.append((d_pre, f"Pré-cadastro com o corretor em {d_pre:%d/%m/%Y}"))
        if dres and dres < conv_ref:
            corretor_antes.append((dres, f"Reserva feita em {dres:%d/%m/%Y}"))
        for (dt, tp, txt, _lid) in todos_ev:
            if tp == "corretor_atribuido" and conv_ref - timedelta(days=DIAS_CORRETOR) <= dt <= conv_ref:
                corretor_antes.append((dt, f"{txt} em {dt:%d/%m/%Y}"))
        # Pré-cadastro colado na conversão: o corretor já atendia, a menos que o SDR tenha qualificado
        # (SQL) ou tratado o lead antes — aí foi um repasse rápido do SDR
        sdr_antes_corretor = bool(inicio_corretor and any(e[1] == "sdr" and e[0] <= inicio_corretor for e in sdr_ev))
        if (inicio_corretor and 0 <= (inicio_corretor - conv_ref).days <= 3 and not tem_sql
                and not sdr_antes_corretor and not corretor_antes):
            corretor_antes.append((inicio_corretor, f"{'Pré-cadastro' if d_pre else 'Reserva'} com o corretor em "
                                                    f"{inicio_corretor:%d/%m/%Y}, junto com a conversão online"))
    corretor_antes.sort()

    return {
        "primeira_conv_online": primeira, "dias_online_antes_venda": (dv - primeira).days,
        "online_90_dias": bool(conv_ref),
        "leads_janela": [p["id"] for p in leads_janela],
        "chaves_ligacao": sorted({k for p in (leads_janela or online_antes) for k in p["chaves"]}),
        "lead_ref": (_ultimo_lead(leads_janela, dv) or {}).get("id"),
        "regra_janela": regra, "safra_lancamento": safra,
        "data_lancamento": data_lancamento, "inicio_pre_campanha": pre_inicio,
        "conv_ref": conv_ref, "dias_conv_venda": (dv - conv_ref).days if conv_ref else None,
        "sdr_eventos": sdr_ev, "sdr_tags": tags, "sdr_situacao": sit_sdr,
        "sdr_humano": humano, "sdr_assistente": assistente, "sdr_sql": tem_sql,
        "corretor_antes": corretor_antes,
    }


def classificar(item: Dict[str, Any], revisoes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """O resultado da venda, com a leitura da conversa que vale (a revisada pelo analista, se houver)."""
    leitura = None
    if item["tipo_sdr"]:
        # O CV registra que o SDR passou o cliente ao especialista: não há o que reler
        chave = "online_cv_sdr"
    elif item["online_90_dias"]:
        if item["corretor_antes"]:
            chave = "ja_atendia"
        else:
            leitura = leitura_conversa.aplicar(item.get("leitura_auto"), revisoes.get(str(item["idreserva"])))
            # Quando a conversa confirma o online, a venda que o CV já conta fica onde está; a que
            # o CV não conta vira caso para investigar. Se a conversa nega, sai do online nas duas.
            online = "online_cv_lead" if item["venda_online_cv"] else "caso"
            chave = {leitura_conversa.ONLINE: online, leitura_conversa.PERDA: "perda"}.get(leitura.get("leitura"),
                                                                                           "nao_nossa")
    elif item["tem_lead_online"]:
        chave = "fora_janela"
    else:
        chave = "sem_conversao"
    return {"resultado": chave, "resultado_label": RESULTADO[chave], "leitura": leitura}


def analisar_periodo(inicio: date, fim: date, progresso: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """A análise do período, gravada, com a planilha pronta."""
    from engine import relatorio_vendas

    analise = analisar(inicio, fim, progresso=progresso)
    if progresso:
        progresso("Montando a planilha...")
    caminho = relatorio_vendas.gerar(analise)
    conteudo = {
        "analise": analise,
        "relatorio": os.path.basename(caminho),
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _gravar_periodo(inicio, fim, conteudo)
    return conteudo


def regra_atual(conteudo: Optional[Dict[str, Any]]) -> bool:
    """A análise gravada foi feita com a regra de hoje (senão precisa ser refeita)."""
    return bool(conteudo) and conteudo["analise"].get("versao_regra") == VERSAO_REGRA


def _arquivo_periodo(inicio: date, fim: date) -> str:
    return os.path.join(CACHE_DIR, "periodos", f"{inicio:%Y%m%d}_{fim:%Y%m%d}.json")


def _gravar_periodo(inicio: date, fim: date, conteudo: Dict[str, Any]) -> None:
    caminho = _arquivo_periodo(inicio, fim)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, default=lambda o: o.isoformat() if isinstance(o, date) else str(o))
    os.replace(tmp, caminho)


def analise_salva(inicio: date, fim: date) -> Optional[Dict[str, Any]]:
    """A última análise gravada desse período, ou None se ele nunca foi analisado."""
    caminho = _arquivo_periodo(inicio, fim)
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = json.load(f)
    except (ValueError, OSError):
        return None
    # As leituras revisadas depois da análise valem na hora: resultado e números são refeitos
    if regra_atual(conteudo):
        conteudo["analise"] = recalcular(conteudo["analise"])
    return conteudo


# ---------------------------------------------------------------------------
# Execução em segundo plano: a primeira leitura de um período vai ao CV
# ---------------------------------------------------------------------------

_trava = threading.Lock()
_execucao: Dict[str, Any] = {"em_andamento": False, "periodo": None, "mensagem": None,
                             "iniciado_em": None, "concluido_em": None, "erro": None}


def estado_execucao() -> Dict[str, Any]:
    return dict(_execucao)


def iniciar_analise(inicio: date, fim: date) -> Dict[str, Any]:
    """Dispara a análise do período numa thread. Ignora o pedido se já houver uma rodando."""
    if not _trava.acquire(blocking=False):
        return {**estado_execucao(), "aceito": False}

    def rodar():
        try:
            _execucao.update(em_andamento=True, periodo=f"{inicio.isoformat()}..{fim.isoformat()}", erro=None,
                             mensagem="Começando...", iniciado_em=time.strftime("%Y-%m-%dT%H:%M:%S"), concluido_em=None)
            analisar_periodo(inicio, fim, progresso=lambda m: _execucao.update(mensagem=m))
        except Exception as e:  # noqa: BLE001 — o erro precisa chegar à tela
            _execucao.update(erro=str(e))
        finally:
            _execucao.update(em_andamento=False, mensagem=None,
                             concluido_em=time.strftime("%Y-%m-%dT%H:%M:%S"))
            _trava.release()

    threading.Thread(target=rodar, daemon=True, name="analise-vendas-online").start()
    return {**estado_execucao(), "em_andamento": True, "aceito": True}


def _montar(resultados, inicio, fim, inicio_leads, produtos, info_lancamentos) -> Dict[str, Any]:
    return recalcular({
        "versao_regra": VERSAO_REGRA,
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat(),
                    "inicio_leads": None if inicio_leads == date.min else inicio_leads.isoformat()},
        "produtos": produtos,
        "time": list(TIME_MOURA_LEITE),
        "lancamentos": {
            p: {k: (v.isoformat() if isinstance(v, date) else v) for k, v in dados.items()}
            for p, dados in info_lancamentos.items()
        },
        "vendas": resultados,
        "calculado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })


def recalcular(analise: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica as leituras revisadas e refaz o resultado de cada venda e os números do período."""
    revisoes = leitura_conversa.revisoes()
    vendas = [{**v, **classificar(v, revisoes)} for v in analise["vendas"]]

    def grupo(*chaves):
        return [v for v in vendas if v["resultado"] in chaves]

    soma = lambda lista: round(sum(v["valor"] for v in lista), 2)
    nao_online = [v for v in vendas if not v["venda_online_cv"]]
    casos, perdas, nao_nossas = grupo("caso"), grupo("perda"), grupo("nao_nossa")
    online = grupo("online_cv_sdr", "online_cv_lead", "caso")
    # O CV conta como online e a conversa desmentiu: é a diferença entre o nosso número e o do BI
    tirados = [v for v in vendas if v["venda_online_cv"] and v["resultado"] not in
               ("online_cv_sdr", "online_cv_lead")]
    return {
        **analise,
        "vendas": vendas,
        "resumo": {
            "vendas": len(vendas),
            "vgv": soma(vendas),
            "distratos": sum(1 for v in vendas if v["situacao_atual"] == "Distrato"),
            # online: pela nossa regra (a conversa decide). online_cv: como o CV conta, para comparar com o BI
            "online": len(online),
            "vgv_online": soma(online),
            "online_cv": len(vendas) - len(nao_online),
            "online_cv_sdr": len(grupo("online_cv_sdr")),
            "online_cv_lead": len(grupo("online_cv_lead")),
            "tirados_do_online": len(tirados),
            "vgv_tirados_do_online": soma(tirados),
            "nao_online_cv": len(nao_online),
            "com_conversao": sum(1 for v in nao_online if v["online_90_dias"]),
            # Veio do online, mas o cliente comprou com outro corretor: não entra nos casos
            "outro_corretor": len(grupo("ja_atendia", "perda", "nao_nossa")),
            "ja_atendia": len(grupo("ja_atendia")),
            "casos": len(casos),
            "vgv_casos": soma(casos),
            "casos_distrato": sum(1 for v in casos if v["situacao_atual"] == "Distrato"),
            "perdas": len(perdas),
            "vgv_perdas": soma(perdas),
            "nao_nossas": len(nao_nossas),
            "vgv_nao_nossas": soma(nao_nossas),
            "fora_janela": len(grupo("fora_janela")),
            "sem_conversao": len(grupo("sem_conversao")),
            "leituras_revisadas": sum(1 for v in vendas if (v.get("leitura") or {}).get("revisada")),
        },
    }
