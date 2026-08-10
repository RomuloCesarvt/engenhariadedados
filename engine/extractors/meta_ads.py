"""
Extrator Meta Ads (Facebook / Instagram Lead Ads).

Fluxo oficial da Graph API:
  1. /me/accounts                   -> páginas que o token enxerga, com o token de cada página
     (ou só as de META_PAGE_IDS / META_PAGE_ID, se configurados)
  2. /{page_id}/leadgen_forms       -> formulários de cadastro de cada página
  3. /{form_id}/leads               -> leads de cada formulário a partir do início do período
"""

import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from engine.config import OriginChannel, LeadRecord
from engine.extractors.base import BaseExtractor, in_period, to_naive_utc
from engine.normalizer import normalize_lead, parse_datetime

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
PLATAFORMAS_META = {"ig": "Instagram", "fb": "Facebook", "an": "Audience Network", "msg": "Messenger", "wa": "WhatsApp"}
MAX_PAGES = 50

ACAO_TOKEN = (
    "Gere um token permanente de Usuário do Sistema no Business Manager com as permissões "
    "leads_retrieval, pages_show_list e pages_read_engagement, e atualize META_ACCESS_TOKEN."
)


class MetaApiError(Exception):
    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.code = code


def meta_lead_to_raw(lead: Dict[str, Any], form_name: Optional[str] = None) -> Dict[str, Any]:
    """Converte um lead da Graph API para o formato aceito por normalize_lead."""
    raw: Dict[str, Any] = {
        "id": lead.get("id"),
        "created_time": lead.get("created_time"),
        "fbclid": lead.get("id"),
        "campaign_name": lead.get("campaign_name") or lead.get("adset_name") or form_name,
        "formulario": form_name,
        "conjunto": lead.get("adset_name"),
        "anuncio": lead.get("ad_name"),
        "anuncio_id": lead.get("ad_id"),
        "conjunto_id": lead.get("adset_id"),
        "campanha_id": lead.get("campaign_id"),
        "plataforma": PLATAFORMAS_META.get(lead.get("platform"), lead.get("platform")),
        "organico": lead.get("is_organic"),
        "utm_source": "facebook",
        "utm_medium": "cpc",
    }
    respostas: Dict[str, Any] = {}
    for field in lead.get("field_data", []):
        nome = str(field.get("name", "")).lower()
        valor = (field.get("values") or [None])[0]
        if "email" in nome:
            raw["email"] = valor
        elif any(p in nome for p in ("phone", "telef", "celular", "whatsapp")):
            raw["phone"] = valor
        elif nome in ("full_name", "nome", "nome_completo", "name"):
            raw["nome"] = valor
        elif "cpf" in nome:
            raw["cpf"] = valor
        elif "empreendimento" in nome:
            raw["empreendimento"] = valor
        else:
            # Demais perguntas do formulário ("estou em busca de", renda...): ajudam a achar o lead no CV
            respostas[nome.replace("_", " ").strip(" :")] = valor
    raw["respostas"] = respostas
    return raw


class MetaAdsExtractor(BaseExtractor):
    def __init__(self, access_token: Optional[str] = None, page_id: Optional[str] = None):
        super().__init__(OriginChannel.META_ADS)
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN")
        ids = page_id or os.getenv("META_PAGE_IDS") or os.getenv("META_PAGE_ID") or ""
        self.page_ids = [i.strip() for i in str(ids).split(",") if i.strip()]

    @staticmethod
    def _get(client, url: str, params: Optional[dict]) -> dict:
        res = client.get(url, params=params)
        try:
            data = res.json()
        except Exception:
            data = {}
        if res.status_code != 200:
            erro = data.get("error", {}) if isinstance(data, dict) else {}
            raise MetaApiError(erro.get("message") or f"HTTP {res.status_code}", erro.get("code"))
        return data

    def _paginate(self, client, url: str, params: dict) -> List[dict]:
        itens: List[dict] = []
        proxima: Optional[str] = url
        pagina = 0
        while proxima and pagina < MAX_PAGES:
            data = self._get(client, proxima, params)
            itens.extend(data.get("data", []))
            proxima = (data.get("paging") or {}).get("next")
            params = None  # a URL "next" já carrega os parâmetros
            pagina += 1
        return itens

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        if not self.access_token:
            self._set_status(
                "nao_configurado",
                message="META_ACCESS_TOKEN não configurado.",
                action=ACAO_TOKEN,
            )
            return self._fallback(self._mock_leads)

        try:
            import httpx

            base = f"https://graph.facebook.com/{GRAPH_VERSION}"
            with httpx.Client(timeout=30) as client:
                # Páginas: todas as que o token administra (com o token de cada uma) ou as configuradas
                acessiveis = self._paginate(
                    client, f"{base}/me/accounts", {"fields": "id,name,access_token", "limit": 100, "access_token": self.access_token}
                )
                if self.page_ids:
                    paginas = [p for p in acessiveis if p.get("id") in self.page_ids]
                    paginas += [{"id": pid, "access_token": self.access_token} for pid in self.page_ids if pid not in {p.get("id") for p in paginas}]
                else:
                    paginas = acessiveis
                if not paginas:
                    raise MetaApiError("o token não enxerga nenhuma página do Facebook (atribua as páginas ao usuário do sistema)")

                inicio_ts = int(to_naive_utc(start_date).replace(tzinfo=timezone.utc).timestamp())
                filtro = json.dumps([{"field": "time_created", "operator": "GREATER_THAN", "value": inicio_ts}])

                leads: List[LeadRecord] = []
                total_formularios = 0
                paginas_com_erro: List[str] = []
                for pagina in paginas:
                    token_pagina = pagina.get("access_token") or self.access_token
                    try:
                        formularios = self._paginate(
                            client,
                            f"{base}/{pagina['id']}/leadgen_forms",
                            {"fields": "id,name,status", "limit": 100, "access_token": token_pagina},
                        )
                    except MetaApiError as e:
                        if e.code == 190:
                            raise
                        paginas_com_erro.append(f"{pagina.get('name') or pagina['id']}: {e}")
                        continue
                    total_formularios += len(formularios)
                    for form in formularios:
                        brutos = self._paginate(
                            client,
                            f"{base}/{form['id']}/leads",
                            {
                                "fields": "id,created_time,field_data,campaign_name,campaign_id,adset_name,adset_id,ad_name,ad_id,form_id,platform,is_organic",
                                "filtering": filtro,
                                "limit": 500,
                                "access_token": token_pagina,
                            },
                        )
                        for lead in brutos:
                            if in_period(parse_datetime(lead.get("created_time")), start_date, end_date):
                                raw = meta_lead_to_raw(lead, form.get("name"))
                                raw["pagina"] = pagina.get("name")
                                leads.append(normalize_lead(raw, self.channel))

            aviso = f" Páginas sem acesso aos formulários: {'; '.join(paginas_com_erro)}." if paginas_com_erro else ""
            self._set_status(
                "real",
                len(leads),
                f"{len(leads)} lead(s) no período em {total_formularios} formulário(s) de {len(paginas)} página(s).{aviso}",
            )
            print(f"  [Meta Ads API] {len(leads)} leads reais no período.")
            return leads

        except MetaApiError as e:
            expirado = e.code == 190
            self._set_status(
                "erro",
                message=("Token da Meta expirado ou invalidado: " if expirado else "Erro da Graph API: ") + str(e),
                action=ACAO_TOKEN if expirado else "Confira o META_PAGE_ID e as permissões do token.",
            )
            print(f"  [Meta Ads API Erro] {e}")
            return self._fallback(self._mock_leads)
        except Exception as e:
            self._set_status("erro", message=f"Falha ao consultar a Meta: {e}", action=ACAO_TOKEN)
            print(f"  [Meta Ads API Erro] {e}")
            return self._fallback(self._mock_leads)

    def _mock_leads(self) -> List[LeadRecord]:
        sample = [
            {"id": "meta_101", "email": "carlos.silva@gmail.com", "phone": "11988881111", "campaign_name": "Lançamento Residencial Sol", "fbclid": "fb_click_101", "created_at": "2026-07-25 10:30:00"},
            {"id": "meta_102", "email": "ana.pereira@outlook.com", "phone": "11988882222", "campaign_name": "Lançamento Residencial Sol", "fbclid": "fb_click_102", "created_at": "2026-07-25 11:15:00"},
            {"id": "meta_103", "email": "marcos.souza@uol.com.br", "phone": "21977773333", "campaign_name": "Condomínio Horizonte", "fbclid": "fb_click_103", "created_at": "2026-07-25 14:00:00"},
            {"id": "meta_104", "email": "luciana.lima@hotmail.com", "phone": "31966664444", "campaign_name": "Condomínio Horizonte", "fbclid": "fb_click_104", "created_at": "2026-07-26 09:20:00"},
            {"id": "meta_105", "email": "roberto.dias.perdido@gmail.com", "phone": "11955555555", "campaign_name": "Lançamento Residencial Sol", "fbclid": "fb_click_105", "created_at": "2026-07-26 15:45:00"},
            {"id": "meta_106", "email": "juliana.mendes@yahoo.com.br", "phone": "11944446666", "campaign_name": "Campanha Retargeting", "fbclid": "fb_click_106", "created_at": "2026-07-27 08:10:00"},
        ]
        leads = []
        for item in sample:
            item["utm_source"] = "facebook"
            item["utm_medium"] = "cpc"
            leads.append(normalize_lead(item, self.channel))
        return leads
