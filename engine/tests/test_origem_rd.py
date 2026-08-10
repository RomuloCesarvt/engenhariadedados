"""
Testes da origem descoberta na RD Station para os leads que chegam sem origem no CV.
"""

import base64
import json
from urllib.parse import quote

import pytest

from engine import origem_rd
from engine.taxonomy import classificar_lead_cv


def conversao(identificador, data="2026-05-10T10:00:00", traffic_source=None):
    return {"identificador": identificador, "data": data, "traffic_source": traffic_source}


def encoded(url):
    dados = {"first_session": {"value": quote(url)}}
    return "encoded_" + base64.b64encode(json.dumps(dados).encode()).decode().rstrip("=")


def test_formulario_do_site_vira_lead_online():
    r = origem_rd.classificar_conversoes([conversao("form-contato-lp-avare")], "ana@exemplo.com", set())
    assert (r["categoria"], r["canal"], r["online"]) == ("Site / landing page (formulário)", "site", True)
    assert "form-contato-lp-avare" in r["detalhe"]


def test_email_conhecido_da_meta_vira_campanha_paga():
    r = origem_rd.classificar_conversoes([conversao("cadastro-geral")], "ana@exemplo.com", {"ana@exemplo.com"})
    assert (r["categoria"], r["canal"], r["online"]) == ("Campanha paga (Meta/Google)", "meta", True)
    assert "formulário de anúncio" in r["detalhe"]


def test_url_da_primeira_sessao_com_gclid_vira_google():
    eventos = [conversao("cadastro-geral", traffic_source=encoded("https://site.com/lp?gclid=abc123"))]
    r = origem_rd.classificar_conversoes(eventos, None, set())
    assert (r["categoria"], r["canal"], r["online"]) == ("Campanha paga (Meta/Google)", "google", True)


def test_url_da_primeira_sessao_com_utm_paga_da_meta():
    eventos = [conversao("cadastro-geral",
                         traffic_source=encoded("https://site.com/lp?utm_source=facebook&utm_medium=cpc"))]
    r = origem_rd.classificar_conversoes(eventos, None, set())
    assert r["canal"] == "meta"


def test_disparo_de_whatsapp_e_lista_nao_sao_online():
    whats = origem_rd.classificar_conversoes([conversao("disparo-whatsapp-setembro")], None, set())
    lista = origem_rd.classificar_conversoes([conversao("base clientes ativos")], None, set())
    assert (whats["online"], whats["canal"]) == (False, "campanha_ativacao")
    assert (lista["online"], lista["canal"]) == (False, "campanha_ativacao")


def test_so_a_assistente_virtual_nao_diz_a_origem():
    r = origem_rd.classificar_conversoes([conversao("M.I.A - atendimento")], None, set())
    assert (r["categoria"], r["canal"]) == ("Sem origem (nem na RD)", None)


def test_conversao_desconhecida_fica_para_confirmar_sem_mudar_o_canal():
    r = origem_rd.classificar_conversoes([conversao("evento-stand-shopping")], None, set())
    assert (r["categoria"], r["canal"], r["online"]) == ("Outra conversão na RD (confirmar)", None, False)


def test_a_primeira_conversao_e_a_que_vale():
    eventos = [conversao("form-lp-avare", data="2026-05-10T10:00:00"),
               conversao("base clientes ativos", data="2026-01-02T10:00:00")]
    r = origem_rd.classificar_conversoes(eventos, None, set())
    assert r["identificador"] == "base clientes ativos"


@pytest.fixture
def origem_fake(monkeypatch):
    def definir(mapa):
        monkeypatch.setattr(origem_rd, "por_lead", lambda: mapa)

    return definir


def test_aplicar_troca_sem_origem_pela_origem_da_rd(origem_fake):
    origem_fake({"7": {"categoria": "Site / landing page (formulário)", "canal": "site", "online": True,
                       "detalhe": "1ª conversão na RD: form-lp em 2026-05-10"}})
    lead = {"idlead": "7", "nome": "Ana", "midia_principal": None, "origem": None}
    antes = classificar_lead_cv(lead)
    depois = origem_rd.aplicar(antes, lead["idlead"])
    assert antes.canal == "nao_rastreado" and not antes.online
    assert (depois.canal, depois.online) == ("site", True)
    assert depois.evidencia.startswith("Origem descoberta na RD Station")


def test_aplicar_nao_mexe_em_lead_que_ja_tem_origem_no_cv(origem_fake):
    origem_fake({"7": {"categoria": "Site / landing page (formulário)", "canal": "site", "online": True,
                       "detalhe": "..."}})
    lead = {"idlead": "7", "midia_principal": "Facebook Ads"}
    c = classificar_lead_cv(lead)
    assert origem_rd.aplicar(c, lead["idlead"]) is c


def test_contato_que_a_rd_nunca_devolve_sai_da_fila_depois_de_algumas_tentativas():
    consultados = {"1": {"erro": "HTTP 404", "tentativas": 1}, "2": {"erro": "HTTP 404", "tentativas": 3},
                   "3": {"categoria": "Site / landing page (formulário)", "canal": "site"}}
    assert origem_rd._na_fila("novo", consultados) is True
    assert origem_rd._na_fila("1", consultados) is True
    assert origem_rd._na_fila("2", consultados) is False
    assert origem_rd._na_fila("3", consultados) is False


def test_aplicar_nao_inventa_origem_quando_a_rd_tambem_nao_sabe(origem_fake):
    origem_fake({"7": {"categoria": "Sem origem (nem na RD)", "canal": None, "online": False, "detalhe": "..."}})
    c = classificar_lead_cv({"idlead": "7"})
    assert origem_rd.aplicar(c, "7").canal == "nao_rastreado"
