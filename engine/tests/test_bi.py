"""
Testes do BI, das bases salvas e dos extratores de investimento.
"""

from datetime import date

import pytest

from engine import bases, bi
from engine.extractors.ads_insights import google_insight_row, meta_insight_row
from engine.integrations import build_status


def lead(idlead, data_cad, midia=None, utm=None, tags=(), situacao="Cancelado", data_venda=None,
         valor=None, empreendimento="Avaré - Central Parque II - 13900", tarefas=(), ultima_conversao=None):
    return {
        "idlead": idlead,
        "data_cad": data_cad,
        "ultima_data_conversao": ultima_conversao,
        "midia_principal": midia,
        "campos_adicionais": [{"slug": f"cf_utm_{k}", "valor": v} for k, v in (utm or {}).items()] or None,
        "tags": [{"nome": t} for t in tags],
        "tarefa": [{"nome": t} for t in tarefas] or None,
        "situacao": {"nome": situacao},
        "data_venda": data_venda,
        "valor_venda": valor,
        "empreendimento": [{"id": 1, "nome": empreendimento}] if empreendimento else [],
        "email": "x@x.com",
        "link_interesses": f"https://cv/lead/{idlead}",
    }


@pytest.fixture
def base_fake(monkeypatch):
    conteudo = {}

    def carregar(chave):
        return conteudo.get(chave)

    monkeypatch.setattr(bi.bases, "carregar", carregar)
    monkeypatch.setattr(bi.bases, "registros", lambda chave: (conteudo.get(chave) or {}).get("registros") or [])
    monkeypatch.setattr(bi.bases, "resumo", lambda chave: {"base": chave})
    bi.limpar_cache()

    def definir(chave, registros, **extra):
        conteudo[chave] = {"registros": registros, "dados_de": extra.get("dados_de", "v1"), "total": len(registros),
                           "atualizado_em": extra.get("atualizado_em", "v1"), "periodo": {"inicio": "2025-01-01T00:00:00"}}
        bi.limpar_cache()

    return definir


# ---------------------------------------------------------------------------
# Etapas do funil
# ---------------------------------------------------------------------------


def test_lead_cancelado_que_foi_sql_conta_como_sql():
    assert bi.etapa_alcancada(lead(1, "2026-08-01", tags=["Lead Oportunidade (SQL)"], situacao="Cancelado")) == 2


def test_visita_agendada_pela_tarefa():
    assert bi.etapa_alcancada(lead(1, "2026-08-01", tarefas=["Visita agendada pela assistente virtual"])) == 3


def test_venda_e_a_ultima_etapa():
    assert bi.etapa_alcancada(lead(1, "2026-08-01", situacao="Vendido", data_venda="2026-08-20")) == 5


def test_tentativa_de_contato_e_sal():
    assert bi.etapa_alcancada(lead(1, "2026-08-01", tags=["Tentativa de Contato 2 (SAL 2)"])) == 1
    assert bi.etapa_alcancada(lead(1, "2026-08-01")) == 0


# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------


def test_kpis_separam_online_pago_organico_e_nao_rastreado(base_fake):
    base_fake("cv_leads", [
        lead(1, "2026-08-05", midia="Facebook Ads"),
        lead(2, "2026-08-06", midia="WhatsApp", utm={"source": "google", "medium": "cpc"}),
        lead(3, "2026-08-07", midia="WhatsApp", tags=["mia-organico"]),
        lead(4, "2026-08-08", midia="WhatsApp"),
        lead(5, "2026-08-09", midia="Painel Corretor"),
    ])
    r = bi.calcular_bi(date(2026, 8, 1), date(2026, 8, 31))
    k = r["kpis"]

    assert k["leads"] == 5
    assert k["pago"] == 2
    # WhatsApp conta como online mesmo sem campanha identificada (regra do BI gerencial)
    assert k["organico"] == 2
    assert k["nao_rastreado"] == 0
    assert k["offline"] == 1
    assert k["online"] == 4
    assert k["pct_online"] == 80.0


def test_vendas_contam_pela_data_da_venda_e_nao_do_cadastro(base_fake):
    base_fake("cv_leads", [
        # lead de junho vendido em agosto: é venda de agosto
        lead(1, "2026-06-10", midia="Facebook Ads", situacao="Vendido", data_venda="2026-08-15", valor="100000"),
        # lead de agosto vendido em setembro: não é venda de agosto
        lead(2, "2026-08-10", midia="Facebook Ads", situacao="Vendido", data_venda="2026-09-02", valor="50000"),
    ])
    r = bi.calcular_bi(date(2026, 8, 1), date(2026, 8, 31))

    assert r["kpis"]["vendas"] == 1
    assert r["kpis"]["vgv"] == 100000.0
    assert r["kpis"]["vendas_online"] == 1
    assert r["kpis"]["leads"] == 1  # só o lead cadastrado em agosto


def test_filtro_por_empreendimento_e_tabela_por_produto(base_fake):
    base_fake("cv_leads", [
        lead(1, "2026-08-05", midia="Facebook Ads", empreendimento="Avaré - Central Parque II - 13900"),
        lead(2, "2026-08-05", midia="Google", empreendimento="Itatinga - Novo Horizonte - 16103"),
        lead(3, "2026-08-05", midia="Painel PDV", empreendimento="Itatinga - Novo Horizonte - 16103"),
    ])
    r = bi.calcular_bi(date(2026, 8, 1), date(2026, 8, 31), empreendimentos=["Itatinga - Novo Horizonte - 16103"])

    assert r["kpis"]["leads"] == 2
    assert [e["empreendimento"] for e in r["por_empreendimento"]] == ["Itatinga - Novo Horizonte - 16103"]
    assert r["por_empreendimento"][0]["praca"] == "Itatinga"
    assert r["por_empreendimento"][0]["pct_online"] == 50.0


def test_comparacao_com_periodo_anterior(base_fake):
    base_fake("cv_leads", [
        lead(1, "2026-07-10", midia="Facebook Ads"),
        lead(2, "2026-08-10", midia="Facebook Ads"),
        lead(3, "2026-08-11", midia="Facebook Ads"),
    ])
    r = bi.calcular_bi(date(2026, 8, 1), date(2026, 8, 31))

    assert r["periodo"]["anterior_inicio"] == "2026-07-01"
    assert r["kpis"]["anterior"]["leads"] == 1
    assert r["kpis"]["variacao"]["leads"] == 100.0


def test_funil_e_monotono(base_fake):
    base_fake("cv_leads", [
        lead(1, "2026-08-05", midia="Facebook Ads"),
        lead(2, "2026-08-05", midia="Facebook Ads", tags=["Lead Oportunidade (SQL)"]),
        lead(3, "2026-08-05", midia="Facebook Ads", situacao="Vendido", data_venda="2026-08-20", valor="1"),
    ])
    funil = bi.calcular_bi(date(2026, 8, 1), date(2026, 8, 31))["funil"]["online"]
    qtds = [e["leads"] for e in funil]

    assert qtds == sorted(qtds, reverse=True)
    assert qtds[0] == 3 and qtds[2] == 2 and qtds[-1] == 1


def test_investimento_atribuido_pela_conta_de_anuncio(base_fake):
    base_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900", "Avaré - Reserva Central Parque II - 14000"])
    base_fake("cv_leads", [lead(i, "2026-08-05", midia="Facebook Ads") for i in range(4)])
    base_fake("meta_insights", [{
        "plataforma": "meta", "conta_nome": "ML - Central Parque Avaré 2", "campanha_nome": "x",
        "data": "2026-08-05", "investimento": 400.0, "leads_plataforma": 10,
    }])
    r = bi.calcular_bi(date(2026, 8, 1), date(2026, 8, 31))
    emp = r["por_empreendimento"][0]

    assert emp["investimento_meta"] == 400.0
    assert emp["leads_segundo_meta"] == 10
    assert emp["cpl_meta_crm"] == 100.0  # R$ 400 / 4 leads que chegaram no CRM


def test_detalhe_nao_expoe_dados_pessoais(base_fake):
    base_fake("cv_leads", [lead(1, "2026-08-05", midia="Facebook Ads")])
    item = bi.leads_detalhe(date(2026, 8, 1), date(2026, 8, 31))["itens"][0]

    assert "email" not in item and "nome" not in item and "telefone" not in item
    assert item["link"] == "https://cv/lead/1"
    assert item["evidencia"]


# ---------------------------------------------------------------------------
# Bases salvas
# ---------------------------------------------------------------------------


def test_atualizacao_que_falha_preserva_os_dados_anteriores(monkeypatch, tmp_path):
    monkeypatch.setattr(bases, "BASES_DIR", str(tmp_path))
    respostas = iter([
        ([{"idlead": 1}], build_status("cv_crm", "real", 1, "ok")),
        ([], build_status("cv_crm", "erro", 0, "token expirado")),
    ])
    monkeypatch.setattr(
        bases, "BASES",
        {"cv_leads": bases.BaseDef("cv_leads", "CV", "teste", lambda i, f: next(respostas))},
    )

    bases.atualizar("cv_leads")
    resumo = bases.atualizar("cv_leads")

    assert bases.registros("cv_leads") == [{"idlead": 1}]
    assert resumo["status"]["mode"] == "erro"
    assert "mantidos os dados" in resumo["status"]["message"]


# ---------------------------------------------------------------------------
# Extratores de investimento
# ---------------------------------------------------------------------------


def test_meta_insight_soma_tipos_de_lead():
    row = meta_insight_row(
        {"id": "act_1", "name": "ML - Jardim dos Ipês III"},
        {
            "campaign_id": "9", "campaign_name": "jardim-dos-ipes-3_meta-gdc_always-on", "date_start": "2026-08-05",
            "spend": "123.45", "impressions": "1000", "clicks": "40",
            "actions": [
                {"action_type": "onsite_conversion.lead_grouped", "value": "7"},
                {"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "3"},
            ],
        },
    )
    assert row["leads_formulario"] == 7
    assert row["conversas_whatsapp"] == 3
    assert row["leads_plataforma"] == 7  # sem a ação "lead" consolidada, soma formulário + site
    assert row["investimento"] == 123.45


def test_google_insight_converte_micros():
    row = google_insight_row({
        "customer": {"id": "123", "descriptiveName": "ML - Novo Horizonte (Itatinga)"},
        "campaign": {"id": "5", "name": "novo-horizonte_google-search"},
        "segments": {"date": "2026-08-05"},
        "metrics": {"costMicros": "2500000", "impressions": "900", "clicks": "30", "conversions": 4.0},
    })
    assert row["investimento"] == 2.5
    assert row["leads_plataforma"] == 4
    assert row["conta_nome"] == "ML - Novo Horizonte (Itatinga)"


def test_lead_com_dois_interesses_conta_nos_dois_e_a_venda_so_no_principal(base_fake):
    """Regra do BI da gestão: o lead conta em cada empreendimento de interesse; a venda, uma vez só."""
    cp2, reserva = "Avaré - Central Parque II - 13900", "Avaré - Reserva Central Parque II - 14000"
    multi = lead(1, "2026-09-05", midia="Facebook Ads", situacao="Vendido", data_venda="2026-09-10", valor="90000",
                 empreendimento=reserva)
    multi["empreendimento"].append({"id": 2, "nome": cp2})
    base_fake("cv_leads", [multi, lead(2, "2026-09-06", midia="WhatsApp", empreendimento=cp2)])

    r = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30), empreendimentos=[cp2])
    assert r["kpis"]["leads"] == 2  # o lead dos dois interesses e o lead só do Central Parque II
    # a venda pertence ao empreendimento principal (Reserva), então não entra no filtro do CP2
    assert r["kpis"]["vendas"] == 0

    geral = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30))
    por_emp = {e["empreendimento"]: e for e in geral["por_empreendimento"]}
    # 2 pessoas, 3 interesses: a soma dos empreendimentos fecha com o total, como no BI
    assert geral["kpis"]["leads"] == 3
    assert geral["kpis"]["pessoas_unicas"] == 2
    assert geral["kpis"]["interesses_adicionais"] == 1
    assert por_emp[cp2]["leads"] == 2 and por_emp[reserva]["leads"] == 1
    assert por_emp[reserva]["vendas"] == 1 and por_emp[cp2]["vendas"] == 0
    assert any("contam em cada produto" in a for a in geral["avisos"])
    assert cp2 in bi.opcoes()["empreendimentos"]


def test_lead_conta_no_mes_do_cadastro_mesmo_tendo_reconvertido_depois(base_fake):
    """O KPI principal usa cadastro; a última conversão é uma medida de conferência separada."""
    reconvertido = lead(1, "2026-02-10", midia="Facebook Ads")
    reconvertido["ultima_data_conversao"] = "2026-09-03 10:00:00"
    base_fake("cv_leads", [reconvertido, lead(2, "2026-09-04", midia="Google")])

    setembro = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30))["kpis"]
    assert setembro["leads"] == 1
    assert setembro["pessoas_unicas"] == 1
    assert setembro["interesses_adicionais"] == 0
    assert setembro["ultima_conversao_pessoas"] == 2
    assert bi.calcular_bi(date(2026, 2, 1), date(2026, 2, 28))["kpis"]["leads"] == 1
    preparado = bi.leads_preparados()[0]
    assert preparado["data"] == date(2026, 2, 10) and preparado["data_conversao"] == date(2026, 9, 3)


def test_escopo_online_tira_corretor_de_leads_e_vendas(base_fake):
    base_fake("cv_leads", [
        lead(1, "2026-09-02", midia="Facebook Ads", situacao="Vendido", data_venda="2026-09-08", valor="137182.50"),
        lead(2, "2026-09-03", midia="WhatsApp"),
        lead(3, "2026-09-04", midia="Painel Imobiliária", situacao="Vendido", data_venda="2026-09-10", valor="146596.80"),
    ])
    tudo = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 14))
    online = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 14), escopo="online")

    assert (tudo["kpis"]["leads"], tudo["kpis"]["vendas"]) == (3, 2)
    assert (online["kpis"]["leads"], online["kpis"]["vendas"], online["kpis"]["vgv"]) == (2, 1, 137182.5)
    assert online["por_empreendimento"][0]["vendas"] == 1
    assert online["funil"]["todos"][0]["leads"] == 2
    assert online["kpis"]["unidades_vendidas"] == 1
    assert len(bi.leads_detalhe(date(2026, 9, 1), date(2026, 9, 14), escopo="online")["itens"]) == 2


def test_mirante_dos_ramos_conta_como_reserva_dos_ramos(base_fake):
    reserva = "Tatuí - Reserva dos Ramos Residencial - 14704"
    base_fake("cv_empreendimentos", ["Tatuí - Mirante dos Ramos - Comercial 14703", reserva])
    base_fake("cv_leads", [
        lead(1, "2026-09-02", midia="Facebook Ads", empreendimento="Tatuí - Mirante dos Ramos - Comercial 14703"),
        lead(2, "2026-09-03", midia="Facebook Ads", empreendimento=reserva),
    ])
    base_fake("meta_insights", [meta_insight_row({"id": "act_1", "name": "Mirante dos Ramos"},
                                                 {"campaign_name": "[Leads] - [Mirante dos Ramos]", "date_start": "2026-09-02", "spend": "100"})])

    r = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30), empreendimentos=[reserva])
    assert r["kpis"]["leads"] == 2
    assert [e["empreendimento"] for e in r["por_empreendimento"]] == [reserva]
    assert r["por_empreendimento"][0]["investimento_meta"] == 100.0
    assert "Tatuí - Mirante dos Ramos - Comercial 14703" not in bi.opcoes()["empreendimentos"]


# ---------------------------------------------------------------------------
# Vendas pelas reservas do CV
# ---------------------------------------------------------------------------


def reserva_vendida(idreserva, data_venda, empreendimento, valor, leads=(), email=None, unidade="A-1",
                    tipo_venda=None, corretor=None):
    return {"idreserva": str(idreserva), "vendida": True, "situacao": "Vendida", "data_venda": f"{data_venda} 10:00:00",
            "empreendimento": empreendimento, "bloco": "Q1", "unidade": unidade, "valor_contrato": valor,
            "leads_associados": [str(l) for l in leads], "titular_email": email, "titular_telefone": None,
            "tipo_venda": tipo_venda, "corretor": corretor}


def test_equivalencias_dos_power_bis_separam_movimentacao_tipo_e_corretor(base_fake):
    cp2 = "Avaré - Central Parque II - 13900"
    movimentado = lead(1, "2026-08-10", midia="Facebook Ads", tags=["Lead Oportunidade (SQL)"],
                       ultima_conversao="2026-09-05 09:00:00")
    movimentado["empreendimento"].append({"id": 2, "nome": "Avaré - Reserva Central Parque II - 14000"})
    base_fake("cv_leads", [
        movimentado,
        lead(2, "2026-09-06", midia="Google"),
        lead(3, "2026-09-07", midia="Painel Corretor", ultima_conversao="2026-09-07 11:00:00"),
        lead(4, "2026-09-08", midia="Facebook Ads", ultima_conversao="2026-10-01 08:00:00"),
    ], dados_de="2026-09-29T11:16:00-03:00")
    base_fake("cv_reservas", [
        reserva_vendida(10, "2026-09-10", cp2, 100000, leads=[1], tipo_venda="Vendas SDR",
                        corretor="Especialista - Ana"),
        reserva_vendida(11, "2026-09-11", cp2, 90000, leads=[2], tipo_venda="Venda Imobiliária",
                        corretor="Especialista - Beto"),
        reserva_vendida(12, "2026-09-12", cp2, 80000),
    ], dados_de="2026-09-29T12:03:00-03:00")

    r = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30), escopo="tudo")
    eq = r["equivalencias_bi"]

    # O lead 1 tem dois interesses, mas é uma só pessoa na régua por última conversão.
    assert eq["mql_ultima_conversao"] == 2
    assert eq["sql_historico"] == 1
    assert r["funil_movimentacao"][0]["leads"] == 2
    assert r["kpis"]["leads"] == 3  # cadastros no mês: 2 e 4 online, 3 offline
    assert eq["unidades_vendidas"] == 2
    assert eq["vgv_unidades"] == 190000
    assert eq["vendas_tipo_sdr"] == 1
    assert eq["vendas_tipo_sdr_online"] == 1
    assert eq["vgv_tipo_sdr_online"] == 100000
    assert eq["vendas_especialistas"] == 2
    assert eq["vendas_sem_tipo"] == 0
    assert eq["vgv_sem_tipo"] == 0
    assert eq["cv_leads_atualizado_em"] == "2026-09-29T11:16:00-03:00"
    assert eq["cv_reservas_atualizado_em"] == "2026-09-29T12:03:00-03:00"
    assert eq["sql_certificado"] is False
    assert eq["novo_lead_mql_certificado"] is False


def test_vendas_das_reservas_contam_no_interesse_do_lead_e_na_unidade_comprada(base_fake):
    from engine import identidade  # noqa: F401  (registra o cache do índice)

    cp2, nh = "Avaré - Central Parque II - 13900", "Cerqueira César - Novo Horizonte - 13200"
    comprador_meta = lead(1, "2026-09-01", midia="Facebook Ads", empreendimento=cp2)
    comprador_meta["email"] = "meta@x.com"
    base_fake("cv_leads", [comprador_meta, lead(2, "2026-08-20", midia="Painel Corretor", empreendimento=cp2)])
    base_fake("cv_reservas", [
        reserva_vendida(10, "2026-09-08", nh, 54724.96, leads=[1]),                 # lead do CP2 comprou no Novo Horizonte
        reserva_vendida(11, "2026-09-08", cp2, 93046.5, leads=[2]),                 # corretor comprou no CP2
        reserva_vendida(12, "2026-09-09", cp2, 89900.0),                            # sem lead no CV
        reserva_vendida(13, "2026-09-10", cp2, 90000.0, email="META@x.com"),        # ligada pelo e-mail do titular
        {**reserva_vendida(14, "2026-09-10", cp2, 1.0), "vendida": False},           # não vendida: fora
    ])

    r = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30), empreendimentos=[cp2], escopo="online")
    k = r["kpis"]
    assert k["fonte_vendas"] == "reservas"
    # regra do BI: as 2 vendas do lead online do CP2, mesmo a do Novo Horizonte
    assert (k["vendas"], k["vgv"], k["vendas_outro_empreendimento"]) == (2, 144724.96, 1)
    # o que foi vendido no CP2 com origem online comprovada
    assert (k["unidades_vendidas"], k["unidades_vendidas_online"], k["unidades_sem_lead"]) == (1, 1, 0)
    assert k["vgv_unidades"] == 90000
    assert any("outro empreendimento" in a for a in r["avisos"])

    geral = {e["empreendimento"]: e for e in bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30))["por_empreendimento"]}
    assert geral[nh]["unidades_vendidas"] == 1 and geral[nh]["vendas"] == 0
    assert geral[cp2]["vendas"] == 4 and geral[cp2]["unidades_vendidas"] == 3

    comprado = bi.leads_detalhe(date(2026, 9, 1), date(2026, 9, 30), empreendimento=cp2, vendidos=True,
                                escopo="online", criterio="comprado")
    assert comprado["total"] == 1
    ligacoes = {i["idreserva"]: i["ligacao"] for i in comprado["itens"]}
    assert ligacoes == {"13": "email"}
    assert all("titular_email" not in i and "titular_telefone" not in i for i in comprado["itens"])

    outro = bi.leads_detalhe(date(2026, 9, 1), date(2026, 9, 30), empreendimento=cp2, vendidos=True,
                             escopo="online", so_outro_empreendimento=True)
    assert [(i["idreserva"], i["empreendimento_comprado"], i["unidade"]) for i in outro["itens"]] == [("10", nh, "Q1 · A-1")]


def test_sem_base_de_reservas_as_vendas_vem_do_lead(base_fake):
    base_fake("cv_leads", [lead(1, "2026-09-01", midia="Facebook Ads", situacao="Vendido", data_venda="2026-09-08", valor="1000")])
    k = bi.calcular_bi(date(2026, 9, 1), date(2026, 9, 30))["kpis"]
    assert (k["fonte_vendas"], k["vendas"], k["unidades_vendidas"]) == ("leads", 1, 1)
