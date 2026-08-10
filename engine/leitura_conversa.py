"""
Leitura da conversa: o cliente que veio do online seguiu no atendimento com a gente?

Não basta o cliente ter vindo do online. Só é venda online quando ele respondeu, conversou com a
GlorIA ou o SDR, seguiu no atendimento e comprou com o nosso time. Se conversou com a gente e
comprou com outro corretor, é venda que estamos perdendo. Se não respondeu, disse que não tinha
interesse, já estava com outro corretor ou era assunto de pós-venda, não era venda nossa.

A leitura é feita sobre o que o CV registra nos leads online da janela: os relatos da GlorIA, as
anotações do SDR, as tarefas (visita agendada), as etapas (SQL, atendimento realizado) e o motivo
de cancelamento. É uma leitura automática: o analista confere na tela e pode corrigir. A correção
fica gravada e vale para a tela e para a planilha, em qualquer período que tenha a venda.
"""

import json
import os
import re
import threading
import time
import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

ONLINE, PERDA, NAO_NOSSA = "online", "perda", "nao_nossa"
LEITURAS = {
    ONLINE: "Venda online (a conversa confirma)",
    PERDA: "Atendemos, mas comprou com outro corretor",
    NAO_NOSSA: "Não era venda nossa",
}
MOTIVOS = {
    "conversou": "Conversou com a gente e seguiu no atendimento",
    "ja_com_outro": "Já estava com outro corretor",
    "sem_interesse": "Sem interesse",
    "pos_venda": "Pós-venda",
    "nao_seguiu": "Pediu informações, mas não seguiu no atendimento",
    "sem_resposta": "Não respondeu",
    "revisado": "Leitura revisada pelo analista",
}

# Até quantos dias antes da conversão de referência a conversa ainda é do mesmo interesse
DIAS_ANTES_DA_CONVERSAO = 45

ARQUIVO_REVISOES = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output", "analises",
                                                "leituras_revisadas.json"))


def _norm(texto: Any) -> str:
    sem = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", sem.replace("&quot;", '"')).strip()


def _data(valor: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def _nome(valor: Any) -> Any:
    return valor.get("nome") if isinstance(valor, dict) else valor


# ---------------------------------------------------------------------------
# Sinais no texto (sempre sem acento e em minúsculas)
# ---------------------------------------------------------------------------

RE_RELATO = re.compile(r"relato enviado pel")
# Relato da GlorIA em que o cliente não disse nada
RE_RELATO_VAZIO = re.compile(r"mensagem inicial, mas o lead nao respondeu|o lead nao respondeu a mensagem"
                             r"|nao houve interacao adicional")
# Registros automáticos ou de cadência, que não mostram conversa
RE_SISTEMA = re.compile(r"^\[m\.i\.a\]|^(mensagem de )?sal\s*\d|mensagem de sal|^tarefa|ticket id")

RE_JA_COM_OUTRO = re.compile(
    r"ja se cadastrou com outro corretor|atendid[oa] por outro corretor"
    r"|ja (esta|estava|e) (em contato|em cadastro|sendo atendid[oa]|atendid[oa])"
    r"|ja (esta|estava) com (outro )?corretor|ja possui corretor")
RE_SEM_INTERESSE = re.compile(
    r"(disse|informou|respondeu|falou|relatou|deixou claro)[^.!]{0,40}(nao tem|nao tinha|nao possui|sem) interesse"
    r"|\bnao tem interesse|\bnao quer mais|desistiu da compra")
RE_POS_VENDA = re.compile(r"\bpos[- ]?vendas?\b")
RE_SEM_RESPOSTA = re.compile(r"nao interage|nunca interage|parou de responder|nao responde|outro lead ativo")

# O que mostra que o cliente seguiu no atendimento, e como isso aparece no texto da leitura
FORTES = [
    (re.compile(r"visita agendada|agendou (uma )?visita|(solicitou|pediu|quis|queria|quer) agendar( uma)? visita"
                r"|^visita\. lead #|concordou em visitar"), "agendou visita"),
    (re.compile(r"(pergunt\w+|question\w+|solicitou informacoes|pediu informacoes) sobre (o |os |a |as )?"
                r"(valor|preco|entrada|parcela|condic)|passei (a ele )?valores|fazem sentido para seu planejamento"),
     "falou de valores e condições"),
    (re.compile(r"participante da decisao|motivo d[ae] compra|estado civil|correspondem ao que busca"),
     "passou os dados do que procura"),
    (re.compile(r"(?<!nao )\b(aceitou|concordou)\b|interesse em fazer o pre-?cadastro|lead esta interessad"),
     "quis seguir com pré-cadastro ou especialista"),
]
TAGS_FORTES = [
    (re.compile(r"lead oportunidade \(sql\)"), "chegou a SQL"),
    (re.compile(r"atendimento realizado"), "teve atendimento realizado"),
]


def _registros(leads: Iterable[Dict[str, Any]], de: date, ate: date) -> List[Dict[str, Any]]:
    """Interações e tarefas dos leads no intervalo, em ordem de data."""
    saida = []
    for lead in leads:
        lid = str(lead.get("idlead"))
        for i in lead.get("interacao") or []:
            dt = _data(i.get("data_cad"))
            if dt and de <= dt <= ate and str(i.get("descricao") or "").strip():
                saida.append({"data": dt, "lead": lid, "tipo": "interacao", "texto": str(i["descricao"]).strip()})
        for t in lead.get("tarefa") or []:
            dt = _data(t.get("data_cad"))
            if dt and de <= dt <= ate and str(t.get("nome") or "").strip():
                saida.append({"data": dt, "lead": lid, "tipo": "tarefa", "texto": str(t["nome"]).strip()})
    return sorted(saida, key=lambda r: (r["data"], r["lead"]))


def _curto(texto: str, limite: int = 180) -> str:
    texto = re.sub(r"\s+", " ", texto.replace("&quot;", '"')).strip()
    texto = re.sub(r"^#\s*relato enviado pel[ao] [^-]*-\s*", "", texto, flags=re.I)
    return texto if len(texto) <= limite else texto[:limite].rsplit(" ", 1)[0] + "…"


def ler(venda: Dict[str, Any], leads: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Lê a conversa dos leads online da janela de uma venda.

    venda: data_venda, conv_ref, do_time, corretor e imobiliaria. leads: os registros completos
    (com interação, tarefa, tags e motivo de cancelamento) dos leads online da janela.
    """
    leads = [l for l in leads if l]
    dv, conv = _data(venda.get("data_venda")), _data(venda.get("conv_ref"))
    if not (dv and conv):
        return {}
    registros = _registros(leads, conv - timedelta(days=DIAS_ANTES_DA_CONVERSAO), dv)

    relevantes: List[Dict[str, Any]] = []
    destaques: List[str] = []
    gloria = sdr = False
    achado: Dict[str, Optional[Dict[str, Any]]] = {"ja_com_outro": None, "sem_interesse": None, "pos_venda": None,
                                                   "sem_resposta": None, "fraco": None}

    def marcar(registro, rotulo=None):
        if registro not in relevantes:
            relevantes.append(registro)
        if rotulo and rotulo not in destaques:
            destaques.append(rotulo)

    for r in registros:
        t = _norm(r["texto"])
        relato = bool(RE_RELATO.search(t))
        if relato and RE_RELATO_VAZIO.search(t):
            continue
        nota_humana = r["tipo"] == "interacao" and not relato and not RE_SISTEMA.search(t)
        for chave, regex in (("ja_com_outro", RE_JA_COM_OUTRO), ("sem_interesse", RE_SEM_INTERESSE),
                             ("pos_venda", RE_POS_VENDA)):
            if (relato or nota_humana) and regex.search(t) and not achado[chave]:
                achado[chave] = r
                marcar(r)
        if nota_humana and RE_SEM_RESPOSTA.search(t) and not achado["sem_resposta"]:
            achado["sem_resposta"] = r
            marcar(r)
        forte = False
        for regex, rotulo in FORTES:
            if (relato or nota_humana or r["tipo"] == "tarefa") and regex.search(t):
                forte = True
                marcar(r, rotulo)
        if forte:
            gloria = gloria or relato or "assistente" in t
            sdr = sdr or nota_humana or (r["tipo"] == "tarefa" and "assistente" not in t)
        elif relato and not achado["fraco"]:
            achado["fraco"] = r
            marcar(r)

    for lead in leads:
        tags = [_norm(_nome(x)) for x in lead.get("tags") or []]
        for regex, rotulo in TAGS_FORTES:
            if any(regex.search(x) for x in tags) and rotulo not in destaques:
                destaques.append(rotulo)
                sdr = True
        motivo = _norm(_nome(lead.get("motivo_cancelamento")))
        if "ja se cadastrou com outro corretor" in motivo and not achado["ja_com_outro"]:
            achado["ja_com_outro"] = {"data": None, "lead": str(lead.get("idlead")), "tipo": "motivo",
                                      "texto": f"Motivo de cancelamento do lead: {_nome(lead.get('motivo_cancelamento'))}"}

    conversou = bool(destaques)
    if achado["pos_venda"]:
        leitura, motivo = NAO_NOSSA, "pos_venda"
    elif achado["ja_com_outro"]:
        leitura, motivo = NAO_NOSSA, "ja_com_outro"
    elif achado["sem_interesse"]:
        leitura, motivo = NAO_NOSSA, "sem_interesse"
    elif conversou:
        leitura, motivo = (ONLINE if venda.get("do_time") else PERDA), "conversou"
    elif achado["fraco"]:
        leitura, motivo = NAO_NOSSA, "nao_seguiu"
    else:
        leitura, motivo = NAO_NOSSA, "sem_resposta"

    return {
        "leitura": leitura,
        "motivo": motivo,
        "texto": _texto(leitura, motivo, venda, destaques, gloria, sdr, achado),
        "destaques": destaques,
        "trechos": [{"data": r["data"].isoformat() if r["data"] else None, "lead": r["lead"], "texto": _curto(r["texto"], 300)}
                    for r in sorted(relevantes, key=lambda r: r["data"] or date.min)[:8]],
    }


def _citacao(registro: Optional[Dict[str, Any]]) -> str:
    if not registro:
        return ""
    quando = f", {registro['data']:%d/%m/%Y}" if registro.get("data") else ""
    return f" (\"{_curto(registro['texto'], 140)}\"{quando})"


def _texto(leitura, motivo, venda, destaques, gloria, sdr, achado) -> str:
    """A leitura em uma ou duas frases, no tom da planilha."""
    vendedor = re.sub(r"^\s*especialista\s*-\s*", "", str(venda.get("corretor") or ""), flags=re.I) or "corretor não informado"
    com_quem = " e ".join(x for x, ok in (("a GlorIA", gloria), ("o SDR", sdr)) if ok) or "a gente"
    o_que = f" ({', '.join(destaques)})" if destaques else ""
    if leitura == ONLINE:
        return f"Conversou com {com_quem}{o_que} e comprou com {vendedor}, do nosso time."
    if leitura == PERDA:
        # Na venda de outro corretor, a imobiliária diz com quem o cliente fechou
        if venda.get("imobiliaria") and _norm(venda["imobiliaria"]) not in _norm(vendedor):
            vendedor += f", da {venda['imobiliaria']}"
        return f"Conversou com {com_quem}{o_que}, mas comprou com {vendedor}."
    if motivo == "ja_com_outro":
        return f"Já estava com outro corretor{_citacao(achado['ja_com_outro'])}."
    if motivo == "sem_interesse":
        return f"Disse que não tinha interesse{_citacao(achado['sem_interesse'])}."
    if motivo == "pos_venda":
        return f"O contato foi de pós-venda, não de compra{_citacao(achado['pos_venda'])}."
    if motivo == "nao_seguiu":
        return "Pediu informações à GlorIA, mas não seguiu no atendimento" + (
            f"{_citacao(achado['sem_resposta'])}." if achado["sem_resposta"] else ".")
    return "Não respondeu à GlorIA nem ao SDR" + (f"{_citacao(achado['sem_resposta'])}." if achado["sem_resposta"] else ".")


# ---------------------------------------------------------------------------
# Revisão do analista
# ---------------------------------------------------------------------------

_trava = threading.Lock()


def revisoes() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(ARQUIVO_REVISOES):
        return {}
    try:
        with open(ARQUIVO_REVISOES, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def _gravar(dados: Dict[str, Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(ARQUIVO_REVISOES), exist_ok=True)
    tmp = ARQUIVO_REVISOES + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ARQUIVO_REVISOES)


def revisar(idreserva: Any, leitura: str, texto: Optional[str] = None) -> Dict[str, Any]:
    """Grava a leitura do analista para a venda. Sem texto, fica valendo o texto da leitura automática."""
    if leitura not in LEITURAS:
        raise ValueError(f"Leitura inválida: {leitura}. Use {', '.join(LEITURAS)}.")
    registro = {"leitura": leitura, "texto": (texto or "").strip() or None,
                "revisado_em": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with _trava:
        dados = revisoes()
        dados[str(idreserva)] = registro
        _gravar(dados)
    return registro


def desfazer(idreserva: Any) -> bool:
    """Volta a valer a leitura automática."""
    with _trava:
        dados = revisoes()
        existia = dados.pop(str(idreserva), None) is not None
        if existia:
            _gravar(dados)
    return existia


def aplicar(automatica: Optional[Dict[str, Any]], revisao: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """A leitura que vale: a revisada pelo analista, ou a automática."""
    automatica = automatica or {}
    if not revisao:
        return {**automatica, "revisada": False}
    return {**automatica, "leitura": revisao["leitura"], "motivo": "revisado",
            "texto": revisao.get("texto") or automatica.get("texto"), "revisada": True,
            "revisado_em": revisao.get("revisado_em"), "leitura_automatica": automatica.get("leitura")}
