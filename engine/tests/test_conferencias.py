"""
Testes das conferências entre bases.
"""

from datetime import date

import pytest

from engine import bi, conferencias


def cv(idlead, data_cad, email=None, telefone=None, uuid=None, midia=None, utm=None, empreendimento="Avaré - Central Parque II - 13900"):
    return {
        "idlead": idlead, "data_cad": data_cad, "email": email, "telefone": telefone, "idrd_station": uuid,
        "midia_principal": midia,
        "campos_adicionais": [{"slug": f"cf_utm_{k}", "valor": v} for k, v in (utm or {}).items()] or None,
        "empreendimento": [{"nome": empreendimento}], "situacao": {"nome": "Em tratativa Corretor"},
        "link_interesses": f"https://cv/{idlead}",
    }


def bee(id_, criada, email=None, phone=None, uuid=None, campanha="Indique e Ganhe Avaré", emp_campo=None):
    return {
        "ID": id_, "CREATION": criada, "EMAIL": email, "PHONE": phone, "CONVERT": "N",
        "CAMPAIGN": {"NAME": campanha},
        "ADDITIONAL_FIELD": [{"FIELD": "Empreendimento de interesse em Avaré", "VALUE": emp_campo}] if emp_campo else [],
        "ADDITIONAL_INFO": [{"FIELD": "rd_contact_uuid", "VALUE": uuid}] if uuid else [],
    }


@pytest.fixture(autouse=True)
def sem_verificacao_ao_vivo(monkeypatch):
    """Os testes nunca chamam as APIs: sem cache de verificação e sem confirmação em segundo plano."""
    monkeypatch.setattr(conferencias.verificacao, "resultado_valido", lambda email, telefone: None)
    monkeypatch.setattr(conferencias.verificacao, "iniciar_confirmacao", lambda pedidos: {"em_andamento": False})


@pytest.fixture
def bases_fake(monkeypatch):
    conteudo = {}
    monkeypatch.setattr(bi.bases, "carregar", lambda k: conteudo.get(k))
    monkeypatch.setattr(bi.bases, "registros", lambda k: (conteudo.get(k) or {}).get("registros") or [])
    monkeypatch.setattr(bi.bases, "resumo", lambda k: {"base": k, "status": (conteudo.get(k) or {}).get("status")})
    bi.limpar_cache()

    def definir(chave, registros, status_mode="real"):
        conteudo[chave] = {"registros": registros, "dados_de": "v", "atualizado_em": str(len(conteudo)),
                           "total": len(registros), "status": {"mode": status_mode}}
        bi.limpar_cache()

    return definir


def test_beeviral_x_cv_classifica_as_quatro_situacoes(bases_fake):
    bases_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900"])
    bases_fake("cv_leads", [
        cv(1, "2026-09-02 10:00:00", uuid="u-1", utm={"source": "Beeviral"}),              # creditada
        cv(2, "2026-09-03 10:00:00", email="b@x.com", midia="Painel Corretor"),           # sem crédito
        cv(3, "2026-01-10 10:00:00", telefone="14999990000", midia="Facebook Ads"),       # já era lead
    ])
    bases_fake("beeviral", [
        bee("a", "2026-09-02T09:00:00", uuid="u-1"),
        bee("b", "2026-09-03T09:00:00", email="b@x.com"),
        bee("c", "2026-09-04T09:00:00", phone="5514999990000"),
        bee("d", "2026-09-05T09:00:00", email="sumiu@x.com"),
    ])

    r = conferencias.conferencia_beeviral(date(2026, 9, 1), date(2026, 9, 14))
    status = {i["indicacao_id"]: i["status"] for i in r["itens"]}

    assert status == {"a": "creditada", "b": "sem_credito", "c": "ja_era_lead", "d": "nao_chegou"}
    assert r["resumo"]["pct_no_cv"] == 75.0
    assert r["resumo"]["pct_creditada"] == 50.0  # 1 creditada de 2 que entraram pela indicação
    assert r["credito_no_cv"][0]["canal"].startswith("Cadastro comercial")
    item = next(i for i in r["itens"] if i["indicacao_id"] == "b")
    assert item["cv_link"] == "https://cv/2"
    assert "email" not in item  # sem dado pessoal na lista


def test_plataforma_sem_base_fica_indisponivel(bases_fake):
    bases_fake("cv_empreendimentos", [])
    bases_fake("cv_leads", [cv(1, "2026-09-02 10:00:00", midia="Facebook Ads")])
    bases_fake("meta_insights", [], status_mode="erro")

    r = conferencias.conferencia_plataforma(date(2026, 9, 1), date(2026, 9, 14), "meta")

    assert r["disponivel"] is False
    assert r["resumo"]["leads_crm"] == 1


def test_meta_x_cv_por_empreendimento(bases_fake):
    bases_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900", "Taguaí - Jardim dos Ipês III - 17701"])
    bases_fake("cv_leads", [
        cv(i, "2026-09-02 10:00:00", utm={"source": "meta ads", "medium": "fb", "campaign": "jardim-dos-ipes-3_meta-gdc_always-on"},
           empreendimento="Taguaí - Jardim dos Ipês III - 17701")
        for i in range(8)
    ])
    bases_fake("meta_insights", [{
        "plataforma": "meta", "conta_nome": "ML - Jardim dos Ipês III", "campanha_nome": "jardim-dos-ipes-3_meta-gdc_always-on",
        "data": "2026-09-02", "investimento": 500.0, "leads_plataforma": 10, "cliques": 90, "conversas_whatsapp": 2,
    }])

    r = conferencias.conferencia_plataforma(date(2026, 9, 1), date(2026, 9, 14), "meta")
    emp = r["por_empreendimento"][0]

    assert emp["empreendimento"] == "Taguaí - Jardim dos Ipês III - 17701"
    assert emp["leads_plataforma"] == 10 and emp["leads_crm"] == 8
    assert emp["pct_chegou"] == 80.0
    assert emp["cpl_plataforma"] == 50.0 and emp["cpl_crm"] == 62.5
    assert r["por_campanha"][0]["leads_crm"] == 8 and r["por_campanha"][0]["leads_plataforma"] == 10
    assert sum(d["leads_plataforma"] for d in r["serie"]) == 10


def test_formularios_da_meta_lead_a_lead(bases_fake):
    bases_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900"])
    bases_fake("cv_leads", [
        cv(1, "2026-09-02 10:05:00", email="chegou@x.com", midia="Facebook Ads"),
        cv(2, "2026-09-03 10:05:00", telefone="14999990000", midia="Painel Corretor"),
        cv(3, "2026-02-01 10:00:00", email="antigo@x.com", midia="Google"),
        # mesmo número do f5, cadastrado sem o nono dígito
        cv(4, "2026-09-06 10:30:00", telefone="1499991234", midia="Facebook Ads"),
    ])
    bases_fake("meta_insights", [])
    bases_fake("rd_leads", [{"source_lead_id": "uuid-4", "email_clean": "sumiu@x.com", "created_at": "2026-09-05T10:01:00"}])
    bases_fake("rd_conversoes", [{"uuid": "uuid-4", "primeira_conversao": "Campanha Meta", "tipo": "inbound"}])

    def form(id_, criado, email=None, fone=None, nome="Fulano de Tal"):
        return {"source_lead_id": id_, "created_at": criado, "email_clean": email, "phone_clean": fone,
                "email": email, "phone": fone, "campaign_name": "avare-2-central_meta-gdc_always-on",
                "raw_payload": {"formulario": "Form Central", "pagina": "Moura Leite Loteamentos", "nome": nome,
                                "email": email, "phone": fone, "conjunto": "Público quente", "anuncio": "Vídeo 01",
                                "plataforma": "Instagram", "organico": False, "respostas": {"estou em busca de": "moradia"}}}

    bases_fake("meta_leads", [
        form("f1", "2026-09-02T10:00:00", email="chegou@x.com"),
        form("f2", "2026-09-03T10:00:00", fone="5514999990000"),
        form("f3", "2026-09-04T10:00:00", email="antigo@x.com"),
        form("f4", "2026-09-05T10:00:00", email="sumiu@x.com", nome="Maria Sumida"),
        form("f5", "2026-09-06T10:00:00", email="outro@x.com", fone="5514999991234"),
    ])

    r = conferencias.conferencia_plataforma(date(2026, 9, 1), date(2026, 9, 14), "meta")["formularios"]

    assert r["resumo"]["leads"] == 5
    assert (r["resumo"]["no_cv"], r["resumo"]["provavel_no_cv"], r["resumo"]["ja_era_lead"], r["resumo"]["nao_chegou"]) == (2, 1, 1, 1)
    assert r["resumo"]["pct_nao_chegou"] == pytest.approx(25.0)
    # chegou no CV, mas registrado como corretor: crédito errado
    assert r["credito_errado_no_cv"][0]["canal"].startswith("Cadastro comercial")

    [sumiu] = r["itens_nao_chegaram"]
    assert sumiu["id"] == "f4"
    # dados para procurar no CV e a origem completa do anúncio
    assert (sumiu["nome"], sumiu["email"]) == ("Maria Sumida", "sumiu@x.com")
    assert (sumiu["plataforma"], sumiu["conjunto"], sumiu["anuncio"]) == ("Instagram", "Público quente", "Vídeo 01")
    assert sumiu["respostas"] == {"estou em busca de": "moradia"}
    # passou pelo RD e parou antes do CV
    assert sumiu["rd"] == {"no_rd": True, "uuid": "uuid-4", "link": "https://app.rdstation.com.br/leads/public/uuid-4",
                           "entrada": "2026-09-05", "primeira_conversao": "Campanha Meta", "tipo": "inbound"}
    assert r["resumo"]["nao_chegou_mas_no_rd"] == 1 and r["resumo"]["nao_chegou_nem_no_rd"] == 0

    [provavel] = r["itens_provaveis"]
    assert provavel["id"] == "f5" and provavel["provavel_link"] == "https://cv/4"
    assert "nono dígito" in provavel["provavel_motivo"]
    # quem chegou no CV não expõe dados de contato
    assert all("email" not in i for i in r["itens_nao_chegaram"] + r["itens_provaveis"] if i["status"] == "no_cv")


def test_lead_antigo_so_no_indice_nao_e_dado_como_nao_chegou(bases_fake):
    """Lead cadastrado anos atrás (fora dos 13 meses da base) está no índice de todos os leads."""
    bases_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900"])
    bases_fake("cv_leads", [])
    bases_fake("cv_indice", [cv(7, "2021-03-01 10:00:00", email="antiga@x.com", midia="Facebook Ads")])
    bases_fake("meta_insights", [])
    bases_fake("meta_leads", [{
        "source_lead_id": "f9", "created_at": "2026-09-05T10:00:00", "email_clean": "antiga@x.com", "phone_clean": None,
        "campaign_name": "avare-2-central", "raw_payload": {"formulario": "Form", "nome": "Antiga Cliente", "email": "antiga@x.com"},
    }])

    r = conferencias.conferencia_plataforma(date(2026, 9, 1), date(2026, 9, 14), "meta")["formularios"]
    assert r["resumo"]["ja_era_lead"] == 1 and r["resumo"]["nao_chegou"] == 0
    assert r["indice_cv"] == {"leads": 1, "cobre_todos_os_leads": True}


def test_confirmacao_ao_vivo_corrige_quem_existe_no_cv(bases_fake, monkeypatch):
    bases_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900"])
    bases_fake("cv_leads", [])
    bases_fake("meta_insights", [])
    bases_fake("meta_leads", [
        {"source_lead_id": "a", "created_at": "2026-09-05T10:00:00", "email_clean": "existe@x.com", "phone_clean": None,
         "campaign_name": "c", "raw_payload": {"formulario": "Form", "nome": "Existe", "email": "existe@x.com"}},
        {"source_lead_id": "b", "created_at": "2026-09-06T10:00:00", "email_clean": "sumiu@x.com", "phone_clean": None,
         "campaign_name": "c", "raw_payload": {"formulario": "Form", "nome": "Sumiu", "email": "sumiu@x.com"}},
    ])
    ao_vivo = {
        "existe@x.com": {"verificado_em": "2026-09-14T15:00:00+00:00", "rd": {"consultado": True, "encontrado": False},
                         "cv": {"consultado": True, "encontrado": True,
                                "leads": [{"idlead": 5, "link": "https://cv/5", "data_cad": "2022-01-10 09:00:00", "situacao": "Cancelado"}]}},
        "sumiu@x.com": {"verificado_em": "2026-09-14T15:00:00+00:00", "rd": {"consultado": True, "encontrado": True, "uuid": "u1",
                                                                             "link": "https://app.rdstation.com.br/leads/public/u1"},
                        "cv": {"consultado": True, "encontrado": False, "leads": []}},
    }
    monkeypatch.setattr(conferencias.verificacao, "resultado_valido", lambda email, telefone: ao_vivo.get(email))

    r = conferencias.conferencia_plataforma(date(2026, 9, 1), date(2026, 9, 14), "meta")["formularios"]
    # quem existe no CV sai da lista, vira "já era lead" e perde os dados de contato
    assert r["resumo"]["ja_era_lead"] == 1 and r["resumo"]["nao_chegou"] == 1
    [sumiu] = r["itens_nao_chegaram"]
    assert sumiu["id"] == "b" and sumiu["confirmacao"]["estado"] == "confirmado"
    # o RD ao vivo corrige a coluna "No RD Station?"
    assert sumiu["rd"]["no_rd"] is True and sumiu["rd"]["link"].endswith("/u1")
    assert r["confirmacao"]["corrigidos"] == 1 and r["confirmacao"]["pendentes"] == 0


def test_beeviral_links_diretos_contato_so_de_quem_nao_chegou_e_origem_das_vendas(bases_fake):
    bases_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900"])
    vendido = cv(1, "2026-09-02 10:05:00", email="comprou@x.com", midia="Painel Corretor")
    vendido.update(data_venda="2026-09-10", valor_venda="150000")
    bases_fake("cv_leads", [vendido])
    bases_fake("beeviral", [
        bee("b1", "2026-09-02T10:00:00", email="comprou@x.com", uuid="uuid-comprou"),
        bee("b2", "2026-09-03T10:00:00", email="sumiu@x.com", phone="14999990000"),
    ])

    r = conferencias.conferencia_beeviral(date(2026, 9, 1), date(2026, 9, 14))
    itens = {i["indicacao_id"]: i for i in r["itens"]}

    assert itens["b1"]["bee_link"] == "https://account.beeviral.app/recommendation/edit/b1"
    assert itens["b1"]["rd_link"] == "https://app.rdstation.com.br/leads/public/uuid-comprou"
    assert itens["b1"]["cv_link"] == "https://cv/1" and "email" not in itens["b1"]
    # quem não chegou traz o contato para procurar, e aguarda a confirmação ao vivo
    assert (itens["b2"]["email"], itens["b2"]["telefone"]) == ("sumiu@x.com", "14999990000")
    assert itens["b2"]["confirmacao"]["estado"] == "pendente" and itens["b2"]["rd_link"] is None

    [venda] = r["vendas"]
    assert venda["indicacao_id"] == "b1" and venda["cv_valor_venda"] == 150000.0 and venda["cv_data_venda"] == "2026-09-10"
    assert venda["status"] == "sem_credito" and venda["cv_canal"].startswith("Cadastro comercial")
    assert r["resumo"]["vgv_vendidas"] == 150000.0


def test_venda_de_quem_foi_indicado_varias_vezes_conta_uma_vez_e_venda_anterior_fica_fora(bases_fake):
    bases_fake("cv_empreendimentos", ["Avaré - Central Parque II - 13900"])
    repetido = cv(1, "2026-07-01 10:00:00", email="repetido@x.com", midia="Painel Corretor")
    repetido.update(data_venda="2026-07-20", valor_venda="67110.91")
    antigo = cv(2, "2026-05-01 10:00:00", email="antigo@x.com", midia="Google")
    antigo.update(data_venda="2026-05-26", valor_venda="93046.47")
    bases_fake("cv_leads", [repetido, antigo])
    bases_fake("beeviral", [
        bee("b1", "2026-07-02T10:00:00", email="repetido@x.com", campanha="Corretor A | Indique e Ganhe"),
        bee("b2", "2026-07-05T10:00:00", email="repetido@x.com", campanha="Corretor B | Indique e Ganhe"),
        bee("b3", "2026-07-06T10:00:00", email="repetido@x.com", campanha="Corretor A | Indique e Ganhe"),
        bee("b4", "2026-07-10T10:00:00", email="antigo@x.com"),
    ])

    r = conferencias.conferencia_beeviral(date(2026, 6, 1), date(2026, 7, 31))
    assert r["resumo"]["indicacoes"] == 4
    assert len(r["vendas"]) == 2
    repetida = next(v for v in r["vendas"] if v["cv_id"] == 1)
    assert repetida["indicacoes_do_lead"] == 3 and repetida["indicacao_id"] == "b1"
    assert repetida["campanhas_do_lead"] == ["Corretor A | Indique e Ganhe", "Corretor B | Indique e Ganhe"]
    anterior = next(v for v in r["vendas"] if v["cv_id"] == 2)
    assert anterior["venda_antes_da_indicacao"] is True
    # só a venda feita depois da indicação entra, e uma única vez
    assert r["resumo"]["vendidas"] == 1 and r["resumo"]["vgv_vendidas"] == 67110.91
    assert r["resumo"]["vendas_antes_da_indicacao"] == 1
