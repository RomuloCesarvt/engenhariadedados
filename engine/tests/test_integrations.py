"""
Testes das integrações reais: formato das APIs, nomes oficiais do CV e a regra de
que dado simulado nunca se passa por real.
"""

from datetime import datetime, timedelta, timezone

from engine.config import LeadRecord, OriginChannel, SaleVerdict
from engine.extractors.beeviral import BeeViralExtractor, beeviral_item_to_raw, parse_beeviral_page
from engine.extractors.cv_crm import CVCRMExtractor, flatten_cv_lead
from engine.extractors.meta_ads import meta_lead_to_raw
from engine.extractors.google_ads import GoogleAdsExtractor, google_row_to_raw
from engine.extractors.sales import flatten_cv_reserva
from engine.normalizer import match_empreendimento, normalize_lead, normalize_sale
from engine.reconciler import LeadReconciler
from engine.sales_auditor import SalesAuditor

# Nomes no formato real devolvido por /api/cvio/empreendimento
CATALOGO_CV = [
    "Cerqueira César - Novo Horizonte - 13200",
    "Itatinga - Novo Horizonte - 16103",
    "Avaré - Central Parque - 13700",
    "Avaré - Central Parque II - 13900",
    "Avaré - Reserva Central Parque II - 14000",
    "Taguai - Jardim dos Ipês - 12400",
    "Taguai - Jardim dos Ipês II - 12800",
    "Taguaí - Jardim dos Ipês III - 17701",
    "Tatuí - Mirante dos Ramos - Comercial 14703",
    "Tatuí - Reserva dos Ramos Residencial - 14704",
]


# ---------------------------------------------------------------------------
# Catálogo oficial do CV
# ---------------------------------------------------------------------------


def test_cidade_desempata_empreendimentos_homonimos():
    assert (
        match_empreendimento("Eduardo Gonçalves | Indique e Ganhe Novo Horizonte Itatinga", CATALOGO_CV)
        == "Itatinga - Novo Horizonte - 16103"
    )
    # Sem cidade no texto, "Novo Horizonte" é ambíguo: melhor não atribuir
    assert match_empreendimento("Campanha Novo Horizonte", CATALOGO_CV) is None


def test_numeral_romano_diferencia_etapas():
    assert match_empreendimento("Central Parque II - lançamento", CATALOGO_CV) == "Avaré - Central Parque II - 13900"
    assert match_empreendimento("Central Parque", CATALOGO_CV) == "Avaré - Central Parque - 13700"
    assert match_empreendimento("Reserva Central Parque II", CATALOGO_CV) == "Avaré - Reserva Central Parque II - 14000"
    assert match_empreendimento("Jardim dos Ipês III", CATALOGO_CV) == "Taguaí - Jardim dos Ipês III - 17701"


def test_campanha_so_com_cidade_nao_atribui_produto():
    assert match_empreendimento("Indique nossos empreendimentos em Avaré e ganhe", CATALOGO_CV) is None


def test_nome_livre_vira_nome_oficial_na_auditoria():
    """Planilha diz "Jardim dos Ipês III"; o CV diz "Taguaí - Jardim dos Ipês III - 17701"."""
    venda = normalize_sale(
        {"id": "v1", "email": "a@x.com", "origem": "Indicação", "empreendimento": "Jardim dos Ipês III", "data_venda": "2026-09-10"}
    )
    report = SalesAuditor([venda], [], [], catalogo_oficial=CATALOGO_CV).audit("2026-09-01", "2026-09-14")

    assert report.empreendimentos[0].empreendimento == "Taguaí - Jardim dos Ipês III - 17701"


# ---------------------------------------------------------------------------
# Formato real das APIs
# ---------------------------------------------------------------------------

BEEVIRAL_PAYLOAD = [
    {
        "Result": [
            {
                "ID": "abc==",
                "NAME": "Cliente Teste",
                "EMAIL": "cliente@teste.com",
                "PHONE": "5514999990000",
                "CREATION": "2026-09-10T11:50:03.137",
                "CONVERT": "N",
                "STATUS": "Indicado",
                "CAMPAIGN": {"ID": "1", "NAME": "Elis | Indique e Ganhe Taguaí"},
                "COLLABORATOR": {"NAME": " Corretora X "},
                "ADDITIONAL_FIELD": [
                    {"FIELD": "37305", "VALUE": "5514999990000"},
                    {"FIELD": "Empreendimento de interesse em Taguaí", "VALUE": "Jardim dos Ipês III"},
                ],
                "ADDITIONAL_INFO": [{"FIELD": "rd_contact_uuid", "VALUE": "uuid-1"}],
            }
        ],
        "Paging": {"TOTAL": 5, "PAGE": 1, "LIMIT": 20, "RECORDS": 90},
    }
]


def test_beeviral_formato_real():
    itens, paginacao = parse_beeviral_page(BEEVIRAL_PAYLOAD)
    assert len(itens) == 1
    assert paginacao["TOTAL"] == 5

    raw = beeviral_item_to_raw(itens[0])
    lead = normalize_lead(raw, OriginChannel.BEEVIRAL)

    assert lead.email_clean == "cliente@teste.com"
    assert lead.phone_clean == "5514999990000"
    assert lead.empreendimento == "Jardim dos Ipês III"
    assert lead.campaign_name == "Elis | Indique e Ganhe Taguaí"
    assert lead.integration_id == "uuid-1"  # UUID da RD Station, mesmo valor do CV
    assert raw["corretor"] == "Corretora X"
    assert lead.created_at.year == 2026 and lead.created_at.month == 9


def test_cv_lead_aninhado_e_achatado():
    item = {
        "idlead": 55,
        "email": "a@x.com",
        "data_cad": "2026-09-01 10:00:00",
        "empreendimento": [{"idempreendimento": 5, "nome": "Taguai - Jardim dos Ipês - 12400"}],
        "midia_principal": {"nome": "Facebook"},
    }
    flat = flatten_cv_lead(item)
    assert flat["empreendimento"] == "Taguai - Jardim dos Ipês - 12400"
    assert flat["origem"] == "Facebook"


def test_meta_lead_campos_do_formulario():
    lead = {
        "id": "123",
        "created_time": "2026-09-10T12:00:00+0000",
        "campaign_name": "Leads - Central Parque II",
        "field_data": [
            {"name": "email", "values": ["x@y.com"]},
            {"name": "phone_number", "values": ["+5514999990000"]},
            {"name": "full_name", "values": ["Fulano"]},
        ],
    }
    raw = meta_lead_to_raw(lead, "Formulário Avaré")
    assert raw["email"] == "x@y.com"
    assert raw["phone"] == "+5514999990000"
    assert raw["nome"] == "Fulano"
    assert raw["campaign_name"] == "Leads - Central Parque II"


def test_google_ads_linha_do_search():
    row = {
        "leadFormSubmissionData": {
            "resourceName": "customers/1/leadFormSubmissionData/9",
            "gclid": "gclid-1",
            "submissionDateTime": "2026-09-10 12:00:00",
            "leadFormSubmissionFields": [
                {"fieldType": "EMAIL", "fieldValue": "g@x.com"},
                {"fieldType": "FIRST_NAME", "fieldValue": "Ana"},
                {"fieldType": "LAST_NAME", "fieldValue": "Lima"},
            ],
        },
        "campaign": {"name": "Search - Reserva dos Ramos"},
    }
    raw = google_row_to_raw(row)
    assert raw["email"] == "g@x.com"
    assert raw["nome"] == "Ana Lima"
    assert raw["gclid"] == "gclid-1"


def test_reserva_do_cv_cancelada_e_identificada():
    flat = flatten_cv_reserva(
        {
            "idreserva": 10,
            "titular": {"nome": "Cliente", "cpf": "123.456.789-01", "email": "c@x.com"},
            "empreendimento": {"nome": "Avaré - Central Parque - 13700"},
            "situacao": {"nome": "Cancelada"},
            "data_reserva": "2026-09-05",
        }
    )
    assert flat["empreendimento"] == "Avaré - Central Parque - 13700"
    assert flat["situacao"] == "Cancelada"
    assert flat["cpf"] == "123.456.789-01"


# ---------------------------------------------------------------------------
# Dado simulado nunca se passa por real
# ---------------------------------------------------------------------------


def test_sem_credencial_nao_devolve_simulacao(monkeypatch):
    monkeypatch.delenv("ALLOW_SIMULATED_DATA", raising=False)
    extractor = BeeViralExtractor(api_key="")
    extractor.api_key = ""

    leads = extractor.fetch_leads(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert leads == []
    assert extractor.status.mode == "nao_configurado"
    assert extractor.status.help_links  # o link para resolver acompanha o estado


def test_modo_demonstracao_marca_dados_como_simulados(monkeypatch):
    monkeypatch.setenv("ALLOW_SIMULATED_DATA", "true")
    extractor = BeeViralExtractor(api_key="")
    extractor.api_key = ""

    leads = extractor.fetch_leads(datetime(2026, 7, 1), datetime(2026, 7, 31))

    assert leads
    assert extractor.status.mode == "simulado"
    assert "SIMULADOS" in extractor.status.message


def test_cv_sem_email_explica_o_que_falta(monkeypatch):
    monkeypatch.delenv("ALLOW_SIMULATED_DATA", raising=False)
    extractor = CVCRMExtractor(api_url="https://exemplo.cvcrm.com.br", email="", token="tok")
    extractor.email = ""

    assert extractor.fetch_cv_leads(datetime(2026, 9, 1), datetime(2026, 9, 14)) == []
    assert extractor.status.mode == "erro"
    assert "CV_CRM_EMAIL" in extractor.status.action


def test_google_ads_lista_credenciais_faltando(monkeypatch):
    monkeypatch.delenv("ALLOW_SIMULATED_DATA", raising=False)
    for chave in ("GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN"):
        monkeypatch.delenv(chave, raising=False)
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")

    extractor = GoogleAdsExtractor(developer_token="dev")
    assert extractor.fetch_leads(datetime(2026, 9, 1), datetime(2026, 9, 14)) == []
    assert "GOOGLE_ADS_REFRESH_TOKEN" in extractor.status.message
    assert "GOOGLE_ADS_CUSTOMER_ID" in extractor.status.message


def test_sem_cv_nenhum_lead_e_acusado_de_perdido():
    agora = datetime.now(timezone.utc)
    lead = LeadRecord(
        source_lead_id="bee_1",
        email="a@x.com",
        email_clean="a@x.com",
        origin_channel=OriginChannel.BEEVIRAL,
        created_at=agora - timedelta(days=2),
    )

    report = LeadReconciler([lead], []).reconcile("2026-09-01", "2026-09-14", cv_available=False)

    assert report.cv_available is False
    assert report.total_missing_in_cv == 0
    assert report.divergences == []


def test_etapa_em_algarismo_equivale_ao_romano():
    catalogo = CATALOGO_CV + ["Botucatu - Reserva Central Parque - 13600"]
    assert (
        match_empreendimento("Loteamento aberto | Central Parque Avaré 2", catalogo)
        == "Avaré - Central Parque II - 13900"
    )
    # Sem o "2", "Reserva Central Parque" de Botucatu venceria; com ele, é a etapa II de Avaré
    assert (
        match_empreendimento("Loteamento fechado | Reserva Central Parque Avaré 2", catalogo)
        == "Avaré - Reserva Central Parque II - 14000"
    )
    # Código do CV continua sendo ignorado
    assert match_empreendimento("Central Parque 13700", catalogo) == "Avaré - Central Parque - 13700"


def test_resposta_generica_nao_vira_empreendimento():
    lead = normalize_lead(
        {"id": "b1", "email": "a@x.com", "created_at": "2026-09-10", "empreendimento": "Outros empreendimentos",
         "campaign_name": "Indique nossos empreendimentos em Avaré e ganhe"},
        OriginChannel.BEEVIRAL,
    )
    report = SalesAuditor([], [lead], [], catalogo_oficial=CATALOGO_CV).audit("2026-09-01", "2026-09-14")

    assert report.leads_sem_empreendimento == 1
    assert all(e.empreendimento != "Outros empreendimentos" for e in report.empreendimentos)


# ---------------------------------------------------------------------------
# Formato real da API de leads do CV (/api/cvio/lead)
# ---------------------------------------------------------------------------


def test_canal_do_cv_vem_da_midia_e_nao_da_origem():
    from engine.config import OriginChannel as OC
    from engine.normalizer import normalize_channel_alias, normalize_cv_lead

    item = {
        "idlead": 54616,
        "email": "a@x.com",
        "data_cad": "2026-09-14 08:35:22",
        "origem": "Busca Compartilhada",
        "midia_principal": "Instagram Ads",
        "midias": ["Instagram Ads"],
        "empreendimento": [{"id": 39, "nome": "Taguaí - Jardim dos Ipês III - 17701"}],
        "idrd_station": "03644cb4-uuid",
    }
    lead = normalize_cv_lead(flatten_cv_lead(item))

    assert normalize_channel_alias(lead.origem_cv) == OC.META_ADS
    assert lead.id_externo == "03644cb4-uuid"
    assert lead.empreendimento == "Taguaí - Jardim dos Ipês III - 17701"
    assert lead.cv_id == "54616"


def test_midias_em_texto_livre_viram_canal():
    from engine.config import OriginChannel as OC
    from engine.normalizer import normalize_channel_alias

    assert normalize_channel_alias("Instagram Ads") == OC.META_ADS
    assert normalize_channel_alias("ig") == OC.META_ADS
    assert normalize_channel_alias("pesquisa / cpc | altavista") == OC.GOOGLE_ADS
    assert normalize_channel_alias("Google") == OC.GOOGLE_ADS
    assert normalize_channel_alias("WhatsApp") == OC.SHEETS_BI
    assert normalize_channel_alias("Painel Corretor") == OC.SHEETS_BI


def test_cv_pagina_ate_duas_paginas_inteiras_antes_do_periodo(monkeypatch):
    import httpx
    from engine.extractors import cv_crm

    # A API não ordena estritamente pelo cadastro: o lead 6 (02/09) aparece depois de uma página antiga
    paginas = {
        0: [{"idlead": 9, "data_cad": "2026-09-14 10:00:00"}, {"idlead": 8, "data_cad": "2026-09-10 10:00:00"}],
        2: [{"idlead": 7, "data_cad": "2026-08-20 10:00:00"}, {"idlead": 5, "data_cad": "2026-08-15 10:00:00"}],
        4: [{"idlead": 6, "data_cad": "2026-09-02 10:00:00"}, {"idlead": 4, "data_cad": "2026-08-10 10:00:00"}],
        6: [{"idlead": 3, "data_cad": "2026-08-05 10:00:00"}, {"idlead": 2, "data_cad": "2026-08-01 10:00:00"}],
        8: [{"idlead": 1, "data_cad": "2026-07-20 10:00:00"}, {"idlead": 0, "data_cad": "2026-07-10 10:00:00"}],
        10: [{"idlead": -1, "data_cad": "2026-07-01 10:00:00"}, {"idlead": -2, "data_cad": "2026-06-01 10:00:00"}],
    }
    chamadas = []

    class Resposta:
        status_code = 200

        def __init__(self, dados):
            self._dados = dados

        def json(self):
            return {"codigo": 200, "total": 5, "leads": self._dados}

    class ClienteFalso:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None, params=None):
            chamadas.append(params)
            return Resposta(paginas.get(params["offset"], []))

    monkeypatch.setattr(httpx, "Client", ClienteFalso)
    monkeypatch.setattr(cv_crm, "REGISTROS_POR_PAGINA", 2)

    extractor = CVCRMExtractor(api_url="https://exemplo.cvcrm.com.br", email="u@x.com", token="t")
    leads = extractor.fetch_cv_leads(datetime(2026, 9, 1), datetime(2026, 9, 14, 23, 59))

    # só para depois de DUAS páginas inteiras anteriores a 01/09 (6 e 8)
    assert [c["offset"] for c in chamadas] == [0, 2, 4, 6, 8]
    assert sorted(lead.cv_id for lead in leads) == ["6", "8", "9"]
    assert extractor.status.mode == "real"


# ---------------------------------------------------------------------------
# Reconciliação com histórico do CV
# ---------------------------------------------------------------------------


def _cv(cv_id, email, origem, dias_atras):
    from engine.config import CVLeadRecord

    return CVLeadRecord(
        cv_id=cv_id,
        email=email,
        email_clean=email,
        origem_cv=origem,
        created_at=datetime(2026, 9, 10) - timedelta(days=dias_atras),
    )


def _bee(lead_id, email):
    return LeadRecord(
        source_lead_id=lead_id,
        email=email,
        email_clean=email,
        origin_channel=OriginChannel.BEEVIRAL,
        created_at=datetime(2026, 9, 10),
    )


def test_lead_que_ja_existia_no_cv_nao_e_perdido_nem_origem_errada():
    antigo = _cv("cv_1", "antigo@x.com", "Facebook Ads", dias_atras=250)
    recente = _cv("cv_2", "novo@x.com", "Não Definido", dias_atras=0)

    report = LeadReconciler(
        [_bee("b1", "antigo@x.com"), _bee("b2", "novo@x.com"), _bee("b3", "sumiu@x.com")],
        [antigo, recente],
        cv_period_leads=[recente],
    ).reconcile("2026-09-01", "2026-09-14")

    tipos = {d.source_lead_id: d.divergence_type.value for d in report.divergences}
    assert "b1" not in tipos                       # já era lead do CV: conciliado
    assert tipos["b2"] == "ORIGIN_MISMATCH"        # indicação registrada como "Não Definido"
    assert tipos["b3"] == "MISSING_IN_CV"          # não existe no CV
    assert report.total_reconciled_ok == 1
    assert report.total_cv_leads == 1              # contagem só do período


def test_chave_de_api_da_rd_explica_que_nao_le_contatos(monkeypatch):
    """A 'Chave de API' do painel da RD só envia conversões: o erro precisa dizer isso, não 'token expirado'."""
    import httpx
    from engine.extractors.rd_station import RDStationExtractor

    class Resposta401:
        status_code = 401
        text = '{"error":"invalid_token"}'

    class ClienteFalso:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return Resposta401()

    monkeypatch.delenv("ALLOW_SIMULATED_DATA", raising=False)
    for chave in ("RD_STATION_CLIENT_ID", "RD_STATION_CLIENT_SECRET", "RD_STATION_REFRESH_TOKEN", "RD_STATION_SEGMENTATION_ID"):
        monkeypatch.delenv(chave, raising=False)
    monkeypatch.setattr(httpx, "Client", ClienteFalso)

    extractor = RDStationExtractor(api_token="chave-do-painel")
    assert extractor.fetch_leads(datetime(2026, 9, 1), datetime(2026, 9, 14)) == []
    assert extractor.status.mode == "erro"
    assert "só envia conversões" in extractor.status.message
    assert "rd_oauth.py" in extractor.status.action


def test_conta_de_anuncio_sem_o_codigo_do_cv_e_atribuida():
    """A conta "Mirante dos Ramos" cai no empreendimento unificado "Reserva dos Ramos Residencial"."""
    catalogo = CATALOGO_CV
    assert match_empreendimento("Mirante dos Ramos", catalogo) == "Tatuí - Reserva dos Ramos Residencial - 14704"
    assert match_empreendimento("Reserva dos Ramos Tatuí", catalogo) == "Tatuí - Reserva dos Ramos Residencial - 14704"
    assert match_empreendimento("ML - Central Parque Avaré 2", catalogo) == "Avaré - Central Parque II - 13900"
