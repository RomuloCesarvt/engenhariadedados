"""
Testes da leitura de reservas do CV (sem chamar a API).
"""

from engine.extractors import cv_crm
from engine.extractors.cv_crm import CVCRMExtractor, reserva_enxuta, valor_monetario


def reserva(vendida="S", leads=None):
    return {
        "situacao": {"idsituacao": 3, "situacao": "Vendida"},
        "vendida": vendida, "data": "2026-08-01 10:00:00", "data_venda": "2026-08-10 09:00:00" if vendida == "S" else None,
        "unidade": {"empreendimento": "Avaré - Central Parque II - 13900", "idempreendimento_cv": 7, "etapa": "1", "bloco": "Q3", "unidade": "L12"},
        "condicoes": {"valor_contrato": "93.046,47", "vgv_tabela": "95000.00"},
        "titular": {"nome": "Fulano", "email": "f@x.com", "celular": "14999990000", "documento": "000"},
        "corretor": {"corretor": "Maria Corretora", "imobiliaria": "Imob X"},
        "imobiliaria": {"nome": "Imobiliária X"},
        "tipovenda": "Venda Imobiliária", "midia": "Facebook",
        "leads_associados": leads if leads is not None else [{"idlead": 123, "idsituacao": 1, "data_cad": "2026-07-01"}],
        "idprecadastro": 55,
    }


def test_valores_em_formato_brasileiro_ou_americano():
    assert valor_monetario("93.046,47") == 93046.47
    assert valor_monetario("93046.47") == 93046.47
    assert valor_monetario("R$ 1.200,00") == 1200.0
    assert valor_monetario("") is None and valor_monetario(None) is None


def test_reserva_enxuta_traz_venda_unidade_valor_e_lead_sem_documento():
    r = reserva_enxuta(reserva())
    assert r["vendida"] is True and r["data_venda"].startswith("2026-08-10")
    assert (r["empreendimento"], r["bloco"], r["unidade"]) == ("Avaré - Central Parque II - 13900", "Q3", "L12")
    assert r["valor_contrato"] == 93046.47 and r["vgv_tabela"] == 95000.0
    assert r["leads_associados"] == ["123"] and r["midia"] == "Facebook" and r["imobiliaria"] == "Imobiliária X"
    assert "documento" not in r and "titular" not in r
    assert reserva_enxuta(reserva(vendida="N", leads=[]))["vendida"] is False


def _cliente_falso(monkeypatch, existentes, recentes, chamadas):
    import httpx

    class Resposta:
        def __init__(self, status, dados=None):
            self.status_code, self._dados = status, dados

        def json(self):
            return self._dados

    class Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None, params=None):
            if url.endswith(cv_crm.RESERVAS_PATH):
                return Resposta(200, {str(i): existentes[i] for i in recentes})
            idreserva = int(url.rsplit("/", 1)[1])
            chamadas.append(idreserva)
            if idreserva in existentes:
                return Resposta(200, {str(idreserva): existentes[idreserva]})
            return Resposta(400, {"error": "x", "code": 400})

    monkeypatch.setattr(httpx, "Client", Cliente)


def test_fetch_reservas_varre_todos_os_ids_e_acha_as_acima_da_listagem(monkeypatch):
    existentes = {3: reserva(), 7: reserva(vendida="N"), 12: reserva(), 13: reserva()}
    chamadas = []
    _cliente_falso(monkeypatch, existentes, recentes=[12], chamadas=chamadas)
    ex = CVCRMExtractor(api_url="https://exemplo.cvcrm.com.br", email="u@x.com", token="t")

    reservas = ex.fetch_reservas()
    assert sorted(int(r["idreserva"]) for r in reservas) == [3, 7, 12, 13]
    assert set(range(1, 14)) <= set(chamadas)  # sem base anterior: todos os IDs até o maior
    assert ex.status.mode == "real" and "3 vendida" in ex.status.message and "varredura completa" in ex.status.message


def test_fetch_reservas_incremental_so_le_novas_e_as_que_podem_mudar(monkeypatch):
    existentes = {1: reserva(), 2: reserva(vendida="N"), 3: reserva(), 4: reserva(), 5: reserva()}
    chamadas = []
    _cliente_falso(monkeypatch, existentes, recentes=[5], chamadas=chamadas)
    anteriores = [
        {"idreserva": "1", "vendida": True, "data": "2019-01-01"},   # vendida e antiga: não relê
        {"idreserva": "2", "vendida": False, "data": "2019-01-01"},  # não vendida: relê
        {"idreserva": "3", "vendida": True, "data": "2019-01-01"},
        {"idreserva": "4", "vendida": True, "data": "2019-01-01"},
    ]
    ex = CVCRMExtractor(api_url="https://exemplo.cvcrm.com.br", email="u@x.com", token="t")
    reservas = ex.fetch_reservas(anteriores)
    lidas = set(chamadas)
    assert 1 not in lidas and 3 not in lidas and {2, 5} <= lidas
    assert sorted(int(r["idreserva"]) for r in reservas) == [1, 2, 3, 4, 5]
