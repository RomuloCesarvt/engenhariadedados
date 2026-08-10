"""
Testes unitários para o motor de reconciliação de leads.
"""

from datetime import datetime, timezone, timedelta
from engine.config import LeadRecord, CVLeadRecord, OriginChannel, DivergenceType, HealthStatus
from engine.reconciler import LeadReconciler


def test_reconciler_match_and_divergence():
    now = datetime.now(timezone.utc)

    # Lead 1: Match perfeito por ID de integração
    lead1 = LeadRecord(
        source_lead_id="meta_01",
        email="user1@example.com",
        email_clean="user1@example.com",
        phone="11900000001",
        phone_clean="5511900000001",
        origin_channel=OriginChannel.META_ADS,
        created_at=now - timedelta(hours=1),
        integration_id="fb_id_01",
    )

    # Lead 2: Lead perdido (MISSING_IN_CV)
    lead2 = LeadRecord(
        source_lead_id="meta_02",
        email="perdido@example.com",
        email_clean="perdido@example.com",
        phone="11900000002",
        phone_clean="5511900000002",
        origin_channel=OriginChannel.META_ADS,
        created_at=now - timedelta(hours=1),
        integration_id="fb_id_02",
    )

    # Lead 3: Lead com origem errada (ORIGIN_MISMATCH)
    lead3 = LeadRecord(
        source_lead_id="bee_01",
        email="indicado@example.com",
        email_clean="indicado@example.com",
        phone="11900000003",
        phone_clean="5511900000003",
        origin_channel=OriginChannel.BEEVIRAL,
        created_at=now - timedelta(hours=1),
        integration_id="bee_id_01",
    )

    # CV Leads
    cv1 = CVLeadRecord(
        cv_id="cv_101",
        email="user1@example.com",
        email_clean="user1@example.com",
        phone="11900000001",
        phone_clean="5511900000001",
        origem_cv="Facebook Ads",
        created_at=now - timedelta(minutes=55),
        id_externo="fb_id_01",
    )

    cv3_mismatch = CVLeadRecord(
        cv_id="cv_103",
        email="indicado@example.com",
        email_clean="indicado@example.com",
        phone="11900000003",
        phone_clean="5511900000003",
        origem_cv="Google Ads",  # Origem incorreta!
        created_at=now - timedelta(minutes=50),
        id_externo="bee_id_01",
    )

    source_leads = [lead1, lead2, lead3]
    cv_leads = [cv1, cv3_mismatch]

    reconciler = LeadReconciler(source_leads, cv_leads)
    report = reconciler.reconcile("2026-07-01", "2026-07-27")

    assert report.total_source_leads == 3
    assert report.total_cv_leads == 2
    assert report.total_reconciled_ok == 1
    assert report.total_missing_in_cv == 1
    assert report.total_origin_mismatch == 1
    assert len(report.divergences) == 2
