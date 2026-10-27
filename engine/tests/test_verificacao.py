"""
Testes da verificação ao vivo de leads no CV e no RD Station (sem chamar as APIs).
"""

from engine import verificacao


def test_telefone_vira_ddd_mais_numero_com_e_sem_nono_digito():
    assert verificacao.variantes_telefone("+55 14 99638-2351") == ["14996382351", "1496382351"]
    assert verificacao.variantes_telefone("015998393926") == ["15998393926", "1598393926"]
    assert verificacao.variantes_telefone("(14) 3732-1234") == ["1437321234", "14937321234"]
    assert verificacao.variantes_telefone("123") == []


def test_links_do_rd_e_do_cv(monkeypatch):
    monkeypatch.setenv("CV_CRM_URL", "https://mouraleite.cvcrm.com.br/")
    assert verificacao.cv_busca_url() == "https://mouraleite.cvcrm.com.br/gestor/comercial/leads"
    assert verificacao.rd_perfil_url("abc") == "https://app.rdstation.com.br/leads/public/abc"
    assert verificacao.rd_perfil_url(None) is None


def test_sem_email_nao_consulta_o_rd(monkeypatch):
    monkeypatch.setenv("RD_STATION_CLIENT_ID", "x")
    monkeypatch.setenv("RD_STATION_CLIENT_SECRET", "y")
    monkeypatch.setenv("RD_STATION_REFRESH_TOKEN", "z")
    r = verificacao.verificar_no_rd(None)
    assert r["consultado"] is False and "e-mail" in r["erro"]


def test_so_conta_como_encontrado_quando_email_ou_telefone_batem():
    assert verificacao.mesma_pessoa({"email": "A@x.com", "telefone": None}, "a@x.com", None)
    assert verificacao.mesma_pessoa({"email": "b@x.com", "telefone": "+55 (14) 99638-2351"}, None, "14996382351")
    assert not verificacao.mesma_pessoa({"email": "b@x.com", "telefone": "1432221111"}, "a@x.com", "14996382351")


def test_cache_nao_encontrado_expira_e_encontrado_vale_sempre(monkeypatch, tmp_path):
    monkeypatch.setattr(verificacao, "CACHE_PATH", str(tmp_path / "cache.json"))
    verificacao._cache.update(mtime=None, dados={})
    antigo = "2026-01-01T00:00:00+00:00"
    verificacao._gravar_no_cache(verificacao.chave_verificacao("nao@x.com", None),
                                 {"verificado_em": antigo, "cv": {"consultado": True, "encontrado": False}})
    verificacao._gravar_no_cache(verificacao.chave_verificacao("sim@x.com", None),
                                 {"verificado_em": antigo, "cv": {"consultado": True, "encontrado": True, "leads": [{}]}})
    assert verificacao.resultado_valido("nao@x.com", None) is None
    assert verificacao.resultado_valido("sim@x.com", None)["cv"]["encontrado"] is True


class _Resposta:
    def __init__(self, status, corpo):
        self.status_code, self._corpo = status, corpo

    def json(self):
        return self._corpo


def _cliente_cv(monkeypatch, respostas):
    """Cliente HTTP falso: devolve a resposta conforme o filtro usado (email ou telefone)."""
    class Cliente:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None, params=None):
            chave = params.get("email") or params.get("telefone")
            return respostas.get(chave, _Resposta(400, {"codigo": 400, "mensagem": "Lead não encontrado"}))

    monkeypatch.setattr(verificacao.httpx, "Client", Cliente)
    monkeypatch.setenv("CV_CRM_URL", "https://exemplo.cvcrm.com.br")
    monkeypatch.setenv("CV_CRM_TOKEN", "t")
    monkeypatch.setenv("CV_CRM_EMAIL", "u@x.com")


def test_cv_400_lead_nao_encontrado_e_consulta_valida_sem_resultado(monkeypatch):
    _cliente_cv(monkeypatch, {})
    r = verificacao.verificar_no_cv("sumiu@x.com", "+55 14 99638-2351")
    assert r["consultado"] is True and r["encontrado"] is False and r["erros"] == []
    assert [c["encontrados"] for c in r["consultas"]] == [0, 0, 0]


def test_cv_outro_erro_nao_conclui_que_o_lead_nao_existe(monkeypatch):
    _cliente_cv(monkeypatch, {"sumiu@x.com": _Resposta(500, {"mensagem": "erro interno"})})
    r = verificacao.verificar_no_cv("sumiu@x.com", None)
    assert r["consultado"] is False and r["erros"]


def test_cv_encontra_a_mesma_pessoa_e_descarta_outra(monkeypatch):
    lead = {"idlead": 9, "email": "achou@x.com", "telefone": None, "data_cad": "2021-05-01 10:00:00",
            "situacao": {"nome": "Cancelado"}, "link_interesses": "https://cv/9"}
    outro = {"idlead": 10, "email": "outra@x.com", "telefone": "1432221111"}
    _cliente_cv(monkeypatch, {"achou@x.com": _Resposta(200, {"total": 2, "leads": [lead, outro]})})
    r = verificacao.verificar_no_cv("achou@x.com", None)
    assert r["encontrado"] is True and [l["idlead"] for l in r["leads"]] == [9]
    assert r["leads"][0]["situacao"] == "Cancelado"
