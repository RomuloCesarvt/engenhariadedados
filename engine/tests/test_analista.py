"""
Testes do analista digital: cada regra gera o achado certo e não gera alarme com amostra pequena.
"""

from datetime import date

from engine import analista

CP2, NH, RR = "Avaré - Central Parque II - 13900", "Itatinga - Novo Horizonte - 16103", "Tatuí - Reserva dos Ramos Residencial - 14704"


def emp(nome, leads=0, meta=0, invest=0.0):
    return {"empreendimento": nome, "leads": leads, "meta": meta, "investimento_meta": invest,
            "cpl_meta_crm": round(invest / meta, 2) if invest and meta else None}


def bi_fake(leads=100, leads_ant=100, emps=(), funil=None, funil_ant=None, vendas_online=0, vendas_online_ant=0):
    return {
        "kpis": {"leads": leads, "vendas": vendas_online, "vgv": 0.0, "vgv_online": 0.0, "vendas_online": vendas_online,
                 "anterior": {"leads": leads_ant, "vendas_online": vendas_online_ant},
                 "variacao": {"leads": analista._variacao(leads, leads_ant), "vendas": None},
                 "unidades_vendidas": 0, "unidades_sem_lead": 0},
        "por_empreendimento": list(emps),
        "funil": {"online": funil or []},
        "funil_anterior": funil_ant or [],
        "investimento": {"meta": 0.0, "google": 0.0},
        "qualidade": {"leads": leads, "whatsapp_sem_rastreio": 0},
    }


def etapas(*qtds):
    saida, anterior = [], None
    for i, q in enumerate(qtds):
        saida.append({"etapa": f"e{i}", "label": f"Etapa {i}", "leads": q,
                      "pct_da_etapa_anterior": round(q / anterior * 100, 1) if anterior else None})
        anterior = q
    return saida


def test_variacao_de_leads_exige_amostra_minima():
    assert analista.achados_leads(bi_fake(leads=5, leads_ant=20)) == []  # 20 leads antes: amostra pequena
    [a] = analista.achados_leads(bi_fake(leads=60, leads_ant=100))
    assert a["tipo"] == "alerta" and "caíram -40,0%" in a["titulo"]


def test_empreendimentos_cpl_subiu_investimento_sem_lead_e_leads_sem_investimento():
    atual = bi_fake(emps=[emp(CP2, leads=100, meta=50, invest=5000), emp(NH, leads=10, meta=0, invest=800),
                          emp(RR, leads=40, meta=30, invest=0)])
    anterior = bi_fake(emps=[emp(CP2, leads=110, meta=100, invest=5000), emp(NH, leads=5, meta=2, invest=100)])
    ids = {a["id"]: a for a in analista.achados_empreendimentos(atual, anterior)}

    assert ids[f"emp_cpl:{CP2}"]["tipo"] == "alerta"            # R$ 50 -> R$ 100 por lead
    assert ids[f"emp_invest_sem_lead:{NH}"]["tipo"] == "alerta"
    assert ids[f"emp_leads_sem_invest:{RR}"]["area"] == "dados"
    assert f"emp_leads:{CP2}" not in ids                        # -9%: abaixo do limite
    assert f"emp_leads:{NH}" not in ids                         # 5 leads antes: amostra pequena
    assert "Central Parque II (Avaré)" in ids[f"emp_cpl:{CP2}"]["titulo"]


def test_funil_aponta_queda_de_passagem_e_maior_perda():
    atual = bi_fake(funil=etapas(200, 100, 30, 10), funil_ant=etapas(200, 140, 42, 14))
    ids = {a["id"]: a for a in analista.achados_funil(atual)}
    assert ids["funil_passagem:e1"]["tipo"] == "alerta"           # 70% -> 50%
    assert "funil_passagem:e2" not in ids                         # 30% -> 30%
    assert ids["funil_maior_perda"]["tipo"] == "contexto" and "Etapa 0" in ids["funil_maior_perda"]["titulo"]


def anuncio(chave, leads, invest, leads_plat=0):
    return {"chave": chave, "anuncio": f"Anúncio {chave}", "conjunto": "Conj", "empreendimento": CP2,
            "leads_cv": leads, "investimento": invest, "leads_plataforma": leads_plat,
            "cpl_real": round(invest / leads, 2) if leads else None, "taxa_sql": 20.0,
            "eficiencia": round(leads ** 2 / invest, 4) if leads and invest else None, "sem_dados_da_plataforma": False}


def test_anuncios_sem_lead_escalar_caros_e_piorando():
    lista = [anuncio("a", 20, 200), anuncio("b", 10, 200), anuncio("c", 10, 220), anuncio("d", 10, 240),
             anuncio("e", 10, 600), anuncio("f", 0, 400, leads_plat=8), anuncio("g", 2, 50)]
    ads = {"disponivel": True, "anuncios": lista, "campeoes": [], "resumo": {"cobertura": 90}}
    ads_ant = {"anuncios": [anuncio("e", 10, 200)]}
    ids = {a["id"]: a for a in analista.achados_anuncios(ads, ads_ant)}

    assert "R$ 400" in ids["anuncios_sem_lead"]["titulo"]
    assert ids["anuncios_escalar"]["evidencias"][0]["rotulo"].startswith("Anúncio a")   # R$ 10 vs mediana R$ 22
    assert ids["anuncios_caros"]["evidencias"][0]["rotulo"].startswith("Anúncio e")     # R$ 60 = 2,7× a mediana
    assert "R$ 20,00 → R$ 60,00" in ids["anuncios_piorando"]["evidencias"][0]["valor"]
    assert "anuncios_cobertura" not in ids


def test_analisar_ordena_por_prioridade_e_isola_falhas(monkeypatch):
    monkeypatch.setattr(analista.bi, "calcular_bi", lambda i, f, e=None, p=None, escopo="online":
                        bi_fake(leads=60, leads_ant=100) if i == date(2026, 9, 1) else bi_fake())
    monkeypatch.setattr(analista.anuncios, "auditoria", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sem base")))
    monkeypatch.setattr(analista.auditoria_vendas, "auditar", lambda *a, **k: {"disponivel": False})
    monkeypatch.setattr(analista.diagnosticos, "calcular", lambda *a, **k: {"itens": []})
    monkeypatch.setattr(analista.bases, "carregar", lambda chave: None)
    analista._cache.clear()

    r = analista.analisar(date(2026, 9, 1), date(2026, 9, 30))
    assert r["falhas"] == ["anúncios"]
    assert r["achados"][0]["id"] == "leads_variacao"
    assert [a["prioridade"] for a in r["achados"]] == sorted((a["prioridade"] for a in r["achados"]), reverse=True)
    assert r["periodo"]["anterior_inicio"] == "2026-08-02" and r["contagem"]["alerta"] == 1
