"""
Testes dos diagnósticos: detecção por período, situação decidida pelos dados e histórico.
"""

from datetime import date, timedelta

import pytest

from engine import diagnosticos


def linha(data, status="no_cv", confirmado=True, formulario="Form A", no_rd=False):
    return {"data": data, "formulario": formulario, "pagina": "Página", "campanha": "Campanha", "empreendimento": "Emp",
            "status": status, "confirmado": confirmado, "no_rd": no_rd, "cv_canal": None}


def semana(segunda: date, perdidos: int, chegaram: int, **kw):
    dias = [(segunda + timedelta(days=i % 5)).isoformat() for i in range(perdidos + chegaram)]
    return [linha(d, "nao_chegou", **kw) for d in dias[:perdidos]] + [linha(d, "no_cv", formulario=kw.get("formulario", "Form A")) for d in dias[perdidos:]]


def test_episodio_resolvido_quando_os_leads_voltam_a_chegar():
    s = date(2026, 6, 15)
    linhas = semana(s, 4, 4) + semana(s + timedelta(days=7), 7, 2) + semana(s + timedelta(days=14), 0, 6) + semana(s + timedelta(days=21), 1, 9)
    [ep] = diagnosticos.episodios_de_falha(linhas)
    assert (ep["inicio"], ep["perdidos"], ep["novos"]) == ("2026-06-15", 11, 17)
    # depois do episódio chegaram 6 seguidos (voltou a funcionar); a perda isolada da semana seguinte não reabre
    assert ep["resolvido"] is True and ep["perdidos_depois"] == 1
    assert "2026-06-29" <= ep["resolvido_em_dados"] <= "2026-07-03"

    # chegadas intercaladas com perdas: nunca 5 seguidas -> continua pendente
    alternado = semana(s, 4, 4) + [linha(f"2026-06-{d:02d}", "nao_chegou" if d % 2 else "no_cv") for d in range(22, 30)]
    [ep_pendente] = diagnosticos.episodios_de_falha(alternado)
    assert ep_pendente["resolvido"] is False and ep_pendente["resolvido_em_dados"] is None

    linhas_ok = semana(s, 4, 4) + semana(s + timedelta(days=7), 7, 2) + semana(s + timedelta(days=14), 0, 6)
    [ep_ok] = diagnosticos.episodios_de_falha(linhas_ok)
    assert ep_ok["resolvido"] is True and ep_ok["chegaram_depois"] == 6


def test_perda_ainda_nao_confirmada_nao_vira_episodio():
    s = date(2026, 9, 7)
    linhas = semana(s, 5, 1, confirmado=False)
    assert diagnosticos.episodios_de_falha(linhas) == []


def test_semana_sem_leads_nao_separa_o_episodio_e_perda_isolada_nao_conta():
    s = date(2026, 8, 3)
    linhas = semana(s, 3, 1) + semana(s + timedelta(days=21), 3, 0) + semana(s + timedelta(days=35), 1, 10)
    [ep] = diagnosticos.episodios_de_falha(linhas)
    assert ep["perdidos"] == 6 and ep["fim"] >= "2026-08-24"


def _item(id_, situacao="pendente", periodo=None, chave_grupo=None, manual=False):
    return diagnosticos.diagnostico(id_, "base", "atencao", situacao, "t", "o", "p", ["c"], periodo=periodo,
                                    chave_grupo=chave_grupo, resolucao_manual=manual)


def test_pendencia_que_some_vira_resolvida_com_data():
    historico = {}
    diagnosticos.consolidar([_item("base_erro:meta_leads")], historico, "2026-09-14T10:00:00+00:00")
    itens = diagnosticos.consolidar([], historico, "2026-09-14T12:00:00+00:00")
    [item] = itens
    assert item["situacao"] == "resolvido" and item["resolvido_em"] == "2026-09-14T12:00:00+00:00"
    assert item["primeira_deteccao"] == "2026-09-14T10:00:00+00:00"


def test_episodio_do_mesmo_formulario_mantem_o_registro_quando_o_periodo_cresce():
    historico = {}
    p1 = {"inicio": "2026-08-31", "fim": "2026-09-07"}
    diagnosticos.consolidar([_item("formulario_meta:F:2026-08-31", periodo=p1, chave_grupo="formulario_meta:F")], historico, "2026-09-08T00:00:00+00:00")
    p2 = {"inicio": "2026-09-01", "fim": "2026-09-14"}
    itens = diagnosticos.consolidar([_item("formulario_meta:F:2026-09-01", periodo=p2, chave_grupo="formulario_meta:F")], historico, "2026-09-14T00:00:00+00:00")
    assert [i["id"] for i in itens] == ["formulario_meta:F:2026-08-31"]
    assert itens[0]["primeira_deteccao"] == "2026-09-08T00:00:00+00:00"


def test_resolucao_manual_so_para_itens_que_os_dados_nao_comprovam(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnosticos, "HISTORICO_PATH", str(tmp_path / "hist.json"))
    historico = {}
    diagnosticos.consolidar([_item("automatico"), _item("manual", manual=True)], historico, "2026-09-14T00:00:00+00:00")
    diagnosticos._gravar_historico(historico)

    with pytest.raises(ValueError):
        diagnosticos.resolver_manual("automatico")
    registro = diagnosticos.resolver_manual("manual", "Chaves trocadas")
    assert registro["situacao"] == "resolvido" and registro["nota"] == "Chaves trocadas"

    # na próxima rodada o detector ainda o devolve como pendente, mas vale a resolução manual
    historico = diagnosticos._ler_historico()
    [manual] = [i for i in diagnosticos.consolidar([_item("manual", manual=True)], historico, "2026-09-15T00:00:00+00:00") if i["id"] == "manual"]
    assert manual["situacao"] == "resolvido" and "Chaves trocadas" in manual["situacao_motivo"]


def test_calcular_filtra_pelo_periodo_e_resume(monkeypatch, tmp_path):
    monkeypatch.setattr(diagnosticos, "HISTORICO_PATH", str(tmp_path / "hist.json"))
    monkeypatch.setattr(diagnosticos, "DETECTORES", [lambda ctx: [
        _item("setembro", periodo={"inicio": "2026-09-01", "fim": "2026-09-10"}),
        _item("julho", periodo={"inicio": "2026-07-01", "fim": "2026-07-10"}),
        _item("sem_periodo"),
    ], lambda ctx: 1 / 0])
    r = diagnosticos.calcular(date(2026, 9, 1), date(2026, 9, 14))
    ids = [i["id"] for i in r["itens"]]
    assert "setembro" in ids and "sem_periodo" in ids and "julho" not in ids
    # detector com erro vira diagnóstico, não derruba os outros
    assert any(i["id"].startswith("detector_com_erro:") for i in r["itens"])
    assert r["resumo"]["pendentes_atencao"] == 3 and r["correcoes"]
