"""
Testes do cruzamento da base de Vendas contra a base de Leads.

Cenário-guia: o relatório comercial diz "5 vendas, 3 online".
O auditor precisa provar, cliente a cliente, se esses 3 existem mesmo.
"""

from datetime import datetime, timezone, timedelta

from engine.config import LeadRecord, CVLeadRecord, OriginChannel, SaleVerdict, MatchKey, HealthStatus
from engine.normalizer import (
    normalize_sale,
    classify_declared_origin,
    clean_document,
    normalize_name,
    match_empreendimento,
    EMPREENDIMENTO_DESCONHECIDO,
)
from engine.sales_auditor import SalesAuditor


SALE_DAY = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def make_lead(
    lead_id,
    channel,
    email=None,
    phone=None,
    days_before=5,
    integration_id=None,
    raw=None,
    empreendimento=None,
    campanha=None,
):
    return LeadRecord(
        source_lead_id=lead_id,
        email=email,
        email_clean=email,
        phone=phone,
        phone_clean=phone,
        origin_channel=channel,
        created_at=SALE_DAY - timedelta(days=days_before),
        integration_id=integration_id,
        empreendimento=empreendimento,
        campaign_name=campanha,
        raw_payload=raw or {},
    )


def make_sale(
    sale_id,
    origem,
    email=None,
    phone=None,
    cpf=None,
    nome=None,
    days_after_lead=0,
    empreendimento=None,
):
    return normalize_sale(
        {
            "id": sale_id,
            "nome_cliente": nome,
            "email": email,
            "telefone": phone,
            "cpf": cpf,
            "origem": origem,
            "empreendimento": empreendimento,
            "data_venda": (SALE_DAY + timedelta(days=days_after_lead)).strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------


def test_classificacao_da_origem_declarada():
    assert classify_declared_origin("Facebook Ads") is True
    assert classify_declared_origin("Google Ads") is True
    assert classify_declared_origin("Mídia Online") is True
    assert classify_declared_origin("Estande de Vendas") is False
    assert classify_declared_origin("Corretor Parceiro") is False
    assert classify_declared_origin("Feirão Imobiliário") is False
    assert classify_declared_origin(None) is False


def test_limpeza_de_documento_e_nome():
    assert clean_document("123.456.789-01") == "12345678901"
    assert clean_document("12.345.678/0001-95") == "12345678000195"
    assert clean_document("123") is None
    assert normalize_name("Patrícia  Rocha!") == "patricia rocha"
    # Nome com uma única palavra é ambíguo demais para servir de chave
    assert normalize_name("Patricia") is None


# ---------------------------------------------------------------------------
# Cenário principal: 5 vendas, 3 declaradas online
# ---------------------------------------------------------------------------


def test_cenario_5_vendas_3_declaradas_online():
    leads = [
        make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", days_before=6),
        make_lead("gads_1", OriginChannel.GOOGLE_ADS, email="b@x.com", days_before=4),
        make_lead("rd_1", OriginChannel.RD_STATION, email="e@x.com", days_before=9),
        make_lead("bi_1", OriginChannel.SHEETS_BI, email="d@x.com", days_before=2),
    ]
    sales = [
        make_sale("v1", "Facebook Ads", email="a@x.com"),        # online comprovado
        make_sale("v2", "Google Ads", email="b@x.com"),          # online comprovado
        make_sale("v3", "Facebook Ads", email="c@x.com"),        # online SEM lead -> inflado
        make_sale("v4", "Estande de Vendas", email="d@x.com"),   # offline coerente
        make_sale("v5", "Estande de Vendas", email="e@x.com"),   # online não declarado
    ]

    report = SalesAuditor(sales, leads, []).audit("2026-08-01", "2026-08-15")

    assert report.total_sales == 5
    assert report.declared_online == 3
    assert report.verified_online == 3  # v1, v2 e v5

    verdicts = {s.sale_id: s.verdict for s in report.sales}
    assert verdicts["v1"] == SaleVerdict.ONLINE_CONFIRMED
    assert verdicts["v2"] == SaleVerdict.ONLINE_CONFIRMED
    assert verdicts["v3"] == SaleVerdict.ONLINE_UNPROVEN
    assert verdicts["v4"] == SaleVerdict.OFFLINE_CONFIRMED
    assert verdicts["v5"] == SaleVerdict.ONLINE_NOT_DECLARED

    # O total bate, mas a composição não: 2 de 5 vendas estão mal atribuídas
    assert report.online_delta == 0
    assert report.attribution_accuracy == 60.0
    assert report.health_status == HealthStatus.CRITICAL
    assert report.unmatched == 1


def test_online_inflado_reduz_o_total_comprovado():
    """Quando não há contrapartida offline, o online comprovado cai abaixo do declarado."""
    leads = [make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com")]
    sales = [
        make_sale("v1", "Facebook Ads", email="a@x.com"),
        make_sale("v2", "Facebook Ads", email="fantasma@x.com"),
        make_sale("v3", "Instagram", email="fantasma2@x.com"),
    ]

    report = SalesAuditor(sales, leads, []).audit("2026-08-01", "2026-08-15")

    assert report.declared_online == 3
    assert report.verified_online == 1
    assert report.online_delta == -2
    assert report.online_unproven == 2


# ---------------------------------------------------------------------------
# Chaves de match
# ---------------------------------------------------------------------------


def test_cpf_tem_prioridade_sobre_as_demais_chaves():
    lead = make_lead(
        "meta_1", OriginChannel.META_ADS, email="outro@x.com", raw={"cpf": "123.456.789-01"}
    )
    sale = make_sale("v1", "Facebook Ads", cpf="12345678901", email="nao_existe@x.com")

    report = SalesAuditor([sale], [lead], []).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].matched_by == MatchKey.DOCUMENT
    assert report.sales[0].verdict == SaleVerdict.ONLINE_CONFIRMED
    assert report.matched_by_document == 1


def test_match_por_telefone_normalizado():
    lead = make_lead("meta_1", OriginChannel.META_ADS, phone="5511988887777")
    sale = make_sale("v1", "Facebook Ads", phone="(11) 98888-7777")

    report = SalesAuditor([sale], [lead], []).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].matched_by == MatchKey.PHONE
    assert report.sales[0].verified_is_online is True


def test_match_por_nome_e_sinalizado_como_baixa_confianca():
    lead = make_lead("meta_1", OriginChannel.META_ADS, raw={"nome": "Sérgio Bastos"})
    sale = make_sale("v1", "Facebook Ads", nome="Sergio  Bastos")

    report = SalesAuditor([sale], [lead], []).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].matched_by == MatchKey.NAME
    assert report.low_confidence_matches == 1
    assert "confiança baixa" in report.sales[0].details


def test_match_por_nome_pode_ser_desligado():
    lead = make_lead("meta_1", OriginChannel.META_ADS, raw={"nome": "Sérgio Bastos"})
    sale = make_sale("v1", "Facebook Ads", nome="Sergio Bastos")

    report = SalesAuditor([sale], [lead], [], allow_name_match=False).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].matched_by == MatchKey.NONE
    assert report.sales[0].verdict == SaleVerdict.ONLINE_UNPROVEN


def test_lead_do_cv_cobre_comprador_ausente_nas_plataformas():
    cv_lead = CVLeadRecord(
        cv_id="cv_1",
        email="a@x.com",
        email_clean="a@x.com",
        origem_cv="Facebook Ads",
        created_at=SALE_DAY - timedelta(days=3),
    )
    sale = make_sale("v1", "Facebook Ads", email="a@x.com")

    report = SalesAuditor([sale], [], [cv_lead]).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].verdict == SaleVerdict.ONLINE_CONFIRMED
    assert report.sales[0].matched_channel == OriginChannel.META_ADS


# ---------------------------------------------------------------------------
# Regras temporais e de canal
# ---------------------------------------------------------------------------


def test_lead_criado_depois_da_venda_nao_comprova_origem():
    lead = make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", days_before=-10)  # 10 dias DEPOIS
    sale = make_sale("v1", "Facebook Ads", email="a@x.com")

    report = SalesAuditor([sale], [lead], []).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].verdict == SaleVerdict.LEAD_AFTER_SALE
    assert report.sales[0].verified_is_online is False
    assert report.lead_after_sale == 1


def test_lead_fora_da_janela_de_atribuicao_e_descartado():
    lead = make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", days_before=400)
    sale = make_sale("v1", "Facebook Ads", email="a@x.com")

    dentro = SalesAuditor([sale], [lead], [], attribution_window_days=500).audit("2026-08-01", "2026-08-15")
    fora = SalesAuditor([sale], [lead], [], attribution_window_days=180).audit("2026-08-01", "2026-08-15")

    assert dentro.sales[0].verdict == SaleVerdict.ONLINE_CONFIRMED
    assert fora.sales[0].verdict == SaleVerdict.ONLINE_UNPROVEN


def test_canal_errado_e_online_mas_conta_como_atribuicao_incorreta():
    lead = make_lead("gads_1", OriginChannel.GOOGLE_ADS, email="a@x.com")
    sale = make_sale("v1", "Facebook Ads", email="a@x.com")

    report = SalesAuditor([sale], [lead], []).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].verdict == SaleVerdict.CHANNEL_MISMATCH
    assert report.verified_online == 1
    assert report.channel_mismatch == 1
    assert report.attribution_accuracy == 0.0  # online certo, canal errado


def test_origem_generica_nao_acusa_canal_errado():
    """
    'Online' e 'Mídia Paga' dizem que a venda é digital, mas não nomeiam canal.
    Sem canal declarado não há divergência de canal a apontar.
    """
    lead = make_lead("gads_1", OriginChannel.GOOGLE_ADS, email="a@x.com")
    sale = make_sale("v1", "Online", email="a@x.com")

    report = SalesAuditor([sale], [lead], []).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].verdict == SaleVerdict.ONLINE_CONFIRMED
    assert report.channel_mismatch == 0


def test_prefere_lead_online_quando_ha_varios_candidatos():
    leads = [
        make_lead("bi_1", OriginChannel.SHEETS_BI, email="a@x.com", days_before=1),
        make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", days_before=20),
    ]
    sale = make_sale("v1", "Estande de Vendas", email="a@x.com")

    report = SalesAuditor(sale and [sale], leads, []).audit("2026-08-01", "2026-08-15")

    assert report.sales[0].matched_channel == OriginChannel.META_ADS
    assert report.sales[0].verdict == SaleVerdict.ONLINE_NOT_DECLARED


def test_comprador_repetido_e_sinalizado():
    lead = make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com")
    sales = [
        make_sale("v1", "Facebook Ads", email="a@x.com"),
        make_sale("v2", "Facebook Ads", email="a@x.com"),
    ]

    report = SalesAuditor(sales, [lead], []).audit("2026-08-01", "2026-08-15")

    assert report.duplicate_buyers == 2
    assert "2 vendas no período" in report.sales[0].details


def test_base_de_vendas_vazia_nao_quebra():
    report = SalesAuditor([], [], []).audit("2026-08-01", "2026-08-15")

    assert report.total_sales == 0
    assert report.attribution_accuracy == 100.0
    assert report.health_status == HealthStatus.HEALTHY
    assert report.channels == []


# ---------------------------------------------------------------------------
# Conferência por empreendimento
# ---------------------------------------------------------------------------


def test_empreendimento_e_reconhecido_no_nome_da_campanha():
    catalogo = ["Residencial Sol", "Condomínio Horizonte"]

    assert match_empreendimento("Lançamento Residencial Sol", catalogo) == "Residencial Sol"
    assert match_empreendimento("PMax - Condominio Horizonte", catalogo) == "Condomínio Horizonte"
    # Campanha genérica não identifica produto — melhor não atribuir do que atribuir errado
    assert match_empreendimento("Display Remarketing", catalogo) is None
    assert match_empreendimento("Search - Apartamentos SP", catalogo) is None


def test_cada_empreendimento_recebe_conferencia_fechada():
    """Dois produtos, números independentes: nada é somado entre obras."""
    leads = [
        make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", empreendimento="Residencial Sol"),
        make_lead("meta_2", OriginChannel.META_ADS, email="b@x.com", empreendimento="Residencial Sol"),
        make_lead("gads_1", OriginChannel.GOOGLE_ADS, email="c@x.com", empreendimento="Torre Azul"),
    ]
    sales = [
        make_sale("v1", "Facebook Ads", email="a@x.com", empreendimento="Residencial Sol"),
        make_sale("v2", "Facebook Ads", email="fantasma@x.com", empreendimento="Residencial Sol"),
        make_sale("v3", "Google Ads", email="c@x.com", empreendimento="Torre Azul"),
    ]

    report = SalesAuditor(sales, leads, []).audit("2026-08-01", "2026-08-15")

    por_nome = {e.empreendimento: e for e in report.empreendimentos}
    assert set(por_nome) == {"Residencial Sol", "Torre Azul"}

    sol = por_nome["Residencial Sol"]
    assert sol.total_leads == 2
    assert sol.total_sales == 2
    assert sol.declared_online == 2
    assert sol.verified_online == 1          # a venda fantasma não tem lead
    assert sol.online_unproven == 1
    assert sol.is_consistent is False

    torre = por_nome["Torre Azul"]
    assert torre.total_leads == 1
    assert torre.total_sales == 1
    assert torre.verified_online == 1
    assert torre.is_consistent is True


def test_filtro_restringe_vendas_mas_preserva_leads_para_match():
    """
    Filtrar por empreendimento não pode cegar o match: um comprador que entrou
    por campanha de outro produto precisa continuar sendo reconhecido.
    """
    leads = [
        make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", empreendimento="Torre Azul"),
    ]
    sales = [
        make_sale("v1", "Facebook Ads", email="a@x.com", empreendimento="Residencial Sol"),
        make_sale("v2", "Facebook Ads", email="z@x.com", empreendimento="Torre Azul"),
    ]

    report = SalesAuditor(sales, leads, [], empreendimento="Residencial Sol").audit(
        "2026-08-01", "2026-08-15"
    )

    assert report.total_sales == 1
    assert report.empreendimento_filtro == "Residencial Sol"

    venda = report.sales[0]
    assert venda.verified_is_online is True              # o lead de outro produto vale como prova
    assert venda.empreendimento_match is False
    assert venda.lead_empreendimento == "Torre Azul"
    assert report.empreendimentos[0].cross_empreendimento_sales == 1


def test_lead_do_mesmo_empreendimento_vence_o_desempate():
    leads = [
        make_lead("meta_outro", OriginChannel.META_ADS, email="a@x.com", days_before=1, empreendimento="Torre Azul"),
        make_lead("meta_certo", OriginChannel.META_ADS, email="a@x.com", days_before=30, empreendimento="Residencial Sol"),
    ]
    sale = make_sale("v1", "Facebook Ads", email="a@x.com", empreendimento="Residencial Sol")

    report = SalesAuditor([sale], leads, []).audit("2026-08-01", "2026-08-15")

    # Mesmo sendo mais antigo, o lead do produto vendido é o que explica a venda
    assert report.sales[0].matched_lead_id == "meta_certo"
    assert report.sales[0].empreendimento_match is True


def test_empreendimento_sem_venda_aparece_no_relatorio():
    """Muito lead e nenhuma venda é exatamente o buraco que precisa ser visto."""
    leads = [
        make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", empreendimento="Torre Azul"),
        make_lead("meta_2", OriginChannel.META_ADS, email="b@x.com", empreendimento="Torre Azul"),
    ]
    sales = [make_sale("v1", "Facebook Ads", email="c@x.com", empreendimento="Residencial Sol")]

    report = SalesAuditor(sales, leads, []).audit("2026-08-01", "2026-08-15")

    torre = next(e for e in report.empreendimentos if e.empreendimento == "Torre Azul")
    assert torre.total_leads == 2
    assert torre.total_sales == 0
    assert torre.is_consistent is False
    assert any("nenhuma venda" in p for p in torre.inconsistencies)


def test_venda_sem_empreendimento_cai_em_nao_identificado():
    sales = [make_sale("v1", "Facebook Ads", email="a@x.com")]

    report = SalesAuditor(sales, [], []).audit("2026-08-01", "2026-08-15")

    assert report.vendas_sem_empreendimento == 1
    grupo = report.empreendimentos[0]
    assert grupo.empreendimento == EMPREENDIMENTO_DESCONHECIDO
    assert any("sem empreendimento informado" in p for p in grupo.inconsistencies)


def test_lead_sem_empreendimento_e_contabilizado_a_parte():
    """Lead de campanha genérica não entra na contagem do produto, mas ainda prova a origem."""
    leads = [
        make_lead("meta_1", OriginChannel.META_ADS, email="a@x.com", campanha="Display Remarketing"),
    ]
    sales = [make_sale("v1", "Facebook Ads", email="a@x.com", empreendimento="Residencial Sol")]

    report = SalesAuditor(sales, leads, []).audit("2026-08-01", "2026-08-15")

    assert report.leads_sem_empreendimento == 1
    sol = report.empreendimentos[0]
    assert sol.total_leads == 0
    assert sol.verified_online == 1  # o lead segue valendo como prova de origem
    assert report.sales[0].empreendimento_match is None


def test_conversao_por_empreendimento():
    leads = [
        make_lead(f"meta_{i}", OriginChannel.META_ADS, email=f"lead{i}@x.com", empreendimento="Residencial Sol")
        for i in range(10)
    ]
    sales = [
        make_sale("v1", "Facebook Ads", email="lead0@x.com", empreendimento="Residencial Sol"),
        make_sale("v2", "Facebook Ads", email="lead1@x.com", empreendimento="Residencial Sol"),
    ]

    report = SalesAuditor(sales, leads, []).audit("2026-08-01", "2026-08-15")

    assert report.empreendimentos[0].total_leads == 10
    assert report.empreendimentos[0].conversion_rate == 20.0


def test_empreendimento_escrito_separado_na_campanha():
    from engine.normalizer import match_empreendimento
    catalogo = ["Itu - Altavista - 15300", "Avaré - Central Parque II - 13900"]
    assert match_empreendimento("[300] - Alta Vista - 22/07", catalogo) == "Itu - Altavista - 15300"
