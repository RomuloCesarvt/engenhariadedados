"""
Extrator Google Ads API (formulários de lead — Lead Form Assets).

Autenticação OAuth2 com refresh token e consulta GAQL ao recurso
lead_form_submission_data via REST (googleAds:search).
"""

import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from engine.config import OriginChannel, LeadRecord
from engine.extractors.base import BaseExtractor, in_period, to_naive_utc
from engine.normalizer import normalize_lead

API_VERSION = os.getenv("GOOGLE_ADS_API_VERSION", "v25")
MAX_PAGES = 50
PLACEHOLDERS = {"", "1234567890", "seu_developer_token_google_ads"}

ACAO_CREDENCIAIS = (
    "Preencha no engine/.env a credencial do Google Cloud: GOOGLE_ADS_CREDENTIALS_PATH (JSON da conta "
    "de serviço, com o e-mail dela liberado em Adm. > Acesso e segurança no Google Ads) ou o trio "
    "GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET / GOOGLE_ADS_REFRESH_TOKEN. O projeto do Cloud "
    "precisa de nível de acesso Explorer ou superior para ler contas de produção "
    "(console.cloud.google.com/google/ads-apis/overview)."
)
ESCOPO = "https://www.googleapis.com/auth/adwords"


def google_row_to_raw(row: Dict[str, Any]) -> Dict[str, Any]:
    """Converte uma linha do googleAds:search para o formato aceito por normalize_lead."""
    dados = row.get("leadFormSubmissionData") or {}
    raw: Dict[str, Any] = {
        "id": dados.get("resourceName"),
        "gclid": dados.get("gclid"),
        "created_at": dados.get("submissionDateTime"),
        "campaign_name": (row.get("campaign") or {}).get("name"),
        "utm_source": "google",
        "utm_medium": "cpc",
    }
    primeiro, ultimo = None, None
    for campo in dados.get("leadFormSubmissionFields") or []:
        tipo = str(campo.get("fieldType", "")).upper()
        valor = campo.get("fieldValue")
        if tipo == "EMAIL" or tipo == "WORK_EMAIL":
            raw["email"] = valor
        elif tipo in ("PHONE_NUMBER", "WORK_PHONE"):
            raw["phone"] = valor
        elif tipo == "FULL_NAME":
            raw["nome"] = valor
        elif tipo == "FIRST_NAME":
            primeiro = valor
        elif tipo == "LAST_NAME":
            ultimo = valor
    if not raw.get("nome") and (primeiro or ultimo):
        raw["nome"] = " ".join(p for p in (primeiro, ultimo) if p)
    return raw


class GoogleAdsExtractor(BaseExtractor):
    def __init__(self, developer_token: Optional[str] = None):
        super().__init__(OriginChannel.GOOGLE_ADS)
        # O token de desenvolvedor foi descontinuado em 09/09/2026: só é enviado se ainda existir
        self.developer_token = developer_token or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN") or ""
        self.credenciais = os.getenv("GOOGLE_ADS_CREDENTIALS_PATH") or ""
        self.client_id = os.getenv("GOOGLE_ADS_CLIENT_ID") or ""
        self.client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET") or ""
        self.refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN") or ""
        self.customer_id = (os.getenv("GOOGLE_ADS_CUSTOMER_ID") or "").replace("-", "").strip()
        self.login_customer_id = (os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or "").replace("-", "").strip()

    def tem_conta_de_servico(self) -> bool:
        return bool(self.credenciais and os.path.exists(self.credenciais))

    def _faltando(self) -> List[str]:
        faltando = []
        if not self.tem_conta_de_servico():
            if not (self.client_id and self.client_secret and self.refresh_token):
                faltando.append("GOOGLE_ADS_CREDENTIALS_PATH (conta de serviço) ou GOOGLE_ADS_CLIENT_ID / "
                                "GOOGLE_ADS_CLIENT_SECRET / GOOGLE_ADS_REFRESH_TOKEN")
        if self.customer_id in PLACEHOLDERS:
            faltando.append("GOOGLE_ADS_CUSTOMER_ID")
        return faltando

    def cabecalhos(self, client) -> Dict[str, str]:
        """Token de acesso (conta de serviço ou refresh token) e cabeçalhos da API do Google Ads."""
        if self.tem_conta_de_servico():
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            cred = service_account.Credentials.from_service_account_file(self.credenciais, scopes=[ESCOPO])
            cred.refresh(Request())
            acesso = cred.token
        else:
            token = client.post("https://oauth2.googleapis.com/token", data={
                "grant_type": "refresh_token", "client_id": self.client_id,
                "client_secret": self.client_secret, "refresh_token": self.refresh_token,
            })
            if token.status_code != 200:
                raise RuntimeError(f"Falha ao renovar o token OAuth ({token.status_code}): {token.text[:160]}")
            acesso = token.json()["access_token"]
        headers = {"Authorization": f"Bearer {acesso}", "Content-Type": "application/json"}
        if self.developer_token not in PLACEHOLDERS:  # descontinuado: só vai se ainda estiver no .env
            headers["developer-token"] = self.developer_token
        if self.login_customer_id:
            headers["login-customer-id"] = self.login_customer_id
        return headers

    @staticmethod
    def _mensagem_erro(res) -> str:
        try:
            erro = res.json()
            if isinstance(erro, list):
                erro = erro[0]
            erro = erro.get("error", {})
            detalhes = erro.get("details") or []
            for d in detalhes:
                for e in d.get("errors") or []:
                    if e.get("message"):
                        return f"HTTP {res.status_code}: {e['message']}"
            return f"HTTP {res.status_code}: {erro.get('message')}"
        except Exception:
            return f"HTTP {res.status_code}: {res.text[:160]}"

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        faltando = self._faltando()
        if faltando:
            self._set_status(
                "nao_configurado",
                message="Credenciais faltando: " + ", ".join(faltando) + ".",
                action=ACAO_CREDENCIAIS,
            )
            return self._fallback(self._mock_leads)

        try:
            import httpx

            with httpx.Client(timeout=40) as client:
                headers = self.cabecalhos(client)
                inicio = to_naive_utc(start_date).strftime("%Y-%m-%d %H:%M:%S")
                fim = to_naive_utc(end_date).strftime("%Y-%m-%d %H:%M:%S")
                query = (
                    "SELECT lead_form_submission_data.resource_name, lead_form_submission_data.gclid, "
                    "lead_form_submission_data.submission_date_time, "
                    "lead_form_submission_data.lead_form_submission_fields, campaign.name "
                    "FROM lead_form_submission_data "
                    f"WHERE lead_form_submission_data.submission_date_time >= '{inicio}' "
                    f"AND lead_form_submission_data.submission_date_time <= '{fim}'"
                )
                url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{self.customer_id}/googleAds:search"

                linhas: List[dict] = []
                page_token = None
                for _ in range(MAX_PAGES):
                    body = {"query": query}
                    if page_token:
                        body["pageToken"] = page_token
                    res = client.post(url, headers=headers, json=body)
                    if res.status_code != 200:
                        raise RuntimeError(self._mensagem_erro(res))
                    data = res.json()
                    linhas.extend(data.get("results", []))
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break

            leads = [
                normalize_lead(google_row_to_raw(row), self.channel)
                for row in linhas
            ]
            leads = [lead for lead in leads if in_period(lead.created_at, start_date, end_date)]
            self._set_status(
                "real",
                len(leads),
                f"{len(leads)} lead(s) de formulário do Google Ads no período. "
                "Leads que chegam por formulário do site não passam pelo Google Ads.",
            )
            print(f"  [Google Ads API] {len(leads)} leads reais no período.")
            return leads

        except Exception as e:
            self._set_status("erro", message=f"Falha ao consultar o Google Ads: {e}", action=ACAO_CREDENCIAIS)
            print(f"  [Google Ads API Erro] {e}")
            return self._fallback(self._mock_leads)

    def _mock_leads(self) -> List[LeadRecord]:
        sample = [
            {"id": "gads_201", "email": "fernando.alves@gmail.com", "phone": "11933331111", "campaign_name": "Search - Residencial Sol - Apartamentos SP", "gclid": "gclid_alpha_201", "created_at": "2026-07-25 09:10:00"},
            {"id": "gads_202", "email": "beatriz.costa@gmail.com", "phone": "21922223333", "campaign_name": "Search - Condomínio Horizonte RJ", "gclid": "gclid_alpha_202", "created_at": "2026-07-25 16:30:00"},
            {"id": "gads_203", "email": "ricardo.oliveira@uol.com.br", "phone": "31911114444", "campaign_name": "PMax - Condomínio Horizonte", "gclid": "gclid_alpha_203", "created_at": "2026-07-26 10:00:00"},
            {"id": "gads_204", "email": "camila.ferreira@outlook.com", "phone": "41999995555", "campaign_name": "Display Remarketing", "gclid": "gclid_alpha_204", "created_at": "2026-07-26 18:00:00"},
        ]
        leads = []
        for item in sample:
            item["utm_source"] = "google"
            item["utm_medium"] = "cpc"
            leads.append(normalize_lead(item, self.channel))
        return leads
