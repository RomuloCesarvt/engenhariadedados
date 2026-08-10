"""
Testes da taxonomia de origem com os padrões reais encontrados na base do CV.
"""

from engine.taxonomy import classificar_lead_cv


def utm(**campos):
    return [{"slug": f"cf_utm_{k}", "valor": v} for k, v in campos.items()]


def test_utm_da_meta_vence_a_midia_whatsapp():
    """785 leads chegam como WhatsApp, mas a UTM mostra que vieram de anúncio da Meta."""
    c = classificar_lead_cv({
        "midia_principal": "WhatsApp",
        "campos_adicionais": utm(source="meta ads", medium="ig", campaign="avare-2-central_meta-gdc_always-on"),
    })
    assert c.canal == "meta"
    assert c.grupo == "online_pago"
    assert c.confianca == "alta"
    assert c.campanha == "avare-2-central_meta-gdc_always-on"


def test_utm_do_google_em_lead_de_whatsapp():
    c = classificar_lead_cv({
        "midia_principal": "WhatsApp",
        "campos_adicionais": utm(source="google", medium="cpc", campaign="novo-horizonte_google-search_keywords-mercado"),
    })
    assert c.canal == "google" and c.online and c.confianca == "alta"


def test_whatsapp_organico_e_whatsapp_sem_rastreio_nao_se_misturam():
    organico = classificar_lead_cv({"midia_principal": "WhatsApp", "tags": [{"nome": "mia-organico"}]})
    sem_rastro = classificar_lead_cv({"midia_principal": "WhatsApp", "tags": [{"nome": "mia-transferido"}]})

    assert organico.canal == "whatsapp_organico" and organico.online
    assert sem_rastro.canal == "whatsapp_nao_rastreado"
    # WhatsApp é canal digital: conta como online, mas separado do orgânico confirmado pela tag
    assert sem_rastro.online is True and sem_rastro.confianca == "nenhuma"


def test_variacoes_de_nome_da_meta_viram_um_canal_so():
    for midia in ("Facebook Ads", "Facebook", "meta_ads", "meta", "Instagram Ads", "Instagram", "ig", "Click To WhatsApp"):
        c = classificar_lead_cv({"midia_principal": midia})
        assert c.canal == "meta", midia
        assert c.confianca == "media"


def test_cadastros_comerciais_sao_offline():
    for midia in ("Painel Corretor", "Painel Imobiliária", "Painel PDV", "Painel Gestor", "Atendimento ao cliente"):
        c = classificar_lead_cv({"midia_principal": midia})
        assert c.grupo == "offline", midia


def test_indicacao_pela_beeviral_detectada_nos_campos_do_cv():
    c = classificar_lead_cv({
        "campos_adicionais": [{"slug": "cf_nome_da_pessoa_que_indicou", "valor": "Fulano"}],
        "midia_principal": None,
    })
    assert c.canal == "beeviral" and c.grupo == "indicacao_digital"


def test_sites_e_dominios_sao_online_organico():
    for midia in ("reservadosramos.com.br", "https://www.google.com/", "Tráfego Direto", "linktr.ee", "Referência: www.mouraleite.com.br"):
        c = classificar_lead_cv({"midia_principal": midia})
        assert c.canal == "site", midia
        assert c.grupo == "online_organico"


def test_valor_null_na_utm_e_ignorado():
    c = classificar_lead_cv({"campos_adicionais": utm(source="null", medium="null"), "midia_principal": "Painel Corretor"})
    assert c.canal == "comercial"


def test_sem_nenhuma_evidencia_fica_nao_rastreado_com_motivo():
    c = classificar_lead_cv({"midia_principal": None, "origem": "Não Definido"})
    assert c.canal == "nao_rastreado"
    assert c.confianca == "nenhuma"
    assert "Não Definido" in c.evidencia
