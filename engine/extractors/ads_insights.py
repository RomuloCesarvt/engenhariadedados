"""
Números das plataformas de anúncio por conta, campanha e dia: investimento, impressões,
cliques e os leads que a PRÓPRIA plataforma diz ter gerado.

É a base da conferência "Meta/Google dizem X leads — quantos chegaram no CV?" e do custo
por lead. Cada conta de anúncios da Moura Leite corresponde a um empreendimento
("ML - Jardim dos Ipês III", "ML - Central Parque Avaré 2"...), o que permite atribuir
investimento e leads ao produto sem depender do nome da campanha.
"""

import json
import time
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from engine.extractors.base import StatusMixin, to_naive_utc
from engine.extractors.google_ads import ACAO_CREDENCIAIS, GoogleAdsExtractor

META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
GOOGLE_API_VERSION = os.getenv("GOOGLE_ADS_API_VERSION", "v25")
MAX_PAGES = 100


def _reais(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fatias_mensais(inicio: datetime, fim: datetime) -> List[tuple]:
    """Divide o período em meses-calendário: [("2026-01-15", "2026-01-31"), ("2026-02-01", ...)]."""
    fatias = []
    atual = inicio.date()
    ultimo = fim.date()
    while atual <= ultimo:
        proximo = (atual.replace(day=1) + timedelta(days=32)).replace(day=1)
        fatias.append((atual.isoformat(), min(proximo - timedelta(days=1), ultimo).isoformat()))
        atual = proximo
    return fatias

ACAO_META_INSIGHTS = (
    "Gere um token permanente de Usuário do Sistema no Business Manager, dê a ele acesso às contas "
    "de anúncio de cada empreendimento com a permissão ads_read (e leads_retrieval para ler os "
    "formulários) e atualize META_ACCESS_TOKEN."
)

# Tipos de ação da Meta que representam lead
META_LEAD_FORMULARIO = ("onsite_conversion.lead_grouped", "leadgen_grouped")
META_LEAD_SITE = ("offsite_conversion.fb_pixel_lead",)
META_CONVERSA = ("onsite_conversion.messaging_conversation_started_7d",)


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


def meta_insight_row(conta: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    """Converte uma linha do /insights (nível campanha, por dia) para o formato da base."""
    acoes: Dict[str, float] = {}
    for acao in item.get("actions") or []:
        acoes[acao.get("action_type")] = acoes.get(acao.get("action_type"), 0) + float(acao.get("value") or 0)

    formulario = sum(acoes.get(t, 0) for t in META_LEAD_FORMULARIO)
    site = sum(acoes.get(t, 0) for t in META_LEAD_SITE)
    conversas = sum(acoes.get(t, 0) for t in META_CONVERSA)
    # "lead" é o total consolidado pela Meta; na ausência dele soma formulário + site
    leads = acoes.get("lead", formulario + site)

    return {
        "plataforma": "meta",
        "conta_id": conta.get("id"),
        "conta_nome": conta.get("name"),
        "campanha_id": item.get("campaign_id"),
        "campanha_nome": item.get("campaign_name"),
        "data": item.get("date_start"),
        "investimento": round(float(item.get("spend") or 0), 2),
        "impressoes": int(float(item.get("impressions") or 0)),
        "cliques": int(float(item.get("clicks") or 0)),
        "leads_formulario": int(formulario),
        "leads_site": int(site),
        "conversas_whatsapp": int(conversas),
        "leads_plataforma": int(leads),
    }


class MetaInsightsExtractor(StatusMixin):
    source_key = "meta_ads"

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN")
        ids = os.getenv("META_AD_ACCOUNT_IDS", "")
        self.account_ids = [i.strip() for i in ids.split(",") if i.strip()]
        self.status = None

    def _get(self, client, url: str, params: Optional[dict]) -> dict:
        res = client.get(url, params=params)
        try:
            data = res.json()
        except Exception:
            data = {}
        if res.status_code != 200:
            erro = data.get("error", {}) if isinstance(data, dict) else {}
            codigo = erro.get("code")
            raise RuntimeError(
                ("Token da Meta expirado ou invalidado: " if codigo == 190 else "Erro da API da Meta: ")
                + str(erro.get("message") or f"HTTP {res.status_code}")
            )
        return data

    def _paginate(self, client, url: str, params: dict) -> List[dict]:
        itens: List[dict] = []
        proxima: Optional[str] = url
        for _ in range(MAX_PAGES):
            if not proxima:
                break
            data = self._get(client, proxima, params)
            itens.extend(data.get("data", []))
            proxima = (data.get("paging") or {}).get("next")
            params = None
        return itens

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        if not self.access_token:
            self._set_status("nao_configurado", message="META_ACCESS_TOKEN não configurado.", action=ACAO_META_INSIGHTS)
            return []
        try:
            import httpx

            base = f"https://graph.facebook.com/{META_GRAPH_VERSION}"
            token = {"access_token": self.access_token}
            with httpx.Client(timeout=60) as client:
                if self.account_ids:
                    contas = []
                    for conta_id in self.account_ids:
                        act = conta_id if conta_id.startswith("act_") else f"act_{conta_id}"
                        contas.append(self._get(client, f"{base}/{act}", {"fields": "id,name,account_status", **token}))
                else:
                    contas = self._paginate(
                        client, f"{base}/me/adaccounts", {"fields": "id,name,account_status", "limit": 200, **token}
                    )

                linhas: List[Dict[str, Any]] = []
                contas_com_erro: List[str] = []
                for conta in contas:
                    try:
                        # Mês a mês: períodos longos no nível campanha/dia estouram o limite da Meta ("unknown error")
                        for inicio, fim in _fatias_mensais(to_naive_utc(start_date), to_naive_utc(end_date)):
                            itens = self._paginate(
                                client,
                                f"{base}/{conta['id']}/insights",
                                {
                                    "level": "campaign",
                                    "time_increment": 1,
                                    "time_range": json.dumps({"since": inicio, "until": fim}),
                                    "fields": "campaign_id,campaign_name,spend,impressions,clicks,actions",
                                    "limit": 500,
                                    **token,
                                },
                            )
                            linhas.extend(meta_insight_row(conta, item) for item in itens)
                    except RuntimeError as e:
                        if "expirado" in str(e):
                            raise
                        contas_com_erro.append(f"{conta.get('name') or conta['id']}: {e}")

            if contas and len(contas_com_erro) == len(contas):
                raise RuntimeError("; ".join(contas_com_erro))
            leads = sum(l["leads_plataforma"] for l in linhas)
            invest = sum(l["investimento"] for l in linhas)
            aviso = f" Contas não lidas: {'; '.join(contas_com_erro)}." if contas_com_erro else ""
            self._set_status(
                "real",
                len(linhas),
                f"{len(contas)} conta(s) de anúncio: {leads} leads e {_reais(invest)} investidos no período, segundo a Meta.{aviso}",
            )
            return linhas
        except Exception as e:
            self._set_status("erro", message=str(e), action=ACAO_META_INSIGHTS)
            return []


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------


def google_insight_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Converte uma linha do googleAds:search (campanha por dia) para o formato da base."""
    customer = row.get("customer") or {}
    campaign = row.get("campaign") or {}
    metrics = row.get("metrics") or {}
    segments = row.get("segments") or {}
    return {
        "plataforma": "google",
        "conta_id": str(customer.get("id") or ""),
        "conta_nome": customer.get("descriptiveName"),
        "campanha_id": str(campaign.get("id") or ""),
        "campanha_nome": campaign.get("name"),
        "data": segments.get("date"),
        "investimento": round(int(metrics.get("costMicros") or 0) / 1_000_000, 2),
        "impressoes": int(metrics.get("impressions") or 0),
        "cliques": int(metrics.get("clicks") or 0),
        "leads_formulario": 0,
        "leads_site": 0,
        "conversas_whatsapp": 0,
        "leads_plataforma": int(round(float(metrics.get("conversions") or 0))),
    }


class GoogleInsightsExtractor(StatusMixin):
    source_key = "google_ads"

    def __init__(self):
        self.creds = GoogleAdsExtractor()
        ids = os.getenv("GOOGLE_ADS_CUSTOMER_IDS", "") or os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
        self.customer_ids = [
            i.replace("-", "").strip() for i in ids.split(",") if i.replace("-", "").strip() not in ("", "1234567890")
        ]
        self.status = None

    def _faltando(self) -> List[str]:
        faltando = [f for f in self.creds._faltando() if f != "GOOGLE_ADS_CUSTOMER_ID"]
        if not self.customer_ids and not self.creds.login_customer_id:
            faltando.append("GOOGLE_ADS_CUSTOMER_IDS (ou GOOGLE_ADS_LOGIN_CUSTOMER_ID da conta MCC)")
        return faltando

    def _search(self, client, headers: dict, customer_id: str, query: str) -> List[dict]:
        url = f"https://googleads.googleapis.com/{GOOGLE_API_VERSION}/customers/{customer_id}/googleAds:search"
        linhas: List[dict] = []
        page_token = None
        for _ in range(MAX_PAGES):
            body = {"query": query}
            if page_token:
                body["pageToken"] = page_token
            res = client.post(url, headers=headers, json=body)
            if res.status_code != 200:
                raise RuntimeError(GoogleAdsExtractor._mensagem_erro(res))
            data = res.json()
            linhas.extend(data.get("results", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return linhas

    def _conectar(self, client) -> dict:
        """Cabeçalhos da API do Google Ads: conta de serviço ou refresh token do usuário."""
        return self.creds.cabecalhos(client)

    @staticmethod
    def _com_login(headers: dict, gestora: Optional[str]) -> dict:
        """A conta filha só responde com o login-customer-id da gestora; a conta direta, sem ele."""
        novos = {k: v for k, v in headers.items() if k != "login-customer-id"}
        if gestora:
            novos["login-customer-id"] = gestora
        return novos

    def _contas(self, client, headers: dict) -> List[Tuple[str, Optional[str]]]:
        """
        (conta, gestora) de tudo que a credencial enxerga: as contas soltas e as filhas de cada MCC.

        A Alta Vista, por exemplo, está fora da MCC — sem isso ela ficaria de fora. Conta cancelada
        ou suspensa responde 403 e derrubaria a consulta inteira, então fica de fora.
        """
        if self.customer_ids:
            gestora = self.creds.login_customer_id or None
            return [(i, gestora) for i in self.customer_ids]
        url = f"https://googleads.googleapis.com/{GOOGLE_API_VERSION}/customers:listAccessibleCustomers"
        res = client.get(url, headers=self._com_login(headers, None))
        if res.status_code != 200:
            raise RuntimeError(GoogleAdsExtractor._mensagem_erro(res))
        saida: List[Tuple[str, Optional[str]]] = []
        for nome in res.json().get("resourceNames") or []:
            raiz = nome.split("/")[-1]
            propria = self._search(client, self._com_login(headers, None), raiz,
                                   "SELECT customer.manager, customer.status FROM customer")
            info = (propria[0] if propria else {}).get("customer") or {}
            if not info.get("manager"):
                if info.get("status") == "ENABLED":
                    saida.append((raiz, None))
                continue
            filhas = self._search(
                client, self._com_login(headers, raiz), raiz,
                "SELECT customer_client.id, customer_client.manager, customer_client.status FROM customer_client "
                "WHERE customer_client.level = 1 AND customer_client.status = 'ENABLED'",
            )
            saida += [(str(c["customerClient"]["id"]), raiz) for c in filhas
                      if not (c.get("customerClient") or {}).get("manager")]
        return saida

    def _por_conta(self, client, headers: dict, contas: List[Tuple[str, Optional[str]]], query: str,
                   linha) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Roda a mesma consulta em cada conta. A conta que recusa não derruba as outras."""
        linhas: List[Dict[str, Any]] = []
        recusadas: List[str] = []
        for conta, gestora in contas:
            try:
                linhas.extend(linha(r) for r in self._search(client, self._com_login(headers, gestora), conta, query))
            except RuntimeError as e:
                if "not yet enabled" in str(e) or "deactivated" in str(e) or "PERMISSION" in str(e).upper():
                    recusadas.append(conta)
                    continue
                raise
        return linhas, recusadas

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        faltando = self._faltando()
        if faltando:
            self._set_status("nao_configurado", message="Credenciais faltando: " + ", ".join(faltando) + ".", action=ACAO_CREDENCIAIS)
            return []
        try:
            import httpx

            with httpx.Client(timeout=60) as client:
                headers = self._conectar(client)
                contas = self._contas(client, headers)
                inicio = to_naive_utc(start_date).strftime("%Y-%m-%d")
                fim = to_naive_utc(end_date).strftime("%Y-%m-%d")
                query = (
                    "SELECT customer.id, customer.descriptive_name, campaign.id, campaign.name, segments.date, "
                    "metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions "
                    f"FROM campaign WHERE segments.date BETWEEN '{inicio}' AND '{fim}' AND metrics.impressions > 0"
                )
                linhas, recusadas = self._por_conta(client, headers, contas, query, google_insight_row)

            leads = sum(l["leads_plataforma"] for l in linhas)
            invest = sum(l["investimento"] for l in linhas)
            self._set_status(
                "real",
                len(linhas),
                f"{len(contas) - len(recusadas)} conta(s): {leads} conversões e {_reais(invest)} investidos no período, "
                "segundo o Google. Conversões seguem as ações marcadas como principais na conta."
                + (f" {len(recusadas)} conta(s) sem acesso ficaram de fora." if recusadas else ""),
            )
            return linhas
        except Exception as e:
            self._set_status("erro", message=f"Falha ao consultar o Google Ads: {e}", action=ACAO_CREDENCIAIS)
            return []


def google_palavra_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Uma linha do keyword_view (palavra-chave por dia) para o formato da base."""
    customer = row.get("customer") or {}
    campaign = row.get("campaign") or {}
    grupo = row.get("adGroup") or {}
    criterio = ((row.get("adGroupCriterion") or {}).get("keyword")) or {}
    metrics = row.get("metrics") or {}
    segments = row.get("segments") or {}
    # Por dia: assim o período escolhido na tela vale exatamente, sem pular para o mês inteiro
    data = str(segments.get("date") or "")[:10]
    return {
        "plataforma": "google",
        "conta_id": str(customer.get("id") or ""),
        "conta_nome": customer.get("descriptiveName"),
        "campanha_id": str(campaign.get("id") or ""),
        "campanha_nome": campaign.get("name"),
        "grupo_nome": grupo.get("name"),
        "palavra": (criterio.get("text") or "").strip(),
        "correspondencia": CORRESPONDENCIA.get(criterio.get("matchType"), criterio.get("matchType")),
        "data": data,
        "mes": data[:7],
        "investimento": round(int(metrics.get("costMicros") or 0) / 1_000_000, 2),
        "impressoes": int(metrics.get("impressions") or 0),
        "cliques": int(metrics.get("clicks") or 0),
        "conversoes": round(float(metrics.get("conversions") or 0), 2),
    }


# Como o Google chama o tipo de correspondência, em português
CORRESPONDENCIA = {"EXACT": "Exata", "PHRASE": "Frase", "BROAD": "Ampla", "NEAR_EXACT": "Exata (variação)",
                   "NEAR_PHRASE": "Frase (variação)"}


class GooglePalavrasExtractor(GoogleInsightsExtractor):
    """Palavras-chave dos anúncios do Google, por mês, com custo e conversões."""

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        faltando = self._faltando()
        if faltando:
            self._set_status("nao_configurado", message="Credenciais faltando: " + ", ".join(faltando) + ".", action=ACAO_CREDENCIAIS)
            return []
        try:
            import httpx

            with httpx.Client(timeout=60) as client:
                headers = self._conectar(client)
                contas = self._contas(client, headers)
                inicio = to_naive_utc(start_date).strftime("%Y-%m-%d")
                fim = to_naive_utc(end_date).strftime("%Y-%m-%d")
                query = (
                    "SELECT customer.id, customer.descriptive_name, campaign.id, campaign.name, ad_group.name, "
                    "ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, segments.date, "
                    "metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions "
                    f"FROM keyword_view WHERE segments.date BETWEEN '{inicio}' AND '{fim}' AND metrics.impressions > 0"
                )
                linhas, recusadas = self._por_conta(client, headers, contas, query, google_palavra_row)
            linhas = [l for l in linhas if l["palavra"]]
            palavras = len({l["palavra"] for l in linhas})
            invest = sum(l["investimento"] for l in linhas)
            self._set_status(
                "real", len(linhas),
                f"{palavras} palavra(s)-chave em {len(contas) - len(recusadas)} conta(s): {_reais(invest)} investidos "
                "no período, segundo o Google."
                + (f" {len(recusadas)} conta(s) sem acesso ficaram de fora." if recusadas else ""),
            )
            return linhas
        except Exception as e:  # noqa: BLE001 — o erro precisa chegar à tela
            self._set_status("erro", message=f"Falha ao consultar as palavras-chave do Google Ads: {e}", action=ACAO_CREDENCIAIS)
            return []


CANAL_CAMPANHA = {"PERFORMANCE_MAX": "Performance Max", "SEARCH": "Pesquisa", "DISPLAY": "Display",
                  "VIDEO": "Vídeo", "DEMAND_GEN": "Demanda", "SHOPPING": "Shopping"}
OUTROS_TERMOS = "Outros termos (agrupados pelo Google)"


class GoogleTermosExtractor(GoogleInsightsExtractor):
    """
    O que as pessoas digitaram antes de ver o anúncio: o termo exato, por campanha e dia, com custo e
    conversões. Campanha de pesquisa vem de `search_term_view` e Performance Max de
    `campaign_search_term_view` — os dois entregam o termo de verdade (o recurso `campaign_search_term_insight`,
    usado antes, só devolve categorias agrupadas). O Google esconde os termos com pouquíssimo volume por
    privacidade, então a soma dos termos pode ficar abaixo do total da campanha.
    """

    CONSULTAS = (
        ("Pesquisa", "search_term_view", "searchTermView", "search_term_view.search_term"),
        ("Performance Max", "campaign_search_term_view", "campaignSearchTermView", "campaign_search_term_view.search_term"),
    )

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        faltando = self._faltando()
        if faltando:
            self._set_status("nao_configurado", message="Credenciais faltando: " + ", ".join(faltando) + ".", action=ACAO_CREDENCIAIS)
            return []
        try:
            import httpx

            linhas: List[Dict[str, Any]] = []
            with httpx.Client(timeout=90) as client:
                base = self._conectar(client)
                contas = self._contas(client, base)
                for inicio, fim in _fatias_mensais(start_date, end_date):
                    for canal, recurso, chave, campo in self.CONSULTAS:
                        query = (
                            "SELECT customer.id, customer.descriptive_name, campaign.id, campaign.name, "
                            f"campaign.advertising_channel_type, {campo}, segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, "
                            f"metrics.conversions FROM {recurso} WHERE segments.date BETWEEN '{inicio}' AND '{fim}'"
                        )
                        novas, _ = self._por_conta(
                            client, base, contas, query, lambda r, canal=canal, chave=chave: google_termo_row(canal, chave, r)
                        )
                        # O campaign_search_term_view também devolve campanhas de pesquisa (já vindas do search_term_view):
                        # cada recurso fica com o seu tipo de campanha, para o mesmo termo não entrar duas vezes
                        linhas += [
                            l for l in novas
                            if l["termo"] and (l["impressoes"] or l["cliques"])
                            and ((l["canal"] == "Performance Max") == (recurso == "campaign_search_term_view"))
                        ]
            termos = len({l["termo"] for l in linhas})
            self._set_status(
                "real", len(linhas),
                f"{termos} termo(s) de pesquisa reais, com custo e conversões por dia, segundo o Google. "
                "O Google omite os termos com pouquíssimo volume.",
            )
            return linhas
        except Exception as e:  # noqa: BLE001 — o erro precisa chegar à tela
            self._set_status("erro", message=f"Falha ao consultar os termos de pesquisa do Google Ads: {e}",
                             action=ACAO_CREDENCIAIS)
            return []


def google_termo_row(canal: str, chave: str, row: Dict[str, Any]) -> Dict[str, Any]:
    customer = row.get("customer") or {}
    campaign = row.get("campaign") or {}
    tipo = campaign.get("advertisingChannelType")
    canal = CANAL_CAMPANHA.get(tipo, tipo) or canal
    metrics = row.get("metrics") or {}
    data = str((row.get("segments") or {}).get("date") or "")[:10]
    return {
        "plataforma": "google",
        "conta_id": str(customer.get("id") or ""),
        "conta_nome": customer.get("descriptiveName"),
        "campanha_id": str(campaign.get("id") or ""),
        "campanha_nome": campaign.get("name"),
        "canal": canal,
        "termo": ((row.get(chave) or {}).get("searchTerm") or "").strip().lower(),
        "data": data,
        "mes": data[:7],
        "investimento": round(int(metrics.get("costMicros") or 0) / 1_000_000, 2),
        "impressoes": int(metrics.get("impressions") or 0),
        "cliques": int(metrics.get("clicks") or 0),
        "conversoes": round(float(metrics.get("conversions") or 0), 2),
    }


FORCA_ANUNCIO = {"EXCELLENT": "Excelente", "GOOD": "Boa", "AVERAGE": "Média", "POOR": "Ruim", "PENDING": "Pendente",
                 "NO_ADS": "Sem anúncios"}


class GoogleAnunciosExtractor(GoogleInsightsExtractor):
    """
    Os anúncios do Google, por dia: o anúncio responsivo de pesquisa (com os títulos) e, no Performance
    Max, o grupo de recursos — que é o "anúncio" dessa campanha (cada um com seus textos e imagens).
    """

    def _consultas(self, inicio: str, fim: str):
        periodo = f"segments.date BETWEEN '{inicio}' AND '{fim}'"
        metricas = "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions"
        base = "customer.id, customer.descriptive_name, campaign.id, campaign.name"
        return (
            ("Pesquisa", f"SELECT {base}, ad_group.name, ad_group_ad.ad.id, ad_group_ad.ad.responsive_search_ad.headlines, "
                         f"segments.date, {metricas} FROM ad_group_ad WHERE {periodo} AND metrics.impressions > 0",
             google_anuncio_pesquisa_row),
            ("Performance Max", f"SELECT {base}, asset_group.id, asset_group.name, asset_group.ad_strength, "
                                f"segments.date, {metricas} FROM asset_group WHERE {periodo} AND metrics.impressions > 0",
             google_anuncio_pmax_row),
        )

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        faltando = self._faltando()
        if faltando:
            self._set_status("nao_configurado", message="Credenciais faltando: " + ", ".join(faltando) + ".", action=ACAO_CREDENCIAIS)
            return []
        try:
            import httpx

            linhas: List[Dict[str, Any]] = []
            with httpx.Client(timeout=90) as client:
                base = self._conectar(client)
                contas = self._contas(client, base)
                for inicio, fim in _fatias_mensais(start_date, end_date):
                    for canal, query, converter in self._consultas(inicio, fim):
                        novas, _ = self._por_conta(client, base, contas, query, lambda r, c=canal, f=converter: f(c, r))
                        linhas += novas
            anuncios = len({(l["campanha_id"], l["anuncio_id"]) for l in linhas})
            self._set_status("real", len(linhas),
                             f"{anuncios} anúncio(s) do Google (pesquisa e grupos de recursos do Performance Max), por dia.")
            return linhas
        except Exception as e:  # noqa: BLE001
            self._set_status("erro", message=f"Falha ao consultar os anúncios do Google Ads: {e}", action=ACAO_CREDENCIAIS)
            return []


def _campos_google(row: Dict[str, Any], canal: str) -> Dict[str, Any]:
    customer, campaign, metrics = row.get("customer") or {}, row.get("campaign") or {}, row.get("metrics") or {}
    return {
        "plataforma": "google",
        "conta_id": str(customer.get("id") or ""),
        "conta_nome": customer.get("descriptiveName"),
        "campanha_id": str(campaign.get("id") or ""),
        "campanha_nome": campaign.get("name"),
        "canal": canal,
        "data": str((row.get("segments") or {}).get("date") or "")[:10],
        "investimento": round(int(metrics.get("costMicros") or 0) / 1_000_000, 2),
        "impressoes": int(metrics.get("impressions") or 0),
        "cliques": int(metrics.get("clicks") or 0),
        "conversoes": round(float(metrics.get("conversions") or 0), 2),
    }


def google_anuncio_pesquisa_row(canal: str, row: Dict[str, Any]) -> Dict[str, Any]:
    ad = (row.get("adGroupAd") or {}).get("ad") or {}
    titulos = [h.get("text") for h in ((ad.get("responsiveSearchAd") or {}).get("headlines") or []) if h.get("text")]
    return {
        **_campos_google(row, canal),
        "grupo_nome": (row.get("adGroup") or {}).get("name"),
        "anuncio_id": str(ad.get("id") or ""),
        "anuncio_nome": " | ".join(titulos[:3]) or f"Anúncio {ad.get('id')}",
        "forca": None,
    }


def google_anuncio_pmax_row(canal: str, row: Dict[str, Any]) -> Dict[str, Any]:
    grupo = row.get("assetGroup") or {}
    return {
        **_campos_google(row, canal),
        "grupo_nome": grupo.get("name"),
        "anuncio_id": str(grupo.get("id") or ""),
        "anuncio_nome": grupo.get("name"),
        "forca": FORCA_ANUNCIO.get(grupo.get("adStrength"), grupo.get("adStrength")),
    }


DISPOSITIVO = {"MOBILE": "Celular", "DESKTOP": "Computador", "TABLET": "Tablet", "CONNECTED_TV": "TV", "OTHER": "Outro"}


class GoogleDetalhesExtractor(GoogleInsightsExtractor):
    """
    Três recortes do Google que explicam o resultado, por campanha e dia: quais ações de conversão
    (formulário, clique no WhatsApp...), o aparelho e a participação de impressões (quanto se perdeu
    por orçamento e por ranking). Tudo na mesma base, separado pelo campo `tipo`.
    """

    def _consultas(self, inicio: str, fim: str):
        periodo = f"segments.date BETWEEN '{inicio}' AND '{fim}'"
        base = "customer.id, customer.descriptive_name, campaign.id, campaign.name, segments.date"
        return (
            ("conversao", f"SELECT {base}, segments.conversion_action_name, segments.conversion_action_category, "
                          f"metrics.conversions, metrics.all_conversions FROM campaign WHERE {periodo} AND metrics.all_conversions > 0"),
            ("dispositivo", f"SELECT {base}, segments.device, metrics.impressions, metrics.clicks, metrics.cost_micros, "
                            f"metrics.conversions FROM campaign WHERE {periodo} AND metrics.impressions > 0"),
            ("participacao", f"SELECT {base}, metrics.impressions, metrics.search_impression_share, "
                             "metrics.search_budget_lost_impression_share, metrics.search_rank_lost_impression_share "
                             f"FROM campaign WHERE {periodo} AND metrics.impressions > 0"),
        )

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        faltando = self._faltando()
        if faltando:
            self._set_status("nao_configurado", message="Credenciais faltando: " + ", ".join(faltando) + ".", action=ACAO_CREDENCIAIS)
            return []
        try:
            import httpx

            linhas: List[Dict[str, Any]] = []
            with httpx.Client(timeout=90) as client:
                base = self._conectar(client)
                contas = self._contas(client, base)
                for inicio, fim in _fatias_mensais(start_date, end_date):
                    for tipo, query in self._consultas(inicio, fim):
                        novas, _ = self._por_conta(client, base, contas, query, lambda r, t=tipo: google_detalhe_row(t, r))
                        linhas += novas
            self._set_status("real", len(linhas),
                             "Conversões por ação, aparelho e participação de impressões do Google, por campanha e dia.")
            return linhas
        except Exception as e:  # noqa: BLE001
            self._set_status("erro", message=f"Falha ao consultar os detalhes do Google Ads: {e}", action=ACAO_CREDENCIAIS)
            return []


def _fracao(valor: Any) -> Optional[float]:
    """Participação de impressões: o Google manda número, ou texto como '< 0.1' quando é muito pequena."""
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def google_detalhe_row(tipo: str, row: Dict[str, Any]) -> Dict[str, Any]:
    metrics, segments = row.get("metrics") or {}, row.get("segments") or {}
    linha = {**_campos_google(row, "Google"), "tipo": tipo}
    if tipo == "conversao":
        linha.update(
            acao=segments.get("conversionActionName"), categoria=segments.get("conversionActionCategory"),
            conversoes=round(float(metrics.get("conversions") or 0), 2),
            todas_conversoes=round(float(metrics.get("allConversions") or 0), 2),
        )
    elif tipo == "dispositivo":
        linha["dispositivo"] = DISPOSITIVO.get(segments.get("device"), segments.get("device"))
    else:
        linha.update(
            participacao=_fracao(metrics.get("searchImpressionShare")),
            perdida_orcamento=_fracao(metrics.get("searchBudgetLostImpressionShare")),
            perdida_ranking=_fracao(metrics.get("searchRankLostImpressionShare")),
        )
    return linha


# ---------------------------------------------------------------------------
# Meta — nível anúncio (auditoria de anúncios)
# ---------------------------------------------------------------------------


def meta_anuncio_row(conta: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    """Linha do /insights no nível anúncio: os campos da campanha mais conjunto e anúncio."""
    row = meta_insight_row(conta, item)
    row.update(
        conjunto_id=item.get("adset_id"),
        conjunto_nome=item.get("adset_name"),
        anuncio_id=item.get("ad_id"),
        anuncio_nome=item.get("ad_name"),
        alcance=int(float(item.get("reach") or 0)),
    )
    return row


class MetaAnunciosExtractor(MetaInsightsExtractor):
    """Investimento e resultados de cada anúncio, por dia, com miniatura e status do anúncio."""

    CAMPOS = "ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name,spend,impressions,clicks,reach,actions"

    def _ler_fatia(self, client, base: str, token: dict, conta: Dict[str, Any], inicio: str, fim: str) -> tuple:
        """
        Insights por anúncio e dia de uma fatia do período. Quando a Meta responde "unknown error" (pedido pesado), repete e, se continuar,
        divide a fatia ao meio e lê cada metade: uma fatia ruim não derruba o resto da conta. Devolve (linhas, fatias que não foi possível ler).
        """
        ultimo_erro: Optional[Exception] = None
        for tentativa in range(3):
            try:
                itens = self._paginate(
                    client,
                    f"{base}/{conta['id']}/insights",
                    {"level": "ad", "time_increment": 1, "time_range": json.dumps({"since": inicio, "until": fim}),
                     "fields": self.CAMPOS, "limit": 200 if tentativa else 500, **token},
                )
                return [meta_anuncio_row(conta, item) for item in itens], []
            except RuntimeError as e:
                if "expirado" in str(e):
                    raise
                ultimo_erro = e
                time.sleep(2 * (tentativa + 1))
        d0, d1 = datetime.fromisoformat(inicio), datetime.fromisoformat(fim)
        if (d1 - d0).days >= 6:
            meio = d0 + (d1 - d0) / 2
            a_linhas, a_falhas = self._ler_fatia(client, base, token, conta, inicio, meio.date().isoformat())
            b_linhas, b_falhas = self._ler_fatia(client, base, token, conta, (meio + timedelta(days=1)).date().isoformat(), fim)
            return a_linhas + b_linhas, a_falhas + b_falhas
        return [], [f"{inicio} a {fim} ({str(ultimo_erro)[:60]})"]

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        if not self.access_token:
            self._set_status("nao_configurado", message="META_ACCESS_TOKEN não configurado.", action=ACAO_META_INSIGHTS)
            return []
        try:
            import httpx

            base = f"https://graph.facebook.com/{META_GRAPH_VERSION}"
            token = {"access_token": self.access_token}
            linhas: List[Dict[str, Any]] = []
            criativos: Dict[str, Dict[str, Any]] = {}
            contas_com_erro: List[str] = []
            with httpx.Client(timeout=120) as client:
                if self.account_ids:
                    contas = [
                        self._get(client, f"{base}/{i if i.startswith('act_') else 'act_' + i}", {"fields": "id,name", **token})
                        for i in self.account_ids
                    ]
                else:
                    contas = self._paginate(client, f"{base}/me/adaccounts", {"fields": "id,name", "limit": 200, **token})

                for conta in contas:
                    perdidas: List[str] = []
                    try:
                        for inicio, fim in _fatias_mensais(to_naive_utc(start_date), to_naive_utc(end_date)):
                            novas, faltou = self._ler_fatia(client, base, token, conta, inicio, fim)
                            linhas.extend(novas)
                            perdidas.extend(faltou)
                        lista_ok = False
                        for limite in (200, 50, 20):  # "unknown error" da Meta costuma ser pedido grande demais: tenta de novo com páginas menores
                            try:
                                for anuncio in self._paginate(
                                    client,
                                    f"{base}/{conta['id']}/ads",
                                    {"fields": "id,effective_status,creative{thumbnail_url}", "limit": limite, **token},
                                ):
                                    criativos[anuncio["id"]] = {
                                        "status": anuncio.get("effective_status"),
                                        "miniatura": (anuncio.get("creative") or {}).get("thumbnail_url"),
                                    }
                                lista_ok = True
                                break
                            except RuntimeError as e:
                                if "expirado" in str(e):
                                    raise
                                time.sleep(3)
                        if not lista_ok:
                            perdidas.append("lista de anúncios e miniaturas")
                    except RuntimeError as e:
                        if "expirado" in str(e):
                            raise
                        contas_com_erro.append(f"{conta.get('name') or conta['id']}: {e}")
                    if perdidas:
                        contas_com_erro.append(f"{conta.get('name') or conta['id']} (parcial, faltou: {', '.join(perdidas)})")

            if contas and len(contas_com_erro) == len(contas):
                raise RuntimeError("; ".join(contas_com_erro))
            for linha in linhas:
                linha.update(criativos.get(linha["anuncio_id"]) or {"status": None, "miniatura": None})

            anuncios = len({l["anuncio_id"] for l in linhas})
            leads = sum(l["leads_plataforma"] for l in linhas)
            invest = sum(l["investimento"] for l in linhas)
            aviso = f" Contas não lidas: {'; '.join(contas_com_erro)}." if contas_com_erro else ""
            self._set_status(
                "real",
                len(linhas),
                f"{len(contas)} conta(s): {anuncios} anúncio(s), {leads} leads e {_reais(invest)} investidos no período, "
                f"segundo a Meta.{aviso}",
            )
            return linhas
        except Exception as e:
            self._set_status("erro", message=str(e), action=ACAO_META_INSIGHTS)
            return []
