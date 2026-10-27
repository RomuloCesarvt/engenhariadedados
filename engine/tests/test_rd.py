"""
Testes da conferência RD Station × CV.

A RD guarda listas importadas e disparos que nunca deveriam ir para o CV; só o contato
que converteu em formulário e não chegou conta como falha.
"""

from datetime import date

import pytest

from engine import bi, conferencias, rd_conversoes
from engine.rd_conversoes import tipo_de_entrada


@pytest.mark.parametrize(
    "identificador, esperado",
    [
        ("fmd_avare-2_form-central_fev-2026", "inbound"),
        ("form-mobile-lp-mirante-dos-ramos", "inbound"),
        ("/fale-conosco/", "inbound"),
        ("Facebook | meta_ads | meta_ads | M.I.A", "inbound"),
        ("Blip", "inbound"),
        ("Lista compradores - empreendimentos abertos - janeiro 2", "importacao"),
        ("PLANILHA BASE COMUNICADO", "importacao"),
        ("Base Clientes Ativos 27/04/26", "importacao"),
        ("Importação de Leads - Jardim dos Ipês II", "importacao"),
        ("Base leads Avaré -Pesquisa qualitativa", "importacao"),
        ("campaign | Whatsapp | DISPARO_TAGUAI_PRIMEIRAPARTE | M.", "disparo"),
        ("Painel Gestor", "cadastro_manual"),
        (None, "sem_conversao"),
    ],
)
def test_tipo_de_entrada_com_identificadores_reais(identificador, esperado):
    assert tipo_de_entrada(identificador) == esperado


@pytest.fixture
def bases_fake(monkeypatch):
    conteudo = {}
    monkeypatch.setattr(bi.bases, "carregar", lambda k: conteudo.get(k))
    monkeypatch.setattr(bi.bases, "registros", lambda k: (conteudo.get(k) or {}).get("registros") or [])
    monkeypatch.setattr(bi.bases, "resumo", lambda k: {"base": k})
    bi.limpar_cache()

    def definir(chave, registros):
        conteudo[chave] = {"registros": registros, "dados_de": "v", "atualizado_em": "v", "total": len(registros)}
        bi.limpar_cache()

    return definir


def rd(uuid, email, criado="2026-08-10T10:00:00"):
    return {"integration_id": uuid, "email_clean": email, "created_at": criado}


def test_conferencia_rd_separa_lead_perdido_de_lista_importada(bases_fake):
    bases_fake("cv_leads", [{"idlead": 1, "idrd_station": "u-cv", "email": "no.cv@x.com"}])
    bases_fake("rd_leads", [
        rd("u-cv", "a@x.com"),              # no CV pelo UUID
        rd("u-2", "no.cv@x.com"),           # no CV pelo e-mail
        rd("u-form", "form@x.com"),         # converteu em formulário e não chegou
        rd("u-lista", "lista@x.com"),       # veio de lista importada
        rd("u-novo", "novo@x.com"),         # ainda sem classificação
        rd("u-velho", "velho@x.com", criado="2025-01-01T10:00:00"),  # fora do período
    ])
    bases_fake("rd_conversoes", [
        {"uuid": "u-form", "primeira_conversao": "fmd_avare-2_form-central", "tipo": "inbound"},
        {"uuid": "u-lista", "primeira_conversao": "Lista compradores", "tipo": "importacao"},
    ])

    r = conferencias.conferencia_rd(date(2026, 8, 1), date(2026, 8, 31))
    res = r["resumo"]

    assert res["contatos"] == 5
    assert res["no_cv"] == 2
    assert res["inbound_fora"] == 1
    assert res["importado"] == 1
    assert res["pendente"] == 1
    # com contato ainda em classificação, a taxa de falha não é publicada
    assert res["pct_inbound_perdido"] is None

    # classificado o pendente como lista importada, a taxa aparece:
    # 1 formulário perdido para 2 contatos que chegaram
    bases_fake("rd_conversoes", [
        {"uuid": "u-form", "primeira_conversao": "fmd_avare-2_form-central", "tipo": "inbound"},
        {"uuid": "u-lista", "primeira_conversao": "Lista compradores", "tipo": "importacao"},
        {"uuid": "u-novo", "primeira_conversao": "PLANILHA BASE", "tipo": "importacao"},
    ])
    assert conferencias.conferencia_rd(date(2026, 8, 1), date(2026, 8, 31))["resumo"]["pct_inbound_perdido"] == pytest.approx(33.3)
    assert r["itens_inbound_fora"][0]["link_rd"].endswith("/u-form")
    assert "email" not in r["itens_inbound_fora"][0]


def test_classificacao_incremental_nao_repete_contatos(bases_fake, monkeypatch):
    bases_fake("cv_leads", [])
    bases_fake("rd_leads", [rd("u-1", "a@x.com")])
    bases_fake("rd_conversoes", [{"uuid": "u-1", "primeira_conversao": "Lista", "tipo": "importacao"}])
    monkeypatch.setattr(rd_conversoes, "bases", bi.bases)

    registros, status = rd_conversoes.baixar(None, None)

    assert status.mode == "real"
    assert registros == [{"uuid": "u-1", "primeira_conversao": "Lista", "tipo": "importacao"}]
    assert "na fila" not in status.message
