"""
Testes das palavras: as melhores palavras-chave do Google Ads por empreendimento e as palavras mais
buscadas por praça (Google Analytics).
"""

from datetime import date

import pytest

from engine import bases, palavras
from engine.normalizer import EMPREENDIMENTO_DESCONHECIDO
from engine.extractors.ads_insights import GooglePalavrasExtractor, google_palavra_row
from engine.extractors.ga4 import GA4PalavrasExtractor, e_palavra, linha_palavra

CATALOGO = ["Itatinga - Novo Horizonte - 16103", "Avaré - Central Parque II - 13900",
            "Avaré - Reserva Central Parque II - 14000", "Itu - Altavista - 15300"]


def linha(palavra, mes="2026-08", pagina=None, campanha=None, sessoes=10, conversoes=0, tipo="Google Ads"):
    return {"plataforma": "ga4", "propriedade": "1", "palavra": palavra, "tipo": tipo, "campanha_nome": campanha,
            "pagina_entrada": pagina, "mes": mes, "sessoes": sessoes, "usuarios": sessoes, "conversoes": conversoes}


def chave(palavra, conta=None, campanha=None, data="2026-08-15", investimento=100.0, impressoes=1000,
          cliques=50, conversoes=0.0):
    """Uma linha da base de palavras-chave do Google Ads (vem por dia)."""
    return {"plataforma": "google", "conta_nome": conta, "campanha_nome": campanha, "grupo_nome": None,
            "palavra": palavra, "correspondencia": "Frase", "data": data, "mes": data[:7],
            "investimento": investimento, "impressoes": impressoes, "cliques": cliques, "conversoes": conversoes}


def termo(texto, conta=None, campanha=None, mes="2026-08", impressoes=500, cliques=40, conversoes=0.0,
          canal="Performance Max"):
    """Uma linha da base de termos de pesquisa (o que a pessoa digitou)."""
    return {"plataforma": "google", "conta_nome": conta, "campanha_nome": campanha, "canal": canal,
            "termo": texto, "mes": mes, "impressoes": impressoes, "cliques": cliques, "conversoes": conversoes}


@pytest.fixture
def base(monkeypatch):
    dados = {"cv_empreendimentos": CATALOGO, "ga4_palavras": [], "google_palavras": [], "google_termos": []}
    monkeypatch.setattr(bases, "registros", lambda chave: dados.get(chave) or [])
    monkeypatch.setattr(bases, "resumo", lambda chave: {"base": chave, "status": {"mode": "real"}})

    def definir(registros, chave="ga4_palavras"):
        dados[chave] = registros

    return definir


def test_palavra_vai_para_a_praca_do_empreendimento_da_pagina(base):
    base([linha("terreno itatinga", pagina="/itatinga-novo-horizonte?utm_source=google")])
    r = palavras.por_praca(date(2026, 8, 1), date(2026, 8, 31))
    assert [p["praca"] for p in r["pracas"]] == ["Itatinga"]
    assert r["pracas"][0]["palavras"][0]["empreendimentos"] == ["Itatinga - Novo Horizonte - 16103"]


def test_sem_pagina_a_praca_sai_da_campanha_e_depois_da_propria_palavra(base):
    base([linha("lotes", campanha="novo-horizonte_google-search"), linha("terrenos em avare", sessoes=5)])
    r = palavras.por_praca(date(2026, 8, 1), date(2026, 8, 31))
    assert {p["praca"] for p in r["pracas"]} == {"Itatinga", "Avaré"}


def test_palavra_sem_empreendimento_fica_em_praca_nao_identificada_e_no_fim(base):
    base([linha("comprar lote", sessoes=50), linha("terreno itatinga", sessoes=10)])
    r = palavras.por_praca(date(2026, 8, 1), date(2026, 8, 31))
    assert [p["praca"] for p in r["pracas"]] == ["Itatinga", palavras.PRACA_DESCONHECIDA]


def test_mesma_palavra_em_meses_diferentes_soma_e_ordena_por_sessoes(base):
    base([linha("terreno itatinga", mes="2026-08", sessoes=10, conversoes=1),
          linha("terreno itatinga", mes="2026-09", sessoes=30, conversoes=2),
          linha("lote itatinga", mes="2026-08", sessoes=25)])
    r = palavras.por_praca(date(2026, 8, 15), date(2026, 9, 10))
    itatinga = r["pracas"][0]
    assert [p["palavra"] for p in itatinga["palavras"]] == ["terreno itatinga", "lote itatinga"]
    assert (itatinga["palavras"][0]["sessoes"], itatinga["palavras"][0]["conversoes"]) == (40, 3)
    assert itatinga["sessoes"] == 65


def test_mes_fora_do_periodo_nao_entra(base):
    base([linha("terreno itatinga", mes="2026-06")])
    assert palavras.por_praca(date(2026, 8, 1), date(2026, 8, 31))["pracas"] == []


def test_filtro_de_praca_da_tela_vale_para_as_palavras(base):
    base([linha("terreno itatinga"), linha("terrenos em avare")])
    r = palavras.por_praca(date(2026, 8, 1), date(2026, 8, 31), pracas=["Avaré"])
    assert [p["praca"] for p in r["pracas"]] == ["Avaré"]


def test_limite_corta_a_lista_mas_o_total_da_praca_continua_inteiro(base):
    base([linha(f"terreno itatinga {i}", sessoes=i) for i in range(1, 8)])
    r = palavras.por_praca(date(2026, 8, 1), date(2026, 8, 31), limite=3)
    praca = r["pracas"][0]
    assert len(praca["palavras"]) == 3 and praca["palavras_distintas"] == 7
    assert praca["sessoes"] == sum(range(1, 8))


@pytest.mark.parametrize("dimensoes,palavra,tipo", [
    (["terreno itatinga", "(not set)", "camp", "/itatinga", "202608"], "terreno itatinga", "Google Ads"),
    (["(not set)", "lote-avare", "camp", "/avare", "202608"], "lote-avare", "UTM (utm_term)"),
])
def test_linha_do_ga4_usa_a_palavra_do_ads_e_cai_para_o_utm_term(dimensoes, palavra, tipo):
    r = linha_palavra("123", dimensoes, ["10", "8", "2"])
    assert (r["palavra"], r["tipo"], r["mes"], r["sessoes"], r["conversoes"]) == (palavra, tipo, "2026-08", 10, 2)


def test_sem_credenciais_o_extrator_avisa_o_que_falta(monkeypatch):
    for chave in ("GA4_PROPERTY_IDS", "GA4_PROPERTY_ID", "GA4_CREDENTIALS_PATH", "GA4_CLIENT_ID", "GA4_CLIENT_SECRET",
                  "GA4_REFRESH_TOKEN", "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN"):
        monkeypatch.delenv(chave, raising=False)
    ex = GA4PalavrasExtractor()
    assert ex.fetch(None, None) == []
    assert ex.status.mode == "nao_configurado" and "GA4_PROPERTY_IDS" in ex.status.message


# ---------------------------------------------------------------------------
# Melhores palavras-chave do Google Ads, por empreendimento
# ---------------------------------------------------------------------------


def test_palavra_chave_vai_para_o_empreendimento_da_conta(base):
    base([chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)")], "google_palavras")
    r = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))
    assert [(e["empreendimento"], e["praca"]) for e in r["empreendimentos"]] == [("Itatinga - Novo Horizonte - 16103", "Itatinga")]


def test_a_melhor_palavra_e_a_que_converte_mais_barato(base):
    base([
        chave("lote barato", conta="ML - Novo Horizonte (Itatinga)", investimento=300.0, conversoes=2.0),
        chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", investimento=200.0, conversoes=4.0),
        chave("so clique", conta="ML - Novo Horizonte (Itatinga)", investimento=500.0, cliques=90, conversoes=0.0),
    ], "google_palavras")
    e = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))["empreendimentos"][0]
    assert [p["palavra"] for p in e["palavras"]] == ["terreno itatinga", "lote barato", "so clique"]
    assert e["palavras"][0]["custo_por_conversao"] == 50.0
    assert (e["palavras_com_conversao"], e["conversoes"]) == (2, 6.0)


def test_palavra_que_so_gasta_aparece_na_lista_do_desperdicio(base):
    base([
        chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", conversoes=1.0),
        chave("casa pronta", conta="ML - Novo Horizonte (Itatinga)", investimento=800.0, conversoes=0.0),
    ], "google_palavras")
    e = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))["empreendimentos"][0]
    assert [p["palavra"] for p in e["sem_conversao"]] == ["casa pronta"]


def test_mesma_palavra_em_meses_diferentes_soma_custo_cliques_e_conversoes(base):
    base([
        chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", data="2026-08-10", investimento=100.0, cliques=40, conversoes=1.0),
        chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", data="2026-09-05", investimento=50.0, cliques=10, conversoes=1.0),
    ], "google_palavras")
    p = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 9, 30))["empreendimentos"][0]["palavras"][0]
    assert (p["investimento"], p["cliques"], p["conversoes"], p["custo_por_conversao"]) == (150.0, 50, 2.0, 75.0)
    assert p["ctr"] == 2.5 and p["cpc"] == 3.0


def test_empreendimentos_saem_do_que_mais_investe_e_o_nao_identificado_fica_por_ultimo(base):
    base([
        chave("lote", conta="Conta sem nome de produto", investimento=900.0),
        chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", investimento=100.0),
        chave("lote avare", conta="ML - Central Parque Avaré 2", investimento=400.0),
    ], "google_palavras")
    r = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))
    assert [e["praca"] for e in r["empreendimentos"]] == ["Avaré", "Itatinga", palavras.PRACA_DESCONHECIDA]


def test_filtro_de_empreendimento_da_tela_vale_para_as_palavras_chave(base):
    base([chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)"),
          chave("lote avare", conta="ML - Central Parque Avaré 2")], "google_palavras")
    r = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31), empreendimentos=["Itatinga - Novo Horizonte - 16103"])
    assert len(r["empreendimentos"]) == 1 and r["empreendimentos"][0]["praca"] == "Itatinga"


def test_linha_do_keyword_view_vira_registro_da_base():
    r = google_palavra_row({
        "customer": {"id": 9, "descriptiveName": "ML - Novo Horizonte (Itatinga)"},
        "campaign": {"id": 7, "name": "Search Itatinga"}, "adGroup": {"name": "Terrenos"},
        "adGroupCriterion": {"keyword": {"text": " terreno em itatinga ", "matchType": "PHRASE"}},
        "segments": {"date": "2026-08-14"},
        "metrics": {"costMicros": 1234560000, "impressions": "900", "clicks": "80", "conversions": 7.0},
    })
    assert (r["palavra"], r["correspondencia"]) == ("terreno em itatinga", "Frase")
    assert (r["data"], r["mes"]) == ("2026-08-14", "2026-08")
    assert (r["investimento"], r["impressoes"], r["cliques"], r["conversoes"]) == (1234.56, 900, 80, 7.0)


def test_sem_credenciais_o_extrator_de_palavras_chave_avisa(monkeypatch):
    for chave_env in ("GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET",
                      "GOOGLE_ADS_REFRESH_TOKEN", "GOOGLE_ADS_CUSTOMER_IDS", "GOOGLE_ADS_CUSTOMER_ID",
                      "GOOGLE_ADS_LOGIN_CUSTOMER_ID"):
        monkeypatch.delenv(chave_env, raising=False)
    ex = GooglePalavrasExtractor()
    assert ex.fetch(None, None) == []
    assert ex.status.mode == "nao_configurado" and "GOOGLE_ADS_CLIENT_ID" in ex.status.message


@pytest.mark.parametrize("texto,vale", [
    ("terreno itatinga", True),
    ("lote-avare", True),
    ("{keyword}", False),          # variável do Google que não foi substituída
    ("{{adset.name}}", False),
    ("52512422694933", False),     # ID de anúncio no utm_term
    ("null", False),
    ("keyword", False),
    ("k", False),
    ("(not set)", False),
])
def test_utm_term_sem_palavra_de_verdade_fica_de_fora(texto, vale):
    assert e_palavra(texto) is vale


# ---------------------------------------------------------------------------
# Termos de pesquisa (Performance Max, que não tem palavra-chave)
# ---------------------------------------------------------------------------


def test_termos_de_pesquisa_entram_mesmo_sem_palavra_chave(base):
    """A conta de Avaré roda campanha da cidade e anuncia os dois produtos: o número fica na praça."""
    base([termo("loteamento em avare sp", conta="Avaré 2 - Central (FMD)",
                campanha="avare_google-pmax_lancamento", cliques=275, conversoes=31.0),
          termo("condominio em avare", conta="Avaré 2 - Central (FMD)",
                campanha="avare_google-pmax_lancamento", cliques=43)], "google_termos")
    r = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))
    e = r["empreendimentos"][0]
    assert (e["praca"], e["empreendimento"]) == ("Avaré", EMPREENDIMENTO_DESCONHECIDO)
    assert [t["termo"] for t in e["termos"]] == ["loteamento em avare sp", "condominio em avare"]
    assert (e["termos_distintos"], e["termos_cliques"], e["palavras_distintas"]) == (2, 318, 0)
    assert e["termos_canais"] == ["Performance Max"]


def test_campanha_que_diz_o_produto_manda_mais_que_a_conta_da_cidade(base):
    """A campanha do Black Friday é do Reserva: essa vai para o produto, não só para a praça."""
    base([termo("reserva central parque avare", conta="Avaré 2 - Reserva (FMD)",
                campanha="reserva-2_google-pmax_black-friday", cliques=31)], "google_termos")
    e = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))["empreendimentos"][0]
    assert e["empreendimento"] == "Avaré - Reserva Central Parque II - 14000" and e["praca"] == "Avaré"


def test_palavra_chave_e_termo_do_mesmo_produto_ficam_no_mesmo_quadro(base):
    base([chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", conversoes=3.0)], "google_palavras")
    base([termo("terrenos em itatinga", conta="Novo Horizonte (Itatinga) (FMD)", cliques=60)], "google_termos")
    r = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))
    assert len(r["empreendimentos"]) == 1
    e = r["empreendimentos"][0]
    assert e["palavras"][0]["palavra"] == "terreno itatinga" and e["termos"][0]["termo"] == "terrenos em itatinga"


def test_termo_de_mes_fora_do_periodo_nao_entra(base):
    base([termo("loteamento em avare sp", conta="Avaré 2 - Central (FMD)", mes="2026-05")], "google_termos")
    assert palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))["empreendimentos"] == []


def test_palavra_chave_respeita_o_dia_escolhido_e_o_termo_fica_no_mes(base):
    """A palavra-chave vem por dia; o termo, só por mês — é o que o Google entrega de cada um."""
    base([chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", data="2026-08-03", investimento=30.0),
          chave("terreno itatinga", conta="ML - Novo Horizonte (Itatinga)", data="2026-08-20", investimento=70.0)],
         "google_palavras")
    base([termo("terrenos em itatinga", conta="Novo Horizonte (Itatinga) (FMD)", mes="2026-08", cliques=90)],
         "google_termos")

    so_inicio = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 10))["empreendimentos"][0]
    assert so_inicio["investimento"] == 30.0
    # o mesmo recorte curto ainda mostra o termo do mês inteiro, e a tela avisa isso
    assert so_inicio["termos_cliques"] == 90

    mes_todo = palavras.por_empreendimento(date(2026, 8, 1), date(2026, 8, 31))["empreendimentos"][0]
    assert mes_todo["investimento"] == 100.0
