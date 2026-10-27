"""
Extrator RD Station Marketing.

Autenticação OAuth2 (o access token dura 24h): com RD_STATION_CLIENT_ID,
RD_STATION_CLIENT_SECRET e RD_STATION_REFRESH_TOKEN o token é renovado a cada
execução. RD_STATION_API_TOKEN, se preenchido, é usado como access token direto.

A API não lista conversões por período; os contatos vêm de uma segmentação
(padrão: a de todos os contatos) e são filtrados pela data de criação.
"""

import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from engine.config import OriginChannel, LeadRecord
from engine.extractors.base import BaseExtractor, in_period
from engine.normalizer import normalize_lead, parse_datetime

API = "https://api.rd.services"
PAGE_SIZE = 125
# A segmentação "Todos os contatos" passa de 25 mil contatos e não vem ordenada por data:
# é preciso ler todas as páginas para não perder contatos do período.
MAX_PAGES = int(os.getenv("RD_STATION_MAX_PAGINAS", "2000"))
# Telefone e última conversão custam 2 chamadas por contato. Desligado por padrão: o cruzamento
# com o CV usa o UUID do contato, que já vem na lista.
MAX_DETALHES = int(os.getenv("RD_STATION_MAX_DETALHES", "0"))
MAX_TENTATIVAS_429 = 6

ACAO_OAUTH = (
    "Crie um app na RD Station App Store (callback http://localhost:8791/callback) e rode "
    "'python engine/rd_oauth.py': ele autoriza a conta e grava RD_STATION_CLIENT_ID, "
    "RD_STATION_CLIENT_SECRET e RD_STATION_REFRESH_TOKEN no engine/.env."
)


class RDStationExtractor(BaseExtractor):
    def __init__(self, api_token: Optional[str] = None):
        super().__init__(OriginChannel.RD_STATION)
        self.api_token = api_token or os.getenv("RD_STATION_API_TOKEN") or ""
        self.client_id = os.getenv("RD_STATION_CLIENT_ID") or ""
        self.client_secret = os.getenv("RD_STATION_CLIENT_SECRET") or ""
        self.refresh_token = os.getenv("RD_STATION_REFRESH_TOKEN") or ""
        self.segmentation_id = os.getenv("RD_STATION_SEGMENTATION_ID") or ""

    def _access_token(self, client) -> str:
        if self.client_id and self.client_secret and self.refresh_token:
            res = client.post(
                f"{API}/auth/token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
            )
            if res.status_code != 200:
                raise RuntimeError(f"Falha ao renovar o token OAuth ({res.status_code}): {res.text[:160]}")
            return res.json()["access_token"]
        return self.api_token

    @staticmethod
    def _get(client, url: str, token: str, params: Optional[dict] = None) -> Any:
        import time

        for tentativa in range(MAX_TENTATIVAS_429):
            res = client.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, params=params)
            if res.status_code != 429:
                break
            # Limite de requisições da RD: espera o tempo indicado (ou recua exponencialmente)
            espera = float(getattr(res, "headers", {}).get("Retry-After", 0) or 2 ** tentativa)
            time.sleep(min(espera, 60))
        if res.status_code == 401:
            raise PermissionError("token inválido ou expirado (HTTP 401)")
        if res.status_code != 200:
            raise RuntimeError(f"HTTP {res.status_code} em {url.replace(API, '')}: {res.text[:160]}")
        return res.json()

    def _segmentacao(self, client, token: str) -> Dict[str, Any]:
        if self.segmentation_id:
            return {"id": self.segmentation_id, "name": f"segmentação {self.segmentation_id}"}
        data = self._get(client, f"{API}/platform/segmentations", token)
        segs = data.get("segmentations", []) if isinstance(data, dict) else []
        if not segs:
            raise RuntimeError("nenhuma segmentação encontrada na conta")
        todos = [s for s in segs if "todos" in str(s.get("name", "")).lower()]
        return (todos or segs)[0]

    def fetch_leads(self, start_date: datetime, end_date: datetime) -> List[LeadRecord]:
        if not (self.api_token or (self.client_id and self.client_secret and self.refresh_token)):
            self._set_status("nao_configurado", message="Credenciais da RD Station não configuradas.", action=ACAO_OAUTH)
            return self._fallback(self._mock_leads)

        try:
            import httpx

            with httpx.Client(timeout=30) as client:
                token = self._access_token(client)
                seg = self._segmentacao(client, token)

                no_periodo: List[dict] = []
                total_lidos = 0
                leitura_completa = False
                for pagina in range(1, MAX_PAGES + 1):
                    data = self._get(
                        client,
                        f"{API}/platform/segmentations/{seg['id']}/contacts",
                        token,
                        {"page": pagina, "page_size": PAGE_SIZE},
                    )
                    contatos = data.get("contacts", []) if isinstance(data, dict) else []
                    if not contatos:
                        leitura_completa = True
                        break
                    total_lidos += len(contatos)
                    for c in contatos:
                        criado = parse_datetime(c.get("created_at") or c.get("last_conversion_date"))
                        if c.get("created_at") or c.get("last_conversion_date"):
                            if in_period(criado, start_date, end_date):
                                no_periodo.append(c)
                    if len(contatos) < PAGE_SIZE:
                        leitura_completa = True
                        break

                leads: List[LeadRecord] = []
                for i, contato in enumerate(no_periodo):
                    raw = {
                        "id": contato.get("uuid"),
                        "rd_id": contato.get("uuid"),
                        "nome": contato.get("name"),
                        "email": contato.get("email"),
                        "created_at": contato.get("created_at") or contato.get("last_conversion_date"),
                        "campaign_name": "RD Station",
                        "utm_source": "rd_station",
                        "utm_medium": "inbound",
                    }
                    if i < MAX_DETALHES and contato.get("uuid"):
                        uuid = contato["uuid"]
                        try:
                            detalhe = self._get(client, f"{API}/platform/contacts/uuid:{uuid}", token)
                            raw["phone"] = detalhe.get("mobile_phone") or detalhe.get("personal_phone")
                            for chave, valor in detalhe.items():
                                if chave.startswith("cf_") and "empreendimento" in chave and valor:
                                    raw["empreendimento"] = valor
                            eventos = self._get(
                                client,
                                # Eventos usam o UUID puro; o prefixo "uuid:" só vale para /contacts/uuid:{id}
                                f"{API}/platform/contacts/{uuid}/events",
                                token,
                                {"event_type": "CONVERSION"},
                            )
                            if isinstance(eventos, list) and eventos:
                                raw["campaign_name"] = eventos[0].get("event_identifier") or raw["campaign_name"]
                        except PermissionError:
                            raise
                        except Exception:
                            pass  # sem detalhe o lead ainda vale por e-mail
                    leads.append(normalize_lead(raw, self.channel))

            extra = ""
            if MAX_DETALHES and len(no_periodo) > MAX_DETALHES:
                extra = f" Telefone e conversão buscados só para os primeiros {MAX_DETALHES}."
            if not leitura_completa:
                extra += (
                    f" ATENÇÃO: leitura interrompida no limite de {MAX_PAGES} páginas — a base pode estar incompleta "
                    "(aumente RD_STATION_MAX_PAGINAS)."
                )
            self._set_status(
                "real",
                len(leads),
                f"{len(leads)} contato(s) criados no período, de {total_lidos} lidos na segmentação "
                f"'{seg.get('name')}'.{extra}",
            )
            print(f"  [RD Station API] {len(leads)} leads reais no período.")
            return leads

        except PermissionError as e:
            usando_oauth = bool(self.client_id and self.client_secret and self.refresh_token)
            if usando_oauth:
                mensagem = f"RD Station recusou o acesso: {e}."
            else:
                # A "Chave de API" do painel da RD Marketing só envia conversões; não lê contatos
                mensagem = (
                    "A chave em RD_STATION_API_TOKEN não tem acesso de leitura (HTTP 401). A 'Chave de API' "
                    "do painel da RD Marketing só envia conversões; para listar contatos é preciso um app OAuth."
                )
            self._set_status("erro", message=mensagem, action=ACAO_OAUTH)
            print(f"  [RD Station API Erro] {e}")
            return self._fallback(self._mock_leads)
        except Exception as e:
            self._set_status("erro", message=f"Falha ao consultar a RD Station: {e}", action=ACAO_OAUTH)
            print(f"  [RD Station API Erro] {e}")
            return self._fallback(self._mock_leads)

    def _mock_leads(self) -> List[LeadRecord]:
        sample = [
            {"id": "rd_301", "email": "patricia.rocha@gmail.com", "phone": "11977778888", "campaign_name": "Ebook Financiamento - Residencial Sol", "rd_id": "rd_lead_301", "created_at": "2026-07-25 12:00:00"},
            {"id": "rd_302", "email": "thiago.martins@yahoo.com", "phone": "21966669999", "campaign_name": "Webinar Simulador - Condomínio Horizonte", "rd_id": "rd_lead_302", "created_at": "2026-07-26 14:20:00"},
            {"id": "rd_303", "email": "vanessa.gomes@icloud.com", "phone": "31955550000", "campaign_name": "Landing Page Cadastro VIP", "rd_id": "rd_lead_303", "created_at": "2026-07-26 17:45:00"},
        ]
        leads = []
        for item in sample:
            leads.append(normalize_lead(item, self.channel))
        return leads
