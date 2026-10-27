"""
Testes da auditoria de anúncios: atribuição anúncio → lead do CV, métricas e campeões.
"""

from datetime import date

import pytest

from engine import anuncios, bi

CP2 = "Avaré - Central Parque II - 13900"


def lead(idlead, data_cad, email, midia="Facebook Ads", utm=None, tags=(), situacao="Cancelado", data_venda=None, valor=None):
    return {
        "idlead": idlead, "data_cad": data_cad, "email": email, "telefone": None, "midia_principal": midia,
        "campos_adicionais": [{"slug": f"cf_utm_{k}", "valor": v} for k, v in (utm or {}).items()] or None,
        "tags": [{"nome": t} for t in tags], "situacao": {"nome": situacao}, "data_venda": data_venda, "valor_venda": valor,
        "empreendimento": [{"id": 1, "nome": CP2}], "link_interesses": f"https://cv/{idlead}",
    }


def linha(anuncio_id, anuncio, dia, investimento, leads, conjunto="c1"):
    return {
        "plataforma": "meta", "conta_id": "act_1", "conta_nome": "ML - Central Parque Avaré 2", "campanha_nome": "avare-2-central",
        "conjunto_nome": conjunto, "anuncio_id": anuncio_id, "anuncio_nome": anuncio, "data": dia, "investimento": investimento,
        "impressoes": 1000, "cliques": 20, "leads_plataforma": leads, "conversas_whatsapp": 0, "status": "ACTIVE", "miniatura": "https://img/1",
    }


@pytest.fixture
def base_fake(monkeypatch):
    conteudo = {}
    monkeypatch.setattr(bi.bases, "carregar", lambda k: conteudo.get(k))
    monkeypatch.setattr(bi.bases, "registros", lambda k: (conteudo.get(k) or {}).get("registros") or [])
    monkeypatch.setattr(bi.bases, "resumo", lambda k: {"base": k})
    bi.limpar_cache()

    def definir(chave, registros):
        conteudo[chave] = {"registros": registros, "dados_de": "v", "atualizado_em": str(len(conteudo) + len(registros)), "total": len(registros)}
        bi.limpar_cache()

    definir("cv_empreendimentos", [CP2])
    definir("meta_anuncios", [
        linha("111", "video-a", "2026-09-02", 100.0, 6),
        linha("111", "video-a", "2026-09-03", 100.0, 4),
        linha("222", "imagem-b", "2026-09-03", 300.0, 6),
    ])
    definir("meta_leads", [{
        "source_lead_id": "f1", "created_at": "2026-09-03T10:00:00", "email_clean": "form@x.com", "phone_clean": None,
        "raw_payload": {"conjunto": "c1", "anuncio": "imagem-b", "anuncio_id": "222"},
    }])
    definir("cv_leads", [
        lead(1, "2026-09-02 10:00:00", "a1@x.com", utm={"source": "facebook", "content": "Adset Name: c1 || Ad Name: video-a"},
             tags=["mia-qualificado"], situacao="Vendido", data_venda="2026-09-10", valor="150000"),
        lead(2, "2026-09-03 10:00:00", "a2@x.com", utm={"source": "facebook", "content": "Adset Name: C1 || Ad Name: Video-A"}),
        lead(3, "2026-09-03 10:05:00", "form@x.com"),
        lead(4, "2026-09-04 10:00:00", "sem@x.com"),
        lead(5, "2026-09-04 11:00:00", "whats@x.com", midia="WhatsApp", utm={"source": "google", "medium": "cpc"}),
    ])
    return definir


def test_le_o_padrao_de_utm_content_das_campanhas():
    assert anuncios.ler_utm_content("Adset Name: avare-2_interesses || Ad Name: avare-2_video") == ("avare-2_interesses", "avare-2_video")
    assert anuncios.ler_utm_content("Ad Name: so-anuncio") == (None, "so-anuncio")
    assert anuncios.ler_utm_content("video-sem-padrao") == (None, None)


def test_atribui_por_formulario_e_utm_e_calcula_custos(base_fake):
    r = anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30))
    por_nome = {a["anuncio"]: a for a in r["anuncios"]}
    a, b = por_nome["video-a"], por_nome["imagem-b"]

    assert (a["leads_plataforma"], a["leads_cv"], a["investimento"]) == (10, 2, 200.0)
    assert a["cpl_real"] == 100.0 and a["cpl_plataforma"] == 20.0 and a["pct_chegou"] == 20.0
    assert (a["sql"], a["vendas"], a["vgv"], a["taxa_venda"]) == (1, 1, 150000.0, 50.0)
    assert a["roas"] == 750.0 and a["empreendimento"] == CP2
    assert b["leads_cv"] == 1 and list(b["fontes"]) == [anuncios.FONTES["formulario"]]

    # lead de Meta sem UTM nem formulário fica sem anúncio (o do Google não entra)
    assert r["resumo"]["leads_meta_cv"] == 4 and r["resumo"]["leads_atribuidos"] == 3 and r["resumo"]["cobertura"] == 75.0
    assert r["resumo"]["cpl_real"] == 125.0


def test_campeoes_respeitam_amostra_minima(base_fake, monkeypatch):
    r = anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30))
    campeoes = {c["id"]: c for c in r["campeoes"]}
    assert campeoes["mais_leads"]["anuncio"]["anuncio"] == "video-a"
    # 2 leads não bastam para ranking de custo e conversão
    assert campeoes["menor_cpl"]["anuncio"] is None and "5+" in campeoes["menor_cpl"]["motivo_vazio"]
    assert campeoes["maior_conversao"]["anuncio"] is None

    monkeypatch.setattr(anuncios, "MIN_LEADS_CPL", 1)
    monkeypatch.setattr(anuncios, "MIN_LEADS_CONVERSAO", 1)
    r = anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30))
    campeoes = {c["id"]: c for c in r["campeoes"]}
    assert campeoes["menor_cpl"]["anuncio"]["anuncio"] == "video-a" and campeoes["menor_cpl"]["valor"] == 100.0
    assert campeoes["eficiencia"]["anuncio"]["anuncio"] == "video-a"
    assert campeoes["maior_conversao"]["anuncio"]["anuncio"] == "video-a"
    assert campeoes["menor_custo_venda"]["valor"] == 200.0


def test_campeao_sql_exige_criativo_disponivel():
    comum = {
        "investimento": 0,
        "cpl_real": None,
        "eficiencia": None,
        "vendas": 0,
        "taxa_venda": 0,
        "custo_por_venda": None,
    }
    sem_criativo = {
        **comum,
        "anuncio": "sem imagem",
        "leads_cv": 10,
        "sql": 5,
        "taxa_sql": 50.0,
        "miniatura": None,
        "anuncio_ids": [],
        "sem_dados_da_plataforma": True,
    }
    com_criativo = {
        **comum,
        "anuncio": "com imagem",
        "leads_cv": 11,
        "sql": 5,
        "taxa_sql": 45.5,
        "miniatura": "https://example.test/criativo.jpg",
        "anuncio_ids": ["123"],
        "sem_dados_da_plataforma": False,
    }

    por_id = {c["id"]: c for c in anuncios.campeoes([sem_criativo, com_criativo])}

    assert por_id["maior_qualificacao"]["anuncio"]["anuncio"] == "com imagem"
    assert "criativo disponível" in por_id["maior_qualificacao"]["criterio"]


def test_leads_por_tras_do_anuncio_e_sem_anuncio(base_fake):
    r = anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30))
    chave = next(a["chave"] for a in r["anuncios"] if a["anuncio"] == "video-a")
    detalhe = anuncios.leads_do_anuncio(date(2026, 9, 1), date(2026, 9, 30), chave)
    assert detalhe["total"] == 2 and {i["link"] for i in detalhe["itens"]} == {"https://cv/1", "https://cv/2"}
    assert "email" not in detalhe["itens"][0]
    sem = anuncios.leads_do_anuncio(date(2026, 9, 1), date(2026, 9, 30), anuncios.SEM_ANUNCIO)
    assert [i["id"] for i in sem["itens"]] == [4]


def test_filtro_sem_anuncio_explica_o_motivo_e_mostra_onde_ha_anuncios(base_fake):
    r = anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30), ["Itatinga - Novo Horizonte - 16103"])
    assert r["anuncios"] == [] and r["resumo"]["leads_meta_cv"] == 0
    assert r["filtro_ativo"] is True and "filtro selecionado" in r["motivo_vazio"]
    assert r["empreendimentos_com_anuncios"] == [{"empreendimento": CP2, "anuncios": 2, "investimento": 500.0}]

    # praça também filtra os anúncios
    assert len(anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30), pracas=["Avaré"])["anuncios"]) == 2
    assert anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30), pracas=["Itu"])["anuncios"] == []


def test_leads_de_meta_sem_anuncio_nas_contas_lidas_explicam_a_conta_sem_acesso(base_fake):
    base_fake("meta_anuncios", [])
    base_fake("cv_leads", [lead(9, "2026-09-05 10:00:00", "semutm@x.com")])
    r = anuncios.auditoria(date(2026, 9, 1), date(2026, 9, 30))
    assert r["anuncios"] == [] and r["resumo"]["leads_meta_cv"] == 1
    assert "sem UTM de anúncio" in r["motivo_vazio"] and "não está liberada" in r["motivo_vazio"]
