"""
Motor Principal de Reconciliação e Validação Híbrida de Leads.
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, timezone
import uuid

from engine.config import (
    LeadRecord,
    CVLeadRecord,
    OriginChannel,
    DivergenceType,
    DivergenceRecord,
    ChannelSummary,
    GlobalReconciliationReport,
    HealthStatus,
)
from engine.normalizer import normalize_channel_alias


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class LeadReconciler:
    def __init__(self, source_leads: List[LeadRecord], cv_leads: List[CVLeadRecord]):
        self.source_leads = source_leads
        self.cv_leads = cv_leads

        # Índices para rápida busca O(1)
        self.cv_by_ext_id: Dict[str, CVLeadRecord] = {}
        self.cv_by_email: Dict[str, CVLeadRecord] = {}
        self.cv_by_phone: Dict[str, CVLeadRecord] = {}

        self._build_cv_indices()

    def _build_cv_indices(self):
        for cv in self.cv_leads:
            if cv.id_externo:
                self.cv_by_ext_id[cv.id_externo] = cv
            if cv.email_clean:
                self.cv_by_email[cv.email_clean] = cv
            if cv.phone_clean:
                self.cv_by_phone[cv.phone_clean] = cv

    def _find_matching_cv_lead(self, lead: LeadRecord) -> Optional[CVLeadRecord]:
        # 1. Tenta Match por ID de Integração Nativo (gclid, fbclid, bee_id, rd_id)
        if lead.integration_id and lead.integration_id in self.cv_by_ext_id:
            return self.cv_by_ext_id[lead.integration_id]

        # 2. Fallback: Match por E-mail Sanitizado
        if lead.email_clean and lead.email_clean in self.cv_by_email:
            return self.cv_by_email[lead.email_clean]

        # 3. Fallback: Match por Telefone Sanitizado
        if lead.phone_clean and lead.phone_clean in self.cv_by_phone:
            return self.cv_by_phone[lead.phone_clean]

        return None

    def reconcile(self, start_date: str, end_date: str) -> GlobalReconciliationReport:
        now = datetime.now(timezone.utc)
        divergences: List[DivergenceRecord] = []

        # Contadores por Canal
        channel_stats: Dict[OriginChannel, Dict[str, int]] = {
            ch: {
                "source": 0,
                "cv": 0,
                "match_ok": 0,
                "missing": 0,
                "mismatch": 0,
                "latency": 0,
                "pending": 0,
            }
            for ch in OriginChannel
            if ch != OriginChannel.CV_CRM
        }

        # Contagem de leads no CV por origem
        for cv in self.cv_leads:
            ch_alias = normalize_channel_alias(cv.origem_cv)
            if ch_alias in channel_stats:
                channel_stats[ch_alias]["cv"] += 1

        total_source = len(self.source_leads)
        total_cv = len(self.cv_leads)
        total_match_ok = 0
        total_missing = 0
        total_mismatch = 0

        for lead in self.source_leads:
            ch = lead.origin_channel
            if ch not in channel_stats:
                continue

            channel_stats[ch]["source"] += 1
            matched_cv = self._find_matching_cv_lead(lead)

            if matched_cv:
                # Lead Encontrado no CV -> Validar Atribuição e Latência
                cv_ch_alias = normalize_channel_alias(matched_cv.origem_cv)

                # Validação de Mídia/Origem
                is_origin_correct = (cv_ch_alias == ch) or (
                    ch == OriginChannel.BEEVIRAL and "beeviral" in matched_cv.origem_cv.lower()
                )

                # Validação de Latência (ex: > 2 horas entre conversão e entrada no CV)
                time_diff_seconds = (ensure_utc(matched_cv.created_at) - ensure_utc(lead.created_at)).total_seconds()
                is_delayed = time_diff_seconds > 7200

                if not is_origin_correct:
                    channel_stats[ch]["mismatch"] += 1
                    total_mismatch += 1
                    divergences.append(
                        DivergenceRecord(
                            id=f"div_{uuid.uuid4().hex[:8]}",
                            source_lead_id=lead.source_lead_id,
                            email=lead.email_clean or lead.email,
                            phone=lead.phone_clean or lead.phone,
                            origin_channel=ch,
                            divergence_type=DivergenceType.ORIGIN_MISMATCH,
                            severity="MEDIUM",
                            details=f"Lead capturado no {ch.value.upper()}, mas registrado no CV como '{matched_cv.origem_cv}'.",
                            source_created_at=lead.created_at.isoformat(),
                            cv_created_at=matched_cv.created_at.isoformat(),
                            origem_no_cv=matched_cv.origem_cv,
                            integration_id=lead.integration_id,
                        )
                    )
                elif is_delayed:
                    channel_stats[ch]["latency"] += 1
                    channel_stats[ch]["match_ok"] += 1
                    total_match_ok += 1
                    divergences.append(
                        DivergenceRecord(
                            id=f"div_{uuid.uuid4().hex[:8]}",
                            source_lead_id=lead.source_lead_id,
                            email=lead.email_clean or lead.email,
                            phone=lead.phone_clean or lead.phone,
                            origin_channel=ch,
                            divergence_type=DivergenceType.LATENCY_DELAY,
                            severity="LOW",
                            details=f"Lead integrado com atraso de {int(time_diff_seconds / 3600)}h no CV.",
                            source_created_at=lead.created_at.isoformat(),
                            cv_created_at=matched_cv.created_at.isoformat(),
                            origem_no_cv=matched_cv.origem_cv,
                            integration_id=lead.integration_id,
                        )
                    )
                else:
                    channel_stats[ch]["match_ok"] += 1
                    total_match_ok += 1
            else:
                # Lead Ausente no CV
                lead_age_seconds = (ensure_utc(now) - ensure_utc(lead.created_at)).total_seconds()

                if lead_age_seconds < 900:  # < 15 minutos -> PENDING_SYNC
                    channel_stats[ch]["pending"] += 1
                else:  # MISSING_IN_CV
                    channel_stats[ch]["missing"] += 1
                    total_missing += 1
                    divergences.append(
                        DivergenceRecord(
                            id=f"div_{uuid.uuid4().hex[:8]}",
                            source_lead_id=lead.source_lead_id,
                            email=lead.email_clean or lead.email,
                            phone=lead.phone_clean or lead.phone,
                            origin_channel=ch,
                            divergence_type=DivergenceType.MISSING_IN_CV,
                            severity="HIGH",
                            details=f"Lead gerado na plataforma {ch.value.upper()} ausente no CRM Construtor de Vendas.",
                            source_created_at=lead.created_at.isoformat(),
                            integration_id=lead.integration_id,
                        )
                    )

        # Construção dos Resumos por Canal
        channel_summaries: List[ChannelSummary] = []
        for ch, stats in channel_stats.items():
            src_cnt = stats["source"]
            ok_cnt = stats["match_ok"]
            adh_rate = round((ok_cnt / src_cnt * 100), 1) if src_cnt > 0 else 100.0

            if adh_rate >= 98.0:
                health = HealthStatus.HEALTHY
            elif adh_rate >= 93.0:
                health = HealthStatus.WARNING
            else:
                health = HealthStatus.CRITICAL

            channel_summaries.append(
                ChannelSummary(
                    channel=ch,
                    total_source_leads=src_cnt,
                    total_cv_leads=stats["cv"],
                    match_ok_count=ok_cnt,
                    missing_in_cv_count=stats["missing"],
                    origin_mismatch_count=stats["mismatch"],
                    latency_delay_count=stats["latency"],
                    pending_sync_count=stats["pending"],
                    adherence_rate=adh_rate,
                    health_status=health,
                )
            )

        overall_adh = round((total_match_ok / total_source * 100), 1) if total_source > 0 else 100.0
        if overall_adh >= 98.0:
            overall_health = HealthStatus.HEALTHY
        elif overall_adh >= 93.0:
            overall_health = HealthStatus.WARNING
        else:
            overall_health = HealthStatus.CRITICAL

        execution_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return GlobalReconciliationReport(
            execution_id=execution_id,
            timestamp=now.isoformat(),
            start_date=start_date,
            end_date=end_date,
            total_source_leads=total_source,
            total_cv_leads=total_cv,
            total_reconciled_ok=total_match_ok,
            total_missing_in_cv=total_missing,
            total_origin_mismatch=total_mismatch,
            overall_adherence_rate=overall_adh,
            overall_health=overall_health,
            channels=channel_summaries,
            divergences=divergences,
        )
