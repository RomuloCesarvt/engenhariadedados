"""
Testes da audiência do site (Google Analytics): atribuição pela página de entrada, comparação com
o período anterior e a leitura que o módulo escreve.
"""

from datetime import date

import pytest

from engine import audiencia, bases
from engine.extractors.ga4 import NAO_INFORMADO, linha_cidade, linha_trafego

CATALOGO = ["Itatinga - Novo Horizonte - 16103", "Avaré - Central Parque II - 13900",
            "Botucatu - Reserva Central Parque - 13600", "Itu - Altavista - 15300"]

INICIO, FIM = date(2026, 8, 15), date(2026, 8, 21)      # 7 dias
ANTES = date(2026, 8, 8)                                 # 7 dias antes


def trafego(data="2026-08-16", pagina="/", canal="Organic Search", origem="google / organic",
            dispositivo="Celular", sessoes=10, conversoes=0, engajadas=None, novos=None, tempo=None):
    return {"plataforma": "ga4", "propriedade": "1", "data": data, "pagina_entrada": pagina, "canal": canal,
            "origem_midia": origem, "dispositivo": dispositivo, "sessoes": sessoes, "usuarios": sessoes,
            "novos_usuarios": sessoes if novos is None else novos,
            "sessoes_engajadas": sessoes // 2 if engajadas is None else engajadas,
            "conversoes": conversoes, "tempo_engajamento": sessoes * 30 if tempo is None else tempo}


def cidade(data="2026-08-16", pagina="/", nome="Avare", estado="State of Sao Paulo", sessoes=10, conversoes=0):
    return {"plataforma": "ga4", "propriedade": "1", "data": data, "pagina_entrada": pagina, "cidade": nome,
            "estado": estado, "sessoes": sessoes, "usuarios": sessoes, "sessoes_engajadas": sessoes // 2,
            "conversoes": conversoes}


@pytest.fixture
def base(monkeypatch):
    dados = {"cv_empreendimentos": CATALOGO, "ga4_trafego": [], "ga4_cidades": []}
    monkeypatch.setattr(bases, "registros", lambda chave: dados.get(chave) or [])
    monkeypatch.setattr(bases, "resumo", lambda chave: {"base": chave, "status": {"mode": "real"}})

    def definir(registros, chave="ga4_trafego"):
        dados[chave] = registros

    return definir


def compilar(**kwargs):
    return audiencia.compilar(INICIO, FIM, **kwargs)


# --- atribuição da página de entrada ---------------------------------------


@pytest.mark.parametrize("pagina,esperado", [
    ("/", audiencia.HOME),
    ("", audiencia.HOME),
    ("/blog/conheca-avare", audiencia.BLOG),
    ("/empreendimento/altavista", audiencia.PRODUTO),
    ("/fale-conosco", audiencia.OUTRAS),
])
def test_tipo_da_pagina_de_entrada(pagina, esperado):
    assert audiencia.tipo_da_pagina(pagina) == esperado


def test_pagina_do_empreendimento_vira_produto_e_praca(base):
    base([trafego(pagina="/empreendimento/novo-horizonte-itatinga", sessoes=40)])
    r = compilar()
    assert [(p["empreendimento"], p["praca"], p["sessoes"]) for p in r["produtos"]] == [
        ("Itatinga - Novo Horizonte - 16103", "Itatinga", 40)]


def test_pagina_que_cita_outra_cidade_nao_vira_produto(base):
    """"/empreendimento/central-parque-botucatu" não é o Central Parque de Avaré: fica na praça."""
    base([trafego(pagina="/empreendimento/central-parque-botucatu", sessoes=30)])
    r = compilar()
    assert r["produtos"] == []
    assert r["entradas"][0]["tipo"] == audiencia.PRODUTO and r["entradas"][0]["sessoes"] == 30


def test_home_e_blog_ficam_fora_dos_produtos(base):
    base([trafego(pagina="/", sessoes=60), trafego(pagina="/blog/conheca-avare", sessoes=20),
          trafego(pagina="/empreendimento/altavista", sessoes=20)])
    r = compilar()
    assert [p["sessoes"] for p in r["produtos"]] == [20]
    assert {e["tipo"]: e["sessoes"] for e in r["entradas"]} == {
        audiencia.PRODUTO: 20, audiencia.HOME: 60, audiencia.BLOG: 20}


def test_filtro_de_empreendimento_so_conta_as_paginas_daquele_produto(base):
    base([trafego(pagina="/empreendimento/altavista", sessoes=20),
          trafego(pagina="/empreendimento/novo-horizonte-itatinga", sessoes=50)])
    r = compilar(empreendimentos=["Itu - Altavista - 15300"])
    assert r["totais"]["sessoes"] == 20


# --- comparação com o período anterior --------------------------------------


def test_cada_quadro_traz_o_periodo_anterior_do_lado(base):
    base([trafego(data="2026-08-16", canal="Paid Search", sessoes=150),
          trafego(data=ANTES.isoformat(), canal="Paid Search", sessoes=100)])
    r = compilar()
    assert r["totais"]["sessoes"] == 150 and r["totais"]["anterior"]["sessoes"] == 100
    assert r["totais"]["variacao"]["sessoes"] == 50.0
    canal = r["canais"][0]
    assert (canal["canal"], canal["sessoes"], canal["sessoes_antes"], canal["variacao"]) == ("Paid Search", 150, 100, 50.0)


def test_fora_do_periodo_e_do_anterior_nao_entra(base):
    base([trafego(data="2026-07-01", sessoes=999), trafego(data="2026-08-16", sessoes=10)])
    r = compilar()
    assert r["totais"]["sessoes"] == 10 and r["totais"]["anterior"]["sessoes"] == 0


def test_queda_de_sessoes_vira_alerta_com_o_canal_que_explica(base):
    base([trafego(data="2026-08-16", canal="Paid Search", sessoes=300),
          trafego(data=ANTES.isoformat(), canal="Paid Search", sessoes=800)])
    r = compilar()
    chaves = {a["chave"]: a for a in r["analises"]}
    assert chaves["sessoes_variacao"]["tipo"] == "alerta"
    assert "500 sessões a menos" in chaves["canal_queda"]["texto"]


def test_variacao_sem_amostra_minima_nao_vira_leitura(base):
    base([trafego(data="2026-08-16", sessoes=10), trafego(data=ANTES.isoformat(), sessoes=50)])
    assert not [a for a in compilar()["analises"] if a["chave"] == "sessoes_variacao"]


# --- aparelhos, cidades e leitura -------------------------------------------


def test_celular_que_converte_menos_que_o_computador_vira_alerta(base):
    base([trafego(dispositivo="Celular", sessoes=700, conversoes=7),
          trafego(dispositivo="Computador", sessoes=300, conversoes=15)])
    r = compilar()
    celular = next(d for d in r["dispositivos"] if d["dispositivo"] == "Celular")
    assert celular["pct"] == 70.0 and celular["taxa_conversao"] == 1.0
    assert "aparelho_conversao" in {a["chave"] for a in r["analises"]}


def test_celular_que_converte_bem_nao_vira_alerta(base):
    base([trafego(dispositivo="Celular", sessoes=700, conversoes=21),
          trafego(dispositivo="Computador", sessoes=300, conversoes=6)])
    assert "aparelho_conversao" not in {a["chave"] for a in compilar()["analises"]}


def test_cidade_das_nossas_pracas_e_reconhecida_sem_acento(base):
    base([cidade(nome="Avare", sessoes=60), cidade(nome="Campinas", sessoes=40)], "ga4_cidades")
    r = compilar()["cidades"]
    assert r["pct_das_nossas_pracas"] == 60.0 and r["distintas"] == 2
    assert [(c["cidade"], c["praca"]) for c in r["cidades"]] == [("Avare", "Avaré"), ("Campinas", None)]


def test_muita_entrada_fora_de_pagina_de_produto_e_dito_na_leitura(base):
    base([trafego(pagina="/", sessoes=80), trafego(pagina="/empreendimento/altavista", sessoes=20)])
    achado = next(a for a in compilar()["analises"] if a["chave"] == "entrada_sem_produto")
    assert "80,0%" in achado["titulo"]


# --- as linhas que vêm do GA4 ------------------------------------------------


def test_linha_de_trafego_traduz_data_e_aparelho():
    linha = linha_trafego("1", ["20260905", "/empreendimento/altavista", "Paid Search", "google / cpc", "mobile"],
                          ["10", "9", "8", "5", "1", "300"])
    assert (linha["data"], linha["dispositivo"], linha["pagina_entrada"]) == ("2026-09-05", "Celular", "/empreendimento/altavista")
    assert (linha["sessoes"], linha["novos_usuarios"], linha["tempo_engajamento"]) == (10, 8, 300)


def test_o_que_o_ga4_nao_sabe_vira_nao_informado():
    linha = linha_cidade("1", ["20260905", "(not set)", "(not set)", ""], ["4", "4", "2", "0"])
    assert (linha["cidade"], linha["estado"], linha["pagina_entrada"]) == (NAO_INFORMADO, NAO_INFORMADO, None)


def test_periodo_anterior_tem_o_mesmo_tamanho():
    assert audiencia._periodo_anterior(date(2026, 8, 15), date(2026, 8, 21)) == (date(2026, 8, 8), date(2026, 8, 14))
    assert audiencia._periodo_anterior(date(2026, 1, 1), date(2026, 1, 31)) == (date(2025, 12, 1), date(2025, 12, 31))


def test_conversao_caindo_com_acesso_subindo_vira_alerta(base):
    base([trafego(data="2026-08-16", sessoes=1200, conversoes=30),
          trafego(data=ANTES.isoformat(), sessoes=800, conversoes=60)])
    achado = next(a for a in compilar()["analises"] if a["chave"] == "conversoes_variacao")
    assert achado["tipo"] == "alerta" and "entrou mais gente e converteu menos" in achado["texto"]
