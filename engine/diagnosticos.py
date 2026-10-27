"""
Diagnósticos de dados: tudo o que o sistema identifica que pode deixar um número errado.

Cada diagnóstico responde: o que aconteceu, por quê, em que período, se está pendente ou
resolvido e como resolver. A situação é decidida pelos próprios dados (ex.: os leads do
formulário voltaram a chegar ao CV) e fica guardada em histórico: quando o problema foi
visto pela primeira vez e quando deixou de acontecer. Só pendências que os dados não
conseguem comprovar (ex.: trocar uma chave de API) são encerradas manualmente.
"""

import json
import os
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from engine import bases, bi, conferencias
from engine.normalizer import EMPREENDIMENTO_DESCONHECIDO

HISTORICO_PATH = os.path.join(bases.BASES_DIR, "diagnosticos_historico.json")
LIMITE_IDADE_BASE_HORAS = float(os.getenv("DIAGNOSTICO_IDADE_BASE_HORAS", "6"))
SEVERIDADES = {"critico": 0, "atencao": 1, "info": 2}
CATEGORIAS = {
    "integracao": "Integração de leads",
    "atribuicao": "Origem e atribuição",
    "investimento": "Investimento em mídia",
    "qualidade": "Qualidade dos dados",
    "base": "Bases e conexões",
    "vendas": "Vendas",
    "regra": "Regras de cálculo",
    "seguranca": "Segurança",
    "sistema": "Sistema",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hoje() -> date:
    return datetime.now().date()


def _br(valor: Any) -> str:
    d = valor if isinstance(valor, date) else bi._data(valor)
    return d.strftime("%d/%m/%Y") if d else "—"


def _reais(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _periodo(inicio: Any, fim: Any) -> Dict[str, Optional[str]]:
    iso = lambda v: (v.isoformat() if isinstance(v, date) else (str(v)[:10] if v else None))
    return {"inicio": iso(inicio), "fim": iso(fim)}


def diagnostico(
    id_: str,
    categoria: str,
    severidade: str,
    situacao: str,
    titulo: str,
    o_que: str,
    por_que: str,
    como_resolver: List[str],
    periodo: Optional[Dict[str, Optional[str]]] = None,
    situacao_motivo: str = "",
    evidencias: Optional[List[Dict[str, str]]] = None,
    links: Optional[List[Dict[str, Any]]] = None,
    resolucao_manual: bool = False,
    chave_grupo: Optional[str] = None,
    resolvido_em_dados: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "resolvido_em_dados": resolvido_em_dados,
        "id": id_,
        "categoria": categoria,
        "categoria_label": CATEGORIAS.get(categoria, categoria),
        "severidade": severidade,
        "situacao": situacao,
        "titulo": titulo,
        "o_que": o_que,
        "por_que": por_que,
        "como_resolver": como_resolver,
        "periodo": periodo,
        "situacao_motivo": situacao_motivo,
        "evidencias": evidencias or [],
        "links": links or [],
        "resolucao_manual": resolucao_manual,
        "chave_grupo": chave_grupo,
    }


def _semana(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _mais_comum(valores: List[Any]) -> Any:
    valores = [v for v in valores if v]
    return Counter(valores).most_common(1)[0][0] if valores else None


def _link_conferencias(inicio: Any, fim: Any) -> Dict[str, Any]:
    p = _periodo(inicio, fim)
    return {
        "label": "Ver na tela de Conferências",
        "url": f"/conferencias?periodo=personalizado&inicio={p['inicio']}&fim={p['fim']}",
        "interno": True,
    }


# ---------------------------------------------------------------------------
# Formulários da Meta que deixaram de integrar
# ---------------------------------------------------------------------------


def episodios_de_falha(
    linhas: List[Dict[str, Any]],
    min_perdidos_semana: int = 2,
    pct_minimo: float = 20.0,
    min_chegadas_para_resolver: int = 5,
) -> List[Dict[str, Any]]:
    """
    Por formulário, junta as semanas em que os leads não chegaram ao CV.

    - Só conta perda CONFIRMADA ao vivo na API do CV.
    - Semana com falha: pelo menos 2 perdidos e 20% dos leads novos da semana.
    - Semanas com falha seguidas (ou separadas só por semanas sem nenhum lead) formam um episódio.
    - Resolvido: depois do episódio, 5 leads SEGUIDOS do formulário chegaram ao CV (a data é a do 5º lead).
    """
    por_form: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for linha in linhas:
        por_form[linha.get("formulario") or "—"].append(linha)

    saida: List[Dict[str, Any]] = []
    for form, leads in por_form.items():
        leads.sort(key=lambda l: l["data"])
        semanas: Dict[date, Dict[str, Any]] = defaultdict(lambda: {"leads": [], "novos": 0, "perdidos": 0})
        for l in leads:
            s = semanas[_semana(date.fromisoformat(l["data"]))]
            s["leads"].append(l)
            s["novos"] += int(l["status"] != "ja_era_lead")
            s["perdidos"] += int(l["status"] == "nao_chegou" and bool(l.get("confirmado")))

        ordem = sorted(semanas)
        com_falha = {
            w for w in ordem
            if semanas[w]["perdidos"] >= min_perdidos_semana and semanas[w]["perdidos"] / max(semanas[w]["novos"], 1) * 100 >= pct_minimo
        }
        grupos: List[List[date]] = []
        atual: List[date] = []
        for w in ordem:
            if w in com_falha:
                atual.append(w)
            elif atual:
                grupos.append(atual)
                atual = []
        if atual:
            grupos.append(atual)

        for n, grupo in enumerate(grupos):
            do_episodio = [l for w in grupo for l in semanas[w]["leads"]]
            perdidos = [l for l in do_episodio if l["status"] == "nao_chegou" and l.get("confirmado")]
            fim = max(l["data"] for l in perdidos)
            proximo = grupos[n + 1][0] if n + 1 < len(grupos) else None
            depois = [
                l for l in leads
                if l["data"] > fim and (proximo is None or _semana(date.fromisoformat(l["data"])) < proximo)
            ]
            chegaram_depois = [l for l in depois if l["status"] in ("no_cv", "ja_era_lead", "provavel_no_cv")]
            perdidos_depois = [l for l in depois if l["status"] == "nao_chegou" and l.get("confirmado")]
            # Voltou a funcionar quando N leads SEGUIDOS chegaram ao CV; uma perda isolada depois não reabre o episódio
            seguidos, resolvido_em = 0, None
            for l in depois:
                if l["status"] == "nao_chegou" and l.get("confirmado"):
                    seguidos = 0
                elif l["status"] in ("no_cv", "ja_era_lead", "provavel_no_cv"):
                    seguidos += 1
                    if seguidos >= min_chegadas_para_resolver:
                        resolvido_em = l["data"]
                        break
            resolvido = resolvido_em is not None
            saida.append({
                "formulario": form,
                "pagina": _mais_comum([l.get("pagina") for l in do_episodio]),
                "campanha": _mais_comum([l.get("campanha") for l in do_episodio]),
                "empreendimento": _mais_comum([l.get("empreendimento") for l in do_episodio]),
                "inicio": do_episodio[0]["data"],
                "fim": fim,
                "novos": sum(1 for l in do_episodio if l["status"] != "ja_era_lead"),
                "perdidos": len(perdidos),
                "perdidos_no_rd": sum(1 for l in perdidos if l.get("no_rd")),
                "a_confirmar": sum(1 for l in do_episodio if l["status"] == "nao_chegou" and not l.get("confirmado")),
                "chegaram_depois": len(chegaram_depois),
                "perdidos_depois": len(perdidos_depois),
                "resolvido": resolvido,
                "resolvido_em_dados": resolvido_em,
                "ultimo_lead_do_formulario": leads[-1]["data"],
            })
    return saida


def _diag_formularios(ctx: "Contexto") -> List[Dict[str, Any]]:
    f = ctx.formularios_meta()
    if not f:
        return []
    saida = []
    for ep in episodios_de_falha(f.get("linhas") or []):
        sem_rd = ep["perdidos"] - ep["perdidos_no_rd"]
        motivos = []
        if sem_rd:
            motivos.append(
                f"{sem_rd} não chegaram nem ao RD Station: o formulário não está enviando os leads para a integração "
                "(Meta → RD Station). O lead fica só na Central de Leads da página na Meta."
            )
        if ep["perdidos_no_rd"]:
            motivos.append(
                f"{ep['perdidos_no_rd']} chegaram ao RD Station e pararam: a integração RD Station → CV não criou o lead."
            )
        if ep["resolvido"]:
            isoladas = f" Depois disso houve {ep['perdidos_depois']} perda(s) isolada(s)." if ep["perdidos_depois"] else ""
            situacao_motivo = (
                f"Voltou a funcionar em {_br(ep['resolvido_em_dados'])}: 5 leads seguidos do formulário chegaram ao CV. "
                f"Após o episódio chegaram {ep['chegaram_depois']} leads.{isoladas}"
            )
        elif ep["chegaram_depois"] or ep["perdidos_depois"]:
            situacao_motivo = (
                f"Ainda não dá para dar como resolvido: depois de {_br(ep['fim'])} chegaram {ep['chegaram_depois']} lead(s) "
                f"e se perderam {ep['perdidos_depois']} (é preciso chegar 5 leads seguidos sem perda)."
            )
        else:
            situacao_motivo = f"Os leads continuam se perdendo — último lead perdido em {_br(ep['fim'])}."

        passos = [
            f"Na integração Meta → RD Station (Lead Ads), confira se o formulário \"{ep['formulario']}\" da página "
            f"\"{ep['pagina']}\" está selecionado para envio.",
            "Se a campanha já usa um formulário novo, pause este formulário antigo na campanha "
            f"\"{ep['campanha']}\" para não gerar leads sem integração.",
        ]
        if ep["perdidos_no_rd"]:
            passos.append("No RD Station, confira a automação/integração que cria o lead no CV para esses contatos.")
        passos.append(
            "Recupere os leads perdidos na tela Conferências → Meta Ads × CV → \"Leads para conferir no CV\" "
            "(Copiar tabela ou Baixar CSV) e cadastre-os no CV."
        )
        passos.append("Quando os leads voltarem a chegar, este diagnóstico muda sozinho para resolvido.")

        saida.append(diagnostico(
            f"formulario_meta:{ep['formulario']}:{ep['inicio']}",
            "integracao",
            "info" if ep["resolvido"] else ("critico" if ep["perdidos"] >= 5 else "atencao"),
            "resolvido" if ep["resolvido"] else "pendente",
            f"Formulário da Meta sem integração com o CV: {ep['formulario']}",
            f"{ep['perdidos']} de {ep['novos']} leads novos deste formulário não chegaram ao CV entre "
            f"{_br(ep['inicio'])} e {_br(ep['fim'])}. Todos foram procurados ao vivo na API do CV, em todos os leads, "
            "por e-mail e telefone.",
            " ".join(motivos) or "Os leads não chegaram ao CV.",
            passos,
            periodo=_periodo(ep["inicio"], ep["fim"]),
            situacao_motivo=situacao_motivo,
            evidencias=[
                {"rotulo": "Página", "valor": ep["pagina"] or "—"},
                {"rotulo": "Campanha", "valor": ep["campanha"] or "—"},
                {"rotulo": "Empreendimento", "valor": ep["empreendimento"] or "—"},
                {"rotulo": "Leads perdidos", "valor": f"{ep['perdidos']} de {ep['novos']} novos"},
                {"rotulo": "Chegaram ao RD e pararam", "valor": str(ep["perdidos_no_rd"])},
                {"rotulo": "Último lead do formulário", "valor": _br(ep["ultimo_lead_do_formulario"])},
                *([{"rotulo": "Ainda em confirmação ao vivo", "valor": str(ep["a_confirmar"])}] if ep["a_confirmar"] else []),
            ],
            links=[_link_conferencias(ep["inicio"], ep["fim"])],
            chave_grupo=f"formulario_meta:{ep['formulario']}",
            resolvido_em_dados=ep["resolvido_em_dados"],
        ))

    pendentes = (f.get("confirmacao") or {}).get("pendentes") or 0
    if pendentes:
        saida.append(diagnostico(
            "confirmacao_ao_vivo_em_andamento",
            "sistema",
            "info",
            "pendente",
            "Confirmação ao vivo em andamento",
            f"{pendentes} lead(s) de formulário da Meta ainda estão sendo procurados na API do CV e do RD.",
            "Nenhum lead é contado como perdido antes dessa confirmação, então os diagnósticos de integração podem mudar "
            "nos próximos minutos.",
            ["Aguarde alguns minutos e recarregue esta tela."],
            periodo=None,
            situacao_motivo="Muda para resolvido quando todos os leads forem confirmados.",
        ))
    return saida


def _diag_atribuicao_meta(ctx: "Contexto") -> List[Dict[str, Any]]:
    f = ctx.formularios_meta()
    if not f:
        return []
    fim = bi._data(f["cobertura"]["fim"]) or _hoje()
    inicio = fim - timedelta(days=29)
    errados = [
        l for l in f.get("linhas") or []
        if l["status"] == "no_cv" and l.get("cv_canal") and "Meta" not in l["cv_canal"]
        and inicio <= date.fromisoformat(l["data"]) <= fim
    ]
    if len(errados) < 5:
        return []
    canais = Counter(l["cv_canal"] for l in errados)
    chegaram = sum(1 for l in f["linhas"] if l["status"] == "no_cv" and inicio <= date.fromisoformat(l["data"]) <= fim)
    return [diagnostico(
        "meta_credito_errado_no_cv",
        "atribuicao",
        "atencao",
        "pendente",
        "Leads de anúncio da Meta registrados no CV com outra origem",
        f"Nos últimos 30 dias de formulários ({_br(inicio)} a {_br(fim)}), {len(errados)} de {chegaram} leads que vieram "
        "de formulário de anúncio da Meta estão no CV com outra mídia.",
        "O CV guardou a mídia de outro contato da pessoa (ex.: WhatsApp) em vez do anúncio. Esses leads saem da conta da "
        "Meta nos indicadores e o custo por lead da Meta aparece maior do que o real.",
        [
            "Na integração que cria o lead no CV, envie a mídia 'Facebook Ads'/'Instagram Ads' e as UTMs do anúncio.",
            "Revise se a mídia principal do lead no CV é sobrescrita quando a pessoa volta a falar pelo WhatsApp.",
        ],
        periodo=_periodo(inicio, fim),
        situacao_motivo="Fica pendente enquanto houver 5 ou mais casos nos últimos 30 dias.",
        evidencias=[{"rotulo": canal, "valor": f"{q} lead(s)"} for canal, q in canais.most_common(5)],
        links=[_link_conferencias(inicio, fim)],
    )]


# ---------------------------------------------------------------------------
# Investimento
# ---------------------------------------------------------------------------


def _diag_contas_sem_acesso(ctx: "Contexto") -> List[Dict[str, Any]]:
    fim = _hoje()
    inicio = fim - timedelta(days=89)
    conf = conferencias.conferencia_plataforma(inicio, fim, "meta")
    links = (bases.resumo("meta_insights").get("status") or {}).get("help_links") or []
    saida = []
    for row in conf.get("por_empreendimento") or []:
        if row["empreendimento"] == EMPREENDIMENTO_DESCONHECIDO or row["leads_plataforma"] or row["investimento"]:
            continue
        if row["leads_crm"] < 10:
            continue
        saida.append(diagnostico(
            f"meta_sem_conta:{row['empreendimento']}",
            "investimento",
            "atencao",
            "pendente",
            f"Sem investimento da Meta para {row['empreendimento']}",
            f"{row['leads_crm']} leads de Meta Ads chegaram ao CV para este empreendimento entre {_br(inicio)} e {_br(fim)}, "
            "mas nenhuma conta de anúncio lida pelo sistema tem investimento dele.",
            "A conta de anúncio desse empreendimento não está compartilhada com o usuário do sistema do token da Meta, ou "
            "as campanhas não citam o nome do empreendimento. Sem isso, custo por lead e conferência Meta × CV ficam sem base.",
            [
                "No Business Manager, dê ao usuário do sistema do token acesso à conta de anúncio deste empreendimento "
                "(permissão ads_read e leads_retrieval).",
                "Se a conta já está liberada, inclua o nome do empreendimento no nome da conta ou das campanhas.",
                "Atualize a base 'Meta Ads — Investimento e leads' em Bases e integrações.",
            ],
            periodo=_periodo(inicio, fim),
            situacao_motivo="Muda para resolvido quando aparecer investimento da Meta para o empreendimento.",
            evidencias=[{"rotulo": "Leads de Meta Ads no CV", "valor": str(row["leads_crm"])}],
            links=[{"label": l.get("label") or "Ajuda", "url": l.get("url"), "interno": False} for l in links if l.get("url")][:2],
        ))
    return saida


def _diag_investimento_sem_empreendimento(ctx: "Contexto") -> List[Dict[str, Any]]:
    fim = _hoje()
    inicio = fim - timedelta(days=89)
    catalogo = bases.registros("cv_empreendimentos")
    por_conta: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"valor": 0.0, "campanhas": Counter()})
    for r in bi._insights_com_empreendimento(catalogo):
        if r["empreendimento"] != EMPREENDIMENTO_DESCONHECIDO or not r["data_d"] or not (inicio <= r["data_d"] <= fim):
            continue
        conta = por_conta[f"{r['plataforma']}|{r.get('conta_nome') or r.get('conta_id')}"]
        conta["valor"] += r["investimento"]
        conta["campanhas"][r.get("campanha_nome") or "—"] += r["investimento"]
    saida = []
    for chave, c in por_conta.items():
        if c["valor"] < 1:
            continue
        plataforma, conta = chave.split("|", 1)
        saida.append(diagnostico(
            f"investimento_sem_empreendimento:{chave}",
            "investimento",
            "info",
            "pendente",
            f"Investimento sem empreendimento na conta {conta}",
            f"{_reais(c['valor'])} investidos na conta \"{conta}\" ({'Meta' if plataforma == 'meta' else 'Google'}) entre "
            f"{_br(inicio)} e {_br(fim)} não foram atribuídos a nenhum empreendimento.",
            "Nem o nome da conta nem o das campanhas cita um empreendimento do CV (ex.: publicações institucionais "
            "impulsionadas). O valor fica fora do custo por lead dos empreendimentos.",
            [
                "Se for mídia institucional, nenhuma ação é necessária.",
                "Se for de um empreendimento, inclua o nome dele no nome da campanha.",
            ],
            periodo=_periodo(inicio, fim),
            situacao_motivo="Informativo: fica listado enquanto houver investimento sem empreendimento nos últimos 90 dias.",
            evidencias=[{"rotulo": nome, "valor": _reais(v)} for nome, v in c["campanhas"].most_common(5)],
        ))
    return saida


# ---------------------------------------------------------------------------
# BeeViral e qualidade
# ---------------------------------------------------------------------------


def _diag_beeviral(ctx: "Contexto") -> List[Dict[str, Any]]:
    if not bases.registros("beeviral"):
        return []
    fim = _hoje()
    inicio = fim - timedelta(days=89)
    r = conferencias.conferencia_beeviral(inicio, fim)
    s = r["resumo"]
    saida = []
    if s["sem_credito"] >= 3:
        saida.append(diagnostico(
            "beeviral_sem_credito",
            "atribuicao",
            "atencao",
            "pendente",
            "Indicações da BeeViral no CV sem o crédito da BeeViral",
            f"{s['sem_credito']} indicações de {_br(inicio)} a {_br(fim)} chegaram ao CV com outra origem.",
            "O lead foi cadastrado pelo comercial ou por outro canal e a origem 'BeeViral / Indique e Ganhe' se perdeu. "
            "A indicação não é medida nem creditada corretamente.",
            [
                "Oriente o comercial a manter a mídia de indicação BeeViral ao cadastrar esses leads.",
                "Confira se a integração BeeViral → CV preenche os campos de indicação e a mídia.",
            ],
            periodo=_periodo(inicio, fim),
            situacao_motivo="Fica pendente enquanto houver 3 ou mais casos nos últimos 90 dias.",
            evidencias=[{"rotulo": c["canal"], "valor": f"{c['indicacoes']} indicação(ões)"} for c in r["credito_no_cv"][:5]],
            links=[_link_conferencias(inicio, fim)],
        ))
    if s["nao_chegou"] >= 3:
        saida.append(diagnostico(
            "beeviral_nao_chegou",
            "integracao",
            "atencao",
            "pendente",
            "Indicações da BeeViral que não chegaram ao CV",
            f"{s['nao_chegou']} indicações de {_br(inicio)} a {_br(fim)} não foram encontradas no CV (busca em todos os "
            "leads, por UUID da RD, e-mail e telefone).",
            "A indicação ficou só na BeeViral: a integração não criou o lead no CV ou o indicado não foi cadastrado.",
            [
                "Confira a integração BeeViral → CV para essas indicações.",
                "Veja a lista na tela Conferências → BeeViral × CV e cadastre os indicados no CV.",
            ],
            periodo=_periodo(inicio, fim),
            situacao_motivo="Fica pendente enquanto houver 3 ou mais indicações sem lead no CV nos últimos 90 dias.",
            links=[_link_conferencias(inicio, fim)],
        ))
    return saida


def _diag_qualidade(ctx: "Contexto") -> List[Dict[str, Any]]:
    if not bases.registros("cv_leads"):
        return []
    fim = _hoje()
    inicio = fim - timedelta(days=29)
    k = bi.calcular_bi(inicio, fim)["kpis"]
    if not k["leads"] or (k["pct_nao_rastreado"] or 0) < 10:
        return []
    return [diagnostico(
        "qualidade_sem_origem",
        "qualidade",
        "atencao",
        "pendente",
        "Leads sem origem registrada no CV",
        f"{k['nao_rastreado']} de {k['leads']} leads ({k['pct_nao_rastreado']}%) de {_br(inicio)} a {_br(fim)} não têm UTM, "
        "mídia reconhecível nem tag de origem.",
        "Esses leads não entram em nenhum canal: o total online e a atribuição por mídia ficam subestimados.",
        [
            "Preencha a mídia ao cadastrar leads manualmente no CV.",
            "Garanta que as integrações (site, WhatsApp, formulários) enviem UTM e mídia.",
        ],
        periodo=_periodo(inicio, fim),
        situacao_motivo="Fica pendente enquanto 10% ou mais dos leads dos últimos 30 dias estiverem sem origem.",
    )]


# ---------------------------------------------------------------------------
# Bases, conexões e permissões
# ---------------------------------------------------------------------------

IMPACTO_BASE = {
    "cv_leads": "BI, funil e todas as conferências usam esta base.",
    "cv_indice": "Sem o índice, leads antigos só são reconhecidos pela confirmação ao vivo.",
    "cv_empreendimentos": "Empreendimentos podem não ser reconhecidos em campanhas e formulários.",
    "beeviral": "A conferência BeeViral × CV fica indisponível ou desatualizada.",
    "meta_insights": "Investimento, custo por lead e conferência Meta × CV ficam indisponíveis ou desatualizados.",
    "google_insights": "Investimento, custo por lead e conferência do Google Ads ficam indisponíveis.",
    "meta_leads": "A conferência lead a lead dos formulários da Meta fica indisponível ou desatualizada.",
    "rd_leads": "A conferência RD Station × CV fica indisponível ou desatualizada.",
    "rd_conversoes": "A classificação dos contatos do RD fora do CV fica incompleta.",
}


def _diag_bases(ctx: "Contexto") -> List[Dict[str, Any]]:
    saida = []
    for b in bases.listar():
        if not b["essencial"]:
            continue
        status = b.get("status") or {}
        modo, mensagem = status.get("mode"), status.get("message") or ""
        links = [{"label": l.get("label") or "Onde resolver", "url": l.get("url"), "interno": False}
                 for l in status.get("help_links") or [] if l.get("url")][:3]
        acao = [status["action"]] if status.get("action") else []
        impacto = IMPACTO_BASE.get(b["base"], "")
        if modo == "erro":
            saida.append(diagnostico(
                f"base_erro:{b['base']}", "base", "critico", "pendente",
                f"A base '{b['label']}' não atualizou",
                f"A última atualização falhou. {('Os dados em uso são de ' + _br(b['dados_de']) + '.') if b.get('dados_de') else 'Não há dados salvos.'}",
                f"{mensagem} {impacto}".strip(),
                acao + ["Depois de corrigir, clique em 'Atualizar dados' no topo do painel."],
                situacao_motivo="Muda para resolvido na primeira atualização bem-sucedida.",
                links=links + [{"label": "Bases e integrações", "url": "/bases", "interno": True}],
            ))
        elif modo == "nao_configurado":
            saida.append(diagnostico(
                f"base_nao_configurada:{b['base']}", "base", "atencao", "pendente",
                f"'{b['label']}' não está conectada",
                mensagem,
                impacto,
                acao + ["Depois de configurar, atualize a base em Bases e integrações."],
                situacao_motivo="Muda para resolvido quando a base for baixada com dados reais.",
                links=links + [{"label": "Bases e integrações", "url": "/bases", "interno": True}],
            ))
        elif modo == "real" and (b.get("idade_horas") or 0) > LIMITE_IDADE_BASE_HORAS:
            saida.append(diagnostico(
                f"base_desatualizada:{b['base']}", "base", "atencao", "pendente",
                f"'{b['label']}' está desatualizada",
                f"Última atualização há {b['idade_horas']} horas ({_br(b['dados_de'])}).",
                f"A atualização automática pode estar desligada ou falhando. {impacto}".strip(),
                ["Clique em 'Atualizar dados' no topo do painel.",
                 "Mantenha a engine rodando com a atualização automática (BASES_AGENDADOR) ativa."],
                situacao_motivo=f"Muda para resolvido quando a base tiver menos de {int(LIMITE_IDADE_BASE_HORAS)} horas.",
                links=[{"label": "Bases e integrações", "url": "/bases", "interno": True}],
            ))
        if modo == "real" and "Atenção" in mensagem:
            saida.append(diagnostico(
                f"base_incompleta:{b['base']}", "base", "atencao", "pendente",
                f"'{b['label']}' pode estar incompleta",
                mensagem,
                f"A quantidade baixada não bate com a informada pela fonte. {impacto}".strip(),
                ["Atualize a base de novo em Bases e integrações.", "Se continuar, verifique o log da engine."],
                situacao_motivo="Muda para resolvido quando a contagem bater.",
                links=[{"label": "Bases e integrações", "url": "/bases", "interno": True}],
            ))
    return saida


def _diag_pendencias_manuais(ctx: "Contexto") -> List[Dict[str, Any]]:
    return [
        diagnostico(
            "powerbi_chave_novo_horizonte",
            "qualidade",
            "critico",
            "pendente",
            "Power BI FM&D quebra o filtro do Novo Horizonte de Itatinga",
            "Na auditoria de 29/09/2026, a matriz do relatório exibiu Itatinga - Novo Horizonte - 16101, "
            "mas o filtro de empreendimento ofereceu Itatinga - Novo Horizonte - 16103. Ao selecionar 16103, "
            "todos os indicadores do produto ficaram zerados.",
            "A dimensão de empreendimento e a tabela de fatos usam chaves diferentes. O código oficial atual no "
            "catálogo e nos leads do CV é 16103; por isso o relacionamento do Power BI não encontra os fatos ligados a 16101.",
            [
                "No Power Query ou na origem do modelo, remapeie 16101 para o código oficial 16103.",
                "Atualize a dimensão e as tabelas de leads, vendas e investimento com a mesma chave.",
                "Publique e atualize o conjunto de dados; depois valide o filtro 16103 em todas as páginas.",
            ],
            periodo=_periodo("2026-09-01", "2026-09-30"),
            situacao_motivo="Depende da correção e publicação do modelo externo; encerre depois de validar o filtro 16103.",
            evidencias=[
                {"rotulo": "Chave na matriz", "valor": "16101"},
                {"rotulo": "Chave oficial/filtro", "valor": "16103"},
                {"rotulo": "Resultado ao filtrar", "valor": "0"},
            ],
            links=[
                {"label": "Power BI FM&D", "url": "https://app.powerbi.com/view?r=eyJrIjoiNjNjNzE1NWQtMDNiNy00Y2MzLTg2MTMtZTYzZWEyYzliMzViIiwidCI6IjM4OTYxZDJlLWE3MjEtNGI0YS1iMGZmLTRjZmM5YTI3MGEzZiJ9", "interno": False},
            ],
            resolucao_manual=True,
        ),
        diagnostico(
            "powerbi_criterios_leads_vendas_investimento",
            "regra",
            "atencao",
            "pendente",
            "Os Power BIs e o app usam critérios diferentes para números com o mesmo nome",
            "No período de 01/09 a 30/09/2026, com o filtro Online, o Gerencial do Power BI FM&D mostrou 989 conversões únicas, "
            "825 mudanças para Novo Lead MQL, 259 SQL e 8 vendas SDR. O Power BI Moura Leite mostrou 890 MQL por última conversão "
            "e 258 SQL na tabela. Os cartões de Vendas e VGV da Moura Leite não entram na comparação online porque ignoram o filtro de origem. "
            "No app, o recorte equivalente contém somente registros com origem online comprovada.",
            "Os relatórios usam fatos e calendários diferentes com o mesmo rótulo. O MQL do Power BI Moura Leite vem da última conversão; "
            "o funil do Power BI FM&D usa fatos de movimentação. Comparar cartões que não recebem o mesmo filtro de origem "
            "produz divergência mesmo quando período e produto parecem iguais.",
            [
                "Defina no Power BI nomes distintos para cadastro, conversão, pessoa única, interesse e unidade vendida.",
                "Use data de cadastro para aquisição; data da venda para unidades; e mantenha conversão de etapa em um funil separado.",
                "Inclua Google Ads no investimento ou identifique o cartão como Meta gerenciada pela agência.",
                "Compare produto a produto somente depois de corrigir as chaves e igualar período, origem, escopo e instante de atualização.",
            ],
            periodo=_periodo("2026-09-01", "2026-09-30"),
            situacao_motivo="Depende da padronização das medidas e rótulos nos relatórios externos.",
            evidencias=[
                {"rotulo": "Power BI FM&D · Online", "valor": "989 conversões · 825 Novo Lead MQL · 259 SQL · 8 vendas SDR"},
                {"rotulo": "Power BI Moura Leite · Online", "valor": "890 MQL · 258 SQL na tabela · Vendas/VGV sem filtro de origem"},
            ],
            links=[
                {"label": "Power BI FM&D", "url": "https://app.powerbi.com/view?r=eyJrIjoiNjNjNzE1NWQtMDNiNy00Y2MzLTg2MTMtZTYzZWEyYzliMzViIiwidCI6IjM4OTYxZDJlLWE3MjEtNGI0YS1iMGZmLTRjZmM5YTI3MGEzZiJ9", "interno": False},
                {"label": "Power BI Moura Leite", "url": "https://app.powerbi.com/groups/398282cf-57bc-4ec4-9c66-f009d5df50d7/reports/9451633a-65cd-4347-b90b-9e11bf29b1f7/1495ec053c31e7a2e000", "interno": False},
            ],
            resolucao_manual=True,
        ),
        diagnostico(
            "powerbi_publico_filtro_online_parcial",
            "regra",
            "critico",
            "pendente",
            "O filtro Online do Power BI FM&D não alcança todos os visuais",
            "Na página Follow Up, em setembro/2026, selecionar tipo = On alterou SQL, agendamentos e descartes, "
            "mas não alterou os cartões de leads, vendas e VGV. Esses cartões não podem ser usados como números online.",
            "Há medidas ou relacionamentos que removem/ignoram o filtro de origem. Por isso, a página não representa "
            "um único escopo online mesmo quando a segmentação mostra On.",
            [
                "Faça todas as medidas da página receberem a mesma dimensão de origem normalizada.",
                "Evite ALL/REMOVEFILTERS sobre origem nas medidas que devem respeitar o recorte Online.",
                "Crie um teste de regressão comparando cada visual com tipo = Todos e tipo = On.",
            ],
            periodo=_periodo("2026-09-01", "2026-09-30"),
            situacao_motivo="Depende da correção e publicação do relatório da FM&D.",
            evidencias=[
                {"rotulo": "Filtro Todos → Online", "valor": "SQL, agendamentos e descartes mudam"},
                {"rotulo": "Cartões ignorando o filtro", "valor": "Leads, vendas e VGV permanecem iguais"},
            ],
            links=[
                {"label": "Power BI FM&D", "url": "https://app.powerbi.com/view?r=eyJrIjoiNjNjNzE1NWQtMDNiNy00Y2MzLTg2MTMtZTYzZWEyYzliMzViIiwidCI6IjM4OTYxZDJlLWE3MjEtNGI0YS1iMGZmLTRjZmM5YTI3MGEzZiJ9", "interno": False},
            ],
            resolucao_manual=True,
        ),
        diagnostico(
            "powerbi_privado_contextos_inconsistentes",
            "regra",
            "critico",
            "pendente",
            "Vendas e VGV do Power BI Moura Leite ignoram o filtro de origem",
            "Em setembro/2026 e sem filtro de praça ou empreendimento, o Gerencial SDR mostrou 329 SQL no cartão e 258 "
            "na tabela. Ao selecionar somente Google em Origem (Online), MQL caiu de 890 para 54, SQL para 12 e agendamentos para 1, "
            "mas Vendas permaneceu em 14 e VGV em R$ 1,29 mi.",
            "Os visuais apontam para medidas, granularidades ou relacionamentos diferentes. O modelo semântico confirma "
            "tabelas-fato separadas de conversões, qualificações, OPPS, visitas e vendas. A tabela-fato de vendas não está sendo filtrada pela dimensão "
            "de origem; por isso seus cartões não representam o recorte online selecionado.",
            [
                "Troque os títulos genéricos pelas definições completas e publique a fórmula de cada medida.",
                "No cartão SQL, use a mesma medida de pessoa única da tabela e da taxa de conversão.",
                "Faça Vendas e VGV receberem a mesma dimensão origem_normatizada usada por MQL, SQL e OPPS.",
                "Adicione data/hora da extração e um identificador de atualização em todas as páginas.",
            ],
            periodo=_periodo("2026-09-01", "2026-09-30"),
            situacao_motivo="Depende da correção e republicação do modelo semântico da Moura Leite.",
            evidencias=[
                {"rotulo": "SQL cartão", "valor": "329"},
                {"rotulo": "SQL tabela", "valor": "258"},
                {"rotulo": "Somente Google", "valor": "54 MQL · 12 SQL · 1 agendamento"},
                {"rotulo": "Cartões que não mudaram", "valor": "14 vendas · R$ 1,29 mi"},
            ],
            links=[
                {"label": "Power BI Moura Leite", "url": "https://app.powerbi.com/groups/398282cf-57bc-4ec4-9c66-f009d5df50d7/reports/9451633a-65cd-4347-b90b-9e11bf29b1f7/1495ec053c31e7a2e000", "interno": False},
            ],
            resolucao_manual=True,
        ),
        diagnostico(
            "regra_funil_bi_gerencial",
            "regra",
            "atencao",
            "pendente",
            "Funil (SQL e Agendamentos) com regra diferente do BI gerencial",
            "Em uma conferência anterior, o funil não fechou: em Central Parque II, de 01/09 a "
            "14/09/2026, o BI gerencial mostra SQL 18 e Agendamentos 1; o app mostra 23 e 9.",
            "O app conta a etapa mais avançada pelo histórico do lead (tags e tarefas). O modelo do Power BI Moura Leite usa as tabelas "
            "vw_fato_qualificacoes e vw_fato_opps, que não estão disponíveis na API de leads do CV. Sem essas fatos, o app "
            "consegue uma estimativa auditável, mas não deve rotulá-la como o SQL certificado do Power BI.",
            [
                "Dê ao app acesso somente leitura às views de qualificações, OPPS e visitas, ou exporte essas fatos para uma base consumível.",
                "Publique as fórmulas DAX de pessoa única e data de referência de SQL e Agendamentos.",
                "Até lá, mantenha o indicador do app identificado como 'detectado no histórico'.",
            ],
            situacao_motivo="Depende de uma informação externa: encerrado manualmente.",
            resolucao_manual=True,
        ),
        diagnostico(
            "credenciais_compartilhadas",
            "seguranca",
            "atencao",
            "pendente",
            "Chaves de API compartilhadas em conversa precisam ser trocadas",
            "A chave da API do RD Station, o client secret do aplicativo do RD e o token da Meta foram enviados por chat.",
            "Quem tiver acesso à conversa pode usar essas chaves para ler os dados de leads e clientes.",
            [
                "RD Station: gere uma nova chave de API e um novo client secret do aplicativo; atualize o engine/.env e "
                "autorize de novo com engine/rd_oauth.py.",
                "Meta: gere um novo token do usuário do sistema no Business Manager e atualize META_ACCESS_TOKEN.",
                "Depois, marque este item como resolvido.",
            ],
            situacao_motivo="Não dá para comprovar pelos dados: encerrado manualmente.",
            resolucao_manual=True,
        ),
    ]


def _diag_vendas_online_nao_contabilizadas(ctx: "Contexto") -> List[Dict[str, Any]]:
    from engine import auditoria_vendas

    if not bases.registros("cv_reservas"):
        return []
    fim = _hoje()
    inicio = fim - timedelta(days=29)
    r = auditoria_vendas.auditar(inicio, fim)
    s = r["resumo"]
    n, p = s["online_nao_contabilizada"], s["provavel_online"]
    if n < 3 and n + p < 10:
        return []
    return [diagnostico(
        "vendas_online_nao_contabilizadas",
        "vendas",
        "atencao",
        "pendente",
        "Vendas com origem online que não contam como online",
        f"De {_br(inicio)} a {_br(fim)}: {n} venda(s) ({_reais(s['vgv_online_nao_contabilizada'])}) com evidência forte de "
        f"origem online e {p} provável(is) ({_reais(s['vgv_provavel_online'])}, só pela mídia escolhida na reserva), mas o "
        "lead ligado à venda não é online ou a venda não tem lead no CV.",
        "A reserva foi feita sem associar o lead que veio da mídia, ou o lead ficou com a mídia do comercial. As vendas "
        "online e o retorno da mídia ficam subestimados.",
        [
            "Abra a tela Vendas × leads e confira cada venda da lista (cada uma traz a evidência e o link do lead).",
            "No CV, associe a reserva ao lead online ou ajuste a mídia do lead.",
            "Oriente o comercial a sempre fazer a reserva a partir do lead já existente.",
        ],
        periodo=_periodo(inicio, fim),
        situacao_motivo="Fica pendente enquanto houver, nos últimos 30 dias, 3 ou mais vendas com evidência forte ou 10 ou "
                        "mais somando as prováveis.",
        evidencias=[{"rotulo": x["label"], "valor": f"{x['vendas']} venda(s)"} for x in r["por_sinal"] if x["vendas"]][:5],
        links=[{"label": "Ver em Vendas × leads", "url": f"/vendas?periodo=personalizado&inicio={inicio}&fim={fim}", "interno": True}],
    )]


DETECTORES: List[Callable[["Contexto"], List[Dict[str, Any]]]] = [
    _diag_bases,
    _diag_formularios,
    _diag_atribuicao_meta,
    _diag_contas_sem_acesso,
    _diag_investimento_sem_empreendimento,
    _diag_beeviral,
    _diag_qualidade,
    _diag_vendas_online_nao_contabilizadas,
    _diag_pendencias_manuais,
]


# ---------------------------------------------------------------------------
# Correções já feitas no sistema (registro permanente)
# ---------------------------------------------------------------------------

CORRECOES: List[Dict[str, Any]] = [
    {
        "id": "reservas_cv_endereco",
        "data": "2026-09-15",
        "titulo": "Reservas do CV apareciam como \"sem permissão\"",
        "o_que": "O app dizia que o token do CV não tinha acesso às reservas e mandava carregar uma planilha de vendas.",
        "por_que": "A consulta usava o endereço /api/cvio/reserva, que o CV bloqueia. O mesmo token lê as reservas pelo "
                   "endereço /api/v1/comercial/reservas; como a listagem só traz a carga histórica, cada reserva é lida pelo ID.",
        "como_foi_resolvido": [
            "Nova base 'CV — Reservas e vendas': situação, data da venda, empreendimento e unidade, valor, corretor e lead associado.",
            "O aviso de permissão saiu dos diagnósticos e a planilha de vendas ficou só como conferência opcional.",
        ],
        "impacto": "Cerca de 4,2 mil reservas do CV passam a estar disponíveis para as análises de vendas.",
    },
    {
        "id": "vendas_beeviral_duplicadas",
        "data": "2026-09-14",
        "titulo": "Vendas das indicações da BeeViral contadas mais de uma vez",
        "o_que": "Últimos 90 dias: o app mostrava 24 vendas e R$ 3,16 mi de VGV vindos de indicações.",
        "por_que": "A venda era contada uma vez por indicação: quem foi indicado 2 ou 3 vezes tinha a mesma venda somada de "
                   "novo. Vendas feitas antes da indicação também entravam na conta.",
        "como_foi_resolvido": [
            "Uma venda por lead do CV, com as campanhas e o número de vezes que a pessoa foi indicada.",
            "Venda anterior à primeira indicação fica marcada e fora da contagem e do VGV.",
        ],
        "impacto": "Últimos 90 dias: 18 vendas e R$ 2,57 mi (3 repetidas e 3 anteriores à indicação saíram da soma).",
    },
    {
        "id": "leads_antigos_como_nao_chegou",
        "data": "2026-09-14",
        "titulo": "Leads antigos apareciam como \"não chegou no CV\"",
        "o_que": "Na conferência dos formulários da Meta, 282 dos 328 leads apontados como perdidos nos últimos 90 dias já "
                 "existiam no CV (19 dos 31 de setembro).",
        "por_que": "A busca usava só a base de 12 meses do CV: quem se cadastrou antes disso não era encontrado.",
        "como_foi_resolvido": [
            "Nova base 'CV — Índice de todos os leads' com os mais de 53 mil leads da conta, de qualquer data.",
            "Confirmação ao vivo na API do CV e do RD antes de mostrar qualquer lead como perdido.",
        ],
        "impacto": "Últimos 90 dias: de 328 para 59 leads realmente perdidos.",
    },
    {
        "id": "cv_400_nao_encontrado",
        "data": "2026-09-14",
        "titulo": "Busca sem resultado no CV era tratada como falha",
        "o_que": "Leads que realmente não existem no CV ficavam eternamente \"em confirmação\".",
        "por_que": "A API do CV responde HTTP 400 \"Lead não encontrado\" quando não acha ninguém, em vez de uma lista vazia.",
        "como_foi_resolvido": ["Essa resposta passou a ser lida como consulta válida sem resultado; outros erros continuam como falha."],
        "impacto": "Os 12 leads perdidos de setembro passaram a ser confirmados.",
    },
    {
        "id": "paginacao_cv",
        "data": "2026-09-14",
        "titulo": "Base de 12 meses do CV perdia leads do período",
        "o_que": "8 leads cadastrados dentro do período não estavam na base salva.",
        "por_que": "A API do CV não ordena estritamente pela data de cadastro e o download parava na primeira página com "
                   "lead mais antigo que o período.",
        "como_foi_resolvido": ["O download só para depois de duas páginas inteiras anteriores ao período."],
        "impacto": "Base passou de 9.913 para 9.921 leads.",
    },
    {
        "id": "regra_mql_bi_gerencial",
        "data": "2026-09-14",
        "titulo": "Contagem de leads não batia com o BI gerencial",
        "o_que": "Central Parque II, 01 a 14/09: o app mostrava 71 leads e o BI gerencial 81.",
        "por_que": "O app contava pela data de cadastro e pelo primeiro empreendimento do lead; o BI gerencial conta pela "
                   "última conversão e pelo interesse mais recente.",
        "como_foi_resolvido": [
            "Lead passou a contar no mês da última conversão e no empreendimento de interesse mais recente.",
            "Venda continua no empreendimento principal. Painel passou a mostrar só leads online.",
        ],
        "impacto": "81 leads, 2 vendas e R$ 191,9 mil de VGV online, iguais ao BI gerencial (até a hora da atualização dele).",
    },
    {
        "id": "mirante_reserva_unificados",
        "data": "2026-09-14",
        "titulo": "Mirante dos Ramos e Reserva dos Ramos apareciam separados",
        "o_que": "O investimento e os formulários estavam em Mirante dos Ramos e os leads no CV em Reserva dos Ramos.",
        "por_que": "O CV registra os leads do Mirante como Reserva dos Ramos Residencial.",
        "como_foi_resolvido": ["Os dois passaram a ser um só empreendimento: Tatuí - Reserva dos Ramos Residencial - 14704."],
        "impacto": "Custo por lead e conferência Meta × CV de Reserva dos Ramos passaram a considerar os R$ 31,5 mil da conta Mirante.",
    },
    {
        "id": "contas_meta",
        "data": "2026-09-14",
        "titulo": "Só 5 das 11 contas de anúncio da Meta eram lidas",
        "o_que": "Investimento da Meta subestimado.",
        "por_que": "A lista de contas estava fixa na configuração.",
        "como_foi_resolvido": ["O sistema passou a ler todas as contas que o token enxerga, mês a mês."],
        "impacto": "13 meses: de R$ 163,9 mil para R$ 173,8 mil investidos.",
    },
    {
        "id": "empreendimento_pela_conta",
        "data": "2026-09-14",
        "titulo": "Leads de formulário de Avaré 2 sem empreendimento",
        "o_que": "159 leads de formulário apareciam como \"Não identificado\".",
        "por_que": "O nome da campanha (\"avare-2-central\") não citava o nome completo do empreendimento.",
        "como_foi_resolvido": ["O empreendimento passou a vir da conta de anúncio da campanha; \"Alta Vista\" passou a ser reconhecido como Altavista."],
        "impacto": "Perdas de Central Parque II e Reserva Central Parque II passaram a aparecer no empreendimento certo.",
    },
]


# ---------------------------------------------------------------------------
# Histórico e cálculo
# ---------------------------------------------------------------------------

_trava = threading.Lock()


class Contexto:
    def __init__(self, historico: Dict[str, Any]):
        self.historico = historico
        self._formularios: Any = None

    def formularios_meta(self) -> Optional[Dict[str, Any]]:
        """Conferência dos formulários sobre toda a janela que a Meta devolve (calculada uma vez)."""
        if self._formularios is None:
            datas = [bi._data(l.get("created_at")) for l in bases.registros("meta_leads")]
            datas = [d for d in datas if d]
            self._formularios = (
                (conferencias.conferencia_plataforma(min(datas), max(datas), "meta").get("formularios") or {}) if datas else {}
            )
        return self._formularios or None


def _ler_historico() -> Dict[str, Any]:
    if not os.path.exists(HISTORICO_PATH):
        return {}
    try:
        with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _gravar_historico(historico: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(HISTORICO_PATH), exist_ok=True)
    tmp = HISTORICO_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False)
    os.replace(tmp, HISTORICO_PATH)


def _sobrepoe(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]], folga_dias: int = 7) -> bool:
    if not a or not b or not a.get("inicio") or not b.get("inicio"):
        return False
    a_ini, a_fim = date.fromisoformat(a["inicio"]), date.fromisoformat(a.get("fim") or a["inicio"])
    b_ini, b_fim = date.fromisoformat(b["inicio"]), date.fromisoformat(b.get("fim") or b["inicio"])
    return a_ini <= b_fim + timedelta(days=folga_dias) and b_ini <= a_fim + timedelta(days=folga_dias)


def consolidar(itens: List[Dict[str, Any]], historico: Dict[str, Any], agora: str) -> List[Dict[str, Any]]:
    """
    Junta o que foi detectado agora com o histórico:
      - mantém a data da primeira detecção e registra quando o problema foi resolvido;
      - episódio do mesmo formulário que se sobrepõe a um anterior mantém o mesmo registro;
      - pendência que deixou de ser detectada vira "resolvido" (com a data);
      - episódios da Meta que saíram da janela de 90 dias continuam com a última situação conhecida.
    """
    vistos = set()
    for item in itens:
        if item.get("chave_grupo"):
            for hid, h in historico.items():
                ultimo = h.get("ultimo") if isinstance(h, dict) else None
                if (hid != item["id"] and ultimo and ultimo.get("chave_grupo") == item["chave_grupo"]
                        and hid not in vistos and _sobrepoe(ultimo.get("periodo"), item.get("periodo"))):
                    item["id"] = hid
                    break
        anterior = historico.get(item["id"]) or {}
        if anterior.get("resolvido_manual") and item["situacao"] == "pendente":
            item["situacao"] = "resolvido"
            item["severidade"] = "info"
            nota = f" Nota: {anterior['nota']}" if anterior.get("nota") else ""
            item["situacao_motivo"] = f"Marcado como resolvido manualmente em {_br(anterior.get('resolvido_em'))}.{nota}"
        if item["situacao"] == "resolvido":
            # Quando os dados mostram quando parou (ex.: formulário voltou a integrar), vale essa data
            resolvido_em = item.get("resolvido_em_dados") or (
                anterior.get("resolvido_em") if anterior.get("situacao") == "resolvido" else agora
            )
        else:
            resolvido_em = None
        registro = {
            "primeira_deteccao": anterior.get("primeira_deteccao") or agora,
            "ultima_deteccao": agora,
            "situacao": item["situacao"],
            "resolvido_em": resolvido_em,
            "resolvido_manual": anterior.get("resolvido_manual", False),
            "nota": anterior.get("nota"),
            "ultimo": item,
        }
        historico[item["id"]] = registro
        item.update(primeira_deteccao=registro["primeira_deteccao"], resolvido_em=resolvido_em, nota_resolucao=registro["nota"])
        vistos.add(item["id"])

    for hid, h in list(historico.items()):
        if hid.startswith("_") or hid in vistos or not isinstance(h, dict) or not h.get("ultimo"):
            continue
        ultimo = dict(h["ultimo"])
        if h["situacao"] == "pendente":
            if (ultimo.get("chave_grupo") or "").startswith("formulario_meta:"):
                ultimo["situacao_motivo"] = (
                    "O período saiu da janela de 90 dias que a Meta devolve: não há mais dados para comprovar a correção. "
                    "Confira a integração do formulário e marque como resolvido quando estiver ok."
                )
                ultimo["resolucao_manual"] = True
            else:
                h.update(situacao="resolvido", resolvido_em=agora)
                ultimo.update(situacao="resolvido", severidade="info",
                              situacao_motivo=f"Deixou de ser detectado na verificação de {_br(agora)}.")
        h["ultimo"] = ultimo
        itens.append({**ultimo, "id": hid, "situacao": h["situacao"], "primeira_deteccao": h.get("primeira_deteccao"),
                      "resolvido_em": h.get("resolvido_em"), "nota_resolucao": h.get("nota")})
    return itens


def _no_periodo(item: Dict[str, Any], inicio: date, fim: date) -> bool:
    p = item.get("periodo")
    if not p or not p.get("inicio"):
        return True
    return date.fromisoformat(p["inicio"]) <= fim and date.fromisoformat(p.get("fim") or p["inicio"]) >= inicio


CACHE_SEGUNDOS = int(os.getenv("DIAGNOSTICO_CACHE_SEGUNDOS", "600"))
_resultado: Dict[str, Any] = {"chave": None, "em": 0.0, "itens": None, "calculado_em": None}
_recalculando = threading.Event()


def _chave_resultado() -> str:
    """Muda quando qualquer base é atualizada (ou quando os detectores/histórico mudam, nos testes)."""
    versoes = "|".join(f"{k}:{(bases.carregar(k) or {}).get('atualizado_em')}" for k in bases.BASES)
    return f"{versoes}#{id(DETECTORES)}#{HISTORICO_PATH}"


def _recalcular() -> None:
    agora = _agora_iso()
    chave = _chave_resultado()
    with _trava:
        historico = _ler_historico()
        ctx = Contexto(historico)
        itens: List[Dict[str, Any]] = []
        for detector in DETECTORES:
            try:
                itens.extend(detector(ctx))
            except Exception as e:  # um detector com erro não pode esconder os demais
                itens.append(diagnostico(
                    f"detector_com_erro:{detector.__name__}", "sistema", "atencao", "pendente",
                    "Uma verificação automática não pôde ser feita",
                    f"A verificação '{detector.__name__.replace('_diag_', '')}' falhou nesta rodada.",
                    str(e),
                    ["Atualize as bases e recarregue esta tela.", "Se continuar, verifique o log da engine."],
                    situacao_motivo="Muda para resolvido quando a verificação voltar a rodar sem erro.",
                ))
        itens = consolidar(itens, historico, agora)
        _gravar_historico(historico)
        _resultado.update(chave=chave, em=time.time(), itens=itens, calculado_em=agora)


def _recalcular_em_segundo_plano() -> None:
    if _recalculando.is_set():
        return
    _recalculando.set()

    def rodar():
        try:
            _recalcular()
        finally:
            _recalculando.clear()

    threading.Thread(target=rodar, daemon=True, name="diagnosticos").start()


def calcular(inicio: date, fim: date, esperar: bool = False) -> Dict[str, Any]:
    """
    Os diagnósticos cruzam todas as bases (alguns segundos). A tela recebe na hora o último
    resultado; quando ele tem mais de 10 minutos ou alguma base mudou, o recálculo roda em
    segundo plano. Só espera quando ainda não existe nenhum resultado.
    """
    vencido = (
        _resultado["itens"] is None
        or _resultado["chave"] != _chave_resultado()
        or time.time() - _resultado["em"] > CACHE_SEGUNDOS
    )
    if _resultado["itens"] is None or (vencido and esperar):
        _recalcular()
    elif vencido:
        _recalcular_em_segundo_plano()

    itens = _resultado["itens"] or []
    visiveis = [i for i in itens if _no_periodo(i, inicio, fim)]
    visiveis.sort(key=lambda i: (
        i["situacao"] != "pendente",
        SEVERIDADES.get(i["severidade"], 9),
        "" if i["situacao"] == "pendente" else "~",
        -(date.fromisoformat((i.get("periodo") or {}).get("fim") or "2000-01-01").toordinal()),
    ))
    pend = [i for i in visiveis if i["situacao"] == "pendente"]
    return {
        "calculado_em": _resultado["calculado_em"],
        "atualizando": _recalculando.is_set(),
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "resumo": {
            "pendentes_criticos": sum(1 for i in pend if i["severidade"] == "critico"),
            "pendentes_atencao": sum(1 for i in pend if i["severidade"] == "atencao"),
            "pendentes_info": sum(1 for i in pend if i["severidade"] == "info"),
            "resolvidos": sum(1 for i in visiveis if i["situacao"] == "resolvido"),
            "total": len(visiveis),
        },
        "itens": visiveis,
        "correcoes": CORRECOES,
    }


def resolver_manual(diagnostico_id: str, nota: Optional[str] = None) -> Dict[str, Any]:
    with _trava:
        historico = _ler_historico()
        registro = historico.get(diagnostico_id)
        if not registro or diagnostico_id.startswith("_"):
            raise KeyError(diagnostico_id)
        if not (registro.get("ultimo") or {}).get("resolucao_manual"):
            raise ValueError("Este diagnóstico é resolvido automaticamente quando os dados mostrarem que o problema parou.")
        registro.update(situacao="resolvido", resolvido_em=_agora_iso(), resolvido_manual=True, nota=(nota or "").strip() or None)
        _gravar_historico(historico)
    _resultado.update(itens=None)  # a próxima leitura já mostra a resolução
    return registro
