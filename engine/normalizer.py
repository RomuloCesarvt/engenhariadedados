"""
Módulo de Normalização e Sanitização de Leads (E-mails, Telefones, Datas e Taxonomia).
"""

import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from engine.config import OriginChannel, LeadRecord, CVLeadRecord


def clean_email(email: Optional[str]) -> Optional[str]:
    if not email or not isinstance(email, str):
        return None
    email_clean = email.strip().lower()
    # Validação simples de sintaxe de email
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_clean):
        return email_clean
    return None


def clean_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    # Extrai apenas dígitos
    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return None
    # Se tiver 10 ou 11 dígitos (BR sem DDI), adiciona 55
    if len(digits) in (10, 11):
        return f"55{digits}"
    # Se já tiver 12 ou 13 dígitos começando com 55
    if len(digits) in (12, 13) and digits.startswith("55"):
        return digits
    return digits


def normalize_channel_alias(channel_raw: str) -> OriginChannel:
    ch = str(channel_raw).strip().lower().replace(" ", "_")
    if ch in ["meta", "facebook", "instagram", "fb", "meta_ads", "facebook_ads"]:
        return OriginChannel.META_ADS
    elif ch in ["google", "google_ads", "gads", "adwords"]:
        return OriginChannel.GOOGLE_ADS
    elif ch in ["rd", "rd_station", "rdstation", "rd_marketing"]:
        return OriginChannel.RD_STATION
    elif ch in ["beeviral", "bee", "indicação", "indicacao"]:
        return OriginChannel.BEEVIRAL
    elif ch in ["sheets", "planilha", "bi", "bi_interno", "excel", "estande_vendas", "feirão_imobiliário"]:
        return OriginChannel.SHEETS_BI
    elif ch in ["cv", "cv_crm", "construtor_de_vendas"]:
        return OriginChannel.CV_CRM
    return OriginChannel.SHEETS_BI


def parse_datetime(dt_val: Any) -> datetime:
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, str):
        try:
            # Tenta ISO 8601
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            pass
        # Tenta formatos comuns no Brasil
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(dt_val, fmt)
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def normalize_lead(raw_dict: Dict[str, Any], channel: OriginChannel) -> LeadRecord:
    email_raw = raw_dict.get("email") or raw_dict.get("e-mail") or raw_dict.get("user_email")
    phone_raw = raw_dict.get("phone") or raw_dict.get("telefone") or raw_dict.get("celular") or raw_dict.get("whatsapp")
    lead_id = str(raw_dict.get("id") or raw_dict.get("lead_id") or raw_dict.get("conversion_id") or f"gen_{hash(str(raw_dict))}")

    created_at_raw = raw_dict.get("created_at") or raw_dict.get("created_time") or raw_dict.get("data_cadastro")
    
    integration_id = (
        raw_dict.get("gclid")
        or raw_dict.get("fbclid")
        or raw_dict.get("bee_id")
        or raw_dict.get("rd_id")
        or raw_dict.get("integration_id")
    )

    return LeadRecord(
        source_lead_id=lead_id,
        email=email_raw,
        email_clean=clean_email(email_raw),
        phone=phone_raw,
        phone_clean=clean_phone(phone_raw),
        origin_channel=channel,
        campaign_name=raw_dict.get("campaign_name") or raw_dict.get("campanha"),
        created_at=parse_datetime(created_at_raw),
        utm_source=raw_dict.get("utm_source"),
        utm_medium=raw_dict.get("utm_medium"),
        utm_campaign=raw_dict.get("utm_campaign"),
        integration_id=str(integration_id) if integration_id else None,
        raw_payload=raw_dict,
    )


def normalize_cv_lead(raw_dict: Dict[str, Any]) -> CVLeadRecord:
    email_raw = raw_dict.get("email") or raw_dict.get("e-mail")
    phone_raw = raw_dict.get("telefone") or raw_dict.get("celular") or raw_dict.get("phone")
    cv_id = str(raw_dict.get("id") or raw_dict.get("id_lead") or raw_dict.get("cv_id"))
    created_at_raw = raw_dict.get("data_cadastramento") or raw_dict.get("created_at")

    origem_cv = str(raw_dict.get("origem") or raw_dict.get("fonte") or "desconhecido").strip()
    midia_cv = raw_dict.get("midia") or raw_dict.get("canal")

    return CVLeadRecord(
        cv_id=cv_id,
        email=email_raw,
        email_clean=clean_email(email_raw),
        phone=phone_raw,
        phone_clean=clean_phone(phone_raw),
        origem_cv=origem_cv,
        midia_cv=str(midia_cv) if midia_cv else None,
        created_at=parse_datetime(created_at_raw),
        id_externo=str(raw_dict.get("id_externo")) if raw_dict.get("id_externo") else None,
        raw_payload=raw_dict,
    )
