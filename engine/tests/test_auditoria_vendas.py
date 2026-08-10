"""
Testes da auditoria de vendas × leads.
"""

from datetime import date

import pytest

from engine import auditoria_vendas, bi, identidade  # noqa: F401  (identidade registra o cache do índice)

CP2 = "Avaré - Central Parque II - 13900"


def lead(idlead, data_cad, midia, email):
    return {"idlead": idlead, "data_cad": data_cad, "midia_principal": midia, "situacao": {"nome": "Cancelado"},
            "empreendimento": [{"id": 1, "nome": CP2}], "email": email, "telefone": None,
            "link_interesses": f"https://cv/lead/{idlead}"}


def reserva(idreserva, data_venda, leads=(), email=None, midia="Painel Corretor", valor=100000.0):
    return {"idreserva": str(idreserva), "vendida": True, "data_venda": f"{data_venda} 10:00:00", "empreendimento": CP2,
            "bloco": "Q1", "unidade": f"L-{idreserva}", "valor_contrato": valor, "leads_associados": [str(l) for l in leads],
            "titular_email": email, "titular_telefone": None, "midia": midia, "imobiliaria": "Imob X", "corretor": "Fulano"}


@pytest.fixture
def base_fake(monkeypatch):
    conteudo = {}
    monkeypatch.setattr(bi.bases, "carregar", lambda chave: conteudo.get(chave))
    monkeypatch.setattr(bi.bases, "registros", lambda chave: (conteudo.get(chave) or {}).get("registros") or [])
    monkeypatch.setattr(bi.bases, "resumo", lambda chave: {"base": chave})

    def definir(chave, registros):
        conteudo[chave] = {"registros": registros, "dados_de": "v1", "atualizado_em": f"v{len(conteudo)}", "total": len(registros)}
        bi.limpar_cache()

    return definir


def test_auditoria_encontra_vendas_online_nao_contabilizadas(base_fake):
    base_fake("cv_leads", [
        lead(1, "2026-08-01", "Facebook Ads", "ana@exemplo.com"),     # lead online da Ana
        lead(2, "2026-08-20", "Painel Corretor", "ana@exemplo.com"),  # a reserva foi ligada a este
        lead(3, "2026-08-05", "Painel Corretor", "bia@exemplo.com"),
        lead(4, "2026-08-05", "Painel Corretor", "caio@exemplo.com"),
        lead(5, "2026-08-05", "Painel Corretor", "davi@exemplo.com"),
    ])
    base_fake("rd_leads", [
        {"email_clean": "bia@exemplo.com", "created_at": "2026-08-02T10:00:00", "source_lead_id": "uuid-bia"},
        {"email_clean": "davi@exemplo.com", "created_at": "2026-09-20T10:00:00", "source_lead_id": "uuid-davi"},  # depois da venda
    ])
    base_fake("meta_leads", [{"email_clean": "eva@exemplo.com", "created_at": "2026-08-03T10:00:00", "campaign_name": "CP2 leads"}])
    base_fake("cv_reservas", [
        reserva(10, "2026-09-05", leads=[2]),                              # outro lead online da mesma pessoa
        reserva(11, "2026-09-06", midia="Click To WhatsApp"),              # sem lead, mídia online na reserva
        reserva(12, "2026-09-07", leads=[3]),                              # só RD antes da venda
        reserva(13, "2026-09-08", leads=[4]),                              # nenhum sinal
        reserva(14, "2026-09-09", leads=[1]),                              # já online
        reserva(15, "2026-09-10", email="eva@exemplo.com"),                # formulário Meta, sem lead no CV
        reserva(16, "2026-09-11", leads=[5]),                              # RD só depois da venda: sem sinal
    ])

    r = auditoria_vendas.auditar(date(2026, 9, 1), date(2026, 9, 30))
    status = {i["idreserva"]: i["status"] for i in r["itens"]}
    assert status == {
        "10": "online_nao_contabilizada", "15": "online_nao_contabilizada",
        "11": "provavel_online",  # só a mídia da reserva: indício, não prova
        "12": "possivel_online", "13": "sem_sinal_online", "16": "sem_sinal_online",
    }
    s = r["resumo"]
    assert (s["vendas"], s["online"], s["online_nao_contabilizada"], s["provavel_online"], s["possivel_online"]) == (7, 1, 2, 1, 1)
    assert s["pct_online_potencial"] == round(3 / 7 * 100, 1)

    item10 = next(i for i in r["itens"] if i["idreserva"] == "10")
    assert item10["sinais"][0]["tipo"] == "outro_lead_online" and item10["sinais"][0]["link"] == "https://cv/lead/1"
    assert "outro lead" in item10["sugestao"]
    assert next(i for i in r["itens"] if i["idreserva"] == "11")["ligacao"] == "sem_lead"
    assert all("titular_email" not in i and "titular_telefone" not in i for i in r["itens"])
    assert any("iriam de 1 para 3" in f for f in r["leituras"])
    assert all("midia_reserva_online" not in i for i in r["itens"])
    assert r["por_imobiliaria"][0] == {"nome": "Imob X", "vendas": 3}


def test_lead_online_de_mais_de_um_ano_e_so_indicio(base_fake):
    base_fake("cv_leads", [
        lead(1, "2021-03-10", "WhatsApp", "ana@exemplo.com"),
        lead(2, "2026-08-20", "Painel Corretor", "ana@exemplo.com"),
    ])
    base_fake("cv_reservas", [reserva(10, "2026-09-05", leads=[2])])
    item = auditoria_vendas.auditar(date(2026, 9, 1), date(2026, 9, 30))["itens"][0]
    assert item["status"] == "provavel_online"
    assert item["sinais"][0]["tipo"] == "lead_online_antigo" and "mais de um ano" in item["sugestao"]


def test_lead_online_da_pessoa_sem_vinculo_com_a_reserva_nao_conta_como_online(base_fake):
    """O CV só conta a venda como online pelo lead vinculado: achar o lead pelo e-mail mostra a origem, não conta."""
    base_fake("cv_leads", [lead(1, "2026-08-20", "Facebook Ads", "ana@exemplo.com")])
    base_fake("cv_reservas", [reserva(10, "2026-09-05", email="ana@exemplo.com"),  # sem lead vinculado
                              reserva(11, "2026-09-06", leads=[1])])               # mesmo lead, vinculado
    r = auditoria_vendas.auditar(date(2026, 9, 1), date(2026, 9, 30))
    status = {i["idreserva"]: i["status"] for i in r["itens"]}
    assert status["10"] == "online_sem_vinculo"
    assert "11" not in status  # contada como online: não aparece na lista de conferência
    assert (r["resumo"]["online"], r["resumo"]["online_sem_vinculo"]) == (1, 1)
    item = next(i for i in r["itens"] if i["idreserva"] == "10")
    assert item["sinais"][0]["tipo"] == "lead_online_sem_vinculo"
    assert "Vincule esse lead à reserva" in item["sugestao"]


def test_sem_base_de_reservas_a_auditoria_fica_indisponivel(base_fake):
    base_fake("cv_leads", [lead(1, "2026-08-01", "Facebook Ads", "ana@exemplo.com")])
    r = auditoria_vendas.auditar(date(2026, 9, 1), date(2026, 9, 30))
    assert r["disponivel"] is False and r["resumo"]["vendas"] == 0
