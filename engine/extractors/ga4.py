"""
Google Analytics 4 — o que acontece no site: palavras buscadas, origem das sessões, dispositivo e
cidade de quem entra.

São três relatórios, todos por dia, para que o período escolhido na tela valha exatamente e dê para
comparar com o período anterior:

  1. palavras (`ga4_palavras`): a palavra do Google Ads (`sessionGoogleAdsKeyword`) e o utm_term
     (`sessionManualTerm`) de cada sessão, por mês, campanha e página de entrada;
  2. tráfego (`ga4_trafego`): página de entrada × canal × origem/mídia × dispositivo;
  3. cidades (`ga4_cidades`): página de entrada × cidade × estado.

A página de entrada é o que liga a sessão ao empreendimento ("/empreendimento/reserva-dos-ipes").
Quem entra pela home ou pelo blog não diz qual produto procurava — isso fica dito, não chutado.

O que o GA4 NÃO tem: a palavra da busca orgânica do Google (isso só existe no Search Console).

Credenciais (engine/.env), nesta ordem:
  1. conta de serviço: GA4_CREDENTIALS_PATH com o JSON da chave (dê acesso de leitura à
     propriedade em Administrador → Acesso à propriedade);
  2. OAuth do próprio usuário: GA4_CLIENT_ID, GA4_CLIENT_SECRET e GA4_REFRESH_TOKEN (escopo
     analytics.readonly). Sem eles, valem os do Google Ads (GOOGLE_ADS_CLIENT_ID e companhia).
E GA4_PROPERTY_IDS: o ID numérico da propriedade (Administrador → Detalhes da propriedade).
"""

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from engine.extractors.base import StatusMixin, to_naive_utc

API = "https://analyticsdata.googleapis.com/v1beta"
ESCOPO = "https://www.googleapis.com/auth/analytics.readonly"
MAX_PAGINAS = 40
LINHAS_POR_PAGINA = 100_000
ACAO = ("Preencha no engine/.env: GA4_PROPERTY_IDS (ID numérico da propriedade) e a credencial "
        "(GA4_CREDENTIALS_PATH com o JSON da conta de serviço, ou GA4_CLIENT_ID / GA4_CLIENT_SECRET / "
        "GA4_REFRESH_TOKEN). A conta precisa de acesso de leitura à propriedade.")

# Valores que o GA4 usa quando não há palavra: não viram linha
SEM_PALAVRA = {"(not set)", "(not provided)", "(none)", "", "(direct)"}
# utm_term nem sempre traz palavra: vem o ID do anúncio (só números) ou a variável do Google/Meta
# que não foi substituída ("{keyword}", "{{adset.name}}"). Nada disso é palavra buscada.
RE_NAO_E_PALAVRA = re.compile(r"^[\d\s.\-_]+$|[{}]")
# O que sobra quando a UTM foi montada errada: o nome da variável, um "null" do site, uma letra solta
LIXO = {"null", "undefined", "keyword", "keywords", "term", "termo", "none", "n/a", "na", "teste", "test"}

# O GA4 devolve o que não sabe como "(not set)"; na tela isso vira um rótulo em português
NAO_INFORMADO = "Não informado"
DISPOSITIVOS = {"mobile": "Celular", "desktop": "Computador", "tablet": "Tablet"}


def e_palavra(texto: str) -> bool:
    limpo = (texto or "").strip().lower()
    if len(limpo) < 3 or limpo in LIXO or limpo in SEM_PALAVRA:
        return False
    return not RE_NAO_E_PALAVRA.search(limpo)


def _ids() -> List[str]:
    bruto = os.getenv("GA4_PROPERTY_IDS") or os.getenv("GA4_PROPERTY_ID") or ""
    return [i.strip().replace("properties/", "") for i in bruto.split(",") if i.strip()]


def _valor(texto: str) -> Optional[str]:
    """O que veio na dimensão, ou None quando o GA4 diz que não sabe."""
    limpo = (texto or "").strip()
    return None if limpo in SEM_PALAVRA else limpo


def _dia(texto: str) -> str:
    """A data do GA4 ("20260905") no formato do resto do sistema."""
    return f"{texto[:4]}-{texto[4:6]}-{texto[6:8]}" if len(texto) == 8 and texto.isdigit() else texto


def _int(valor: str) -> int:
    return int(round(float(valor or 0)))


def linha_palavra(propriedade: str, dimensoes: List[str], metricas: List[str]) -> Dict[str, Any]:
    """Uma linha do runReport vira o registro da base."""
    ads, manual, campanha, pagina, mes = dimensoes
    paga = ads.strip() not in SEM_PALAVRA
    return {
        "plataforma": "ga4",
        "propriedade": propriedade,
        "palavra": (ads if paga else manual).strip(),
        "tipo": "Google Ads" if paga else "UTM (utm_term)",
        "campanha_nome": campanha if campanha not in SEM_PALAVRA else None,
        "pagina_entrada": pagina if pagina not in SEM_PALAVRA else None,
        "mes": f"{mes[:4]}-{mes[4:]}" if len(mes) == 6 else mes,
        "sessoes": int(float(metricas[0] or 0)),
        "usuarios": int(float(metricas[1] or 0)),
        "conversoes": int(round(float(metricas[2] or 0))),
    }


def linha_trafego(propriedade: str, dimensoes: List[str], metricas: List[str]) -> Dict[str, Any]:
    """Página de entrada × canal × origem/mídia × dispositivo, num dia."""
    dia, pagina, canal, origem, dispositivo = dimensoes
    return {
        "plataforma": "ga4",
        "propriedade": propriedade,
        "data": _dia(dia),
        "pagina_entrada": _valor(pagina),
        "canal": _valor(canal) or NAO_INFORMADO,
        "origem_midia": _valor(origem) or NAO_INFORMADO,
        "dispositivo": DISPOSITIVOS.get((dispositivo or "").strip().lower(), _valor(dispositivo) or NAO_INFORMADO),
        "sessoes": _int(metricas[0]),
        "usuarios": _int(metricas[1]),
        "novos_usuarios": _int(metricas[2]),
        "sessoes_engajadas": _int(metricas[3]),
        "conversoes": _int(metricas[4]),
        "tempo_engajamento": _int(metricas[5]),
    }


def linha_cidade(propriedade: str, dimensoes: List[str], metricas: List[str]) -> Dict[str, Any]:
    """Página de entrada × cidade × estado, num dia."""
    dia, pagina, cidade, estado = dimensoes
    return {
        "plataforma": "ga4",
        "propriedade": propriedade,
        "data": _dia(dia),
        "pagina_entrada": _valor(pagina),
        "cidade": _valor(cidade) or NAO_INFORMADO,
        "estado": _valor(estado) or NAO_INFORMADO,
        "sessoes": _int(metricas[0]),
        "usuarios": _int(metricas[1]),
        "sessoes_engajadas": _int(metricas[2]),
        "conversoes": _int(metricas[3]),
    }


class _GA4Extractor(StatusMixin):
    """O que todo relatório do GA4 precisa: credencial, token e paginação."""

    source_key = "ga4"

    def __init__(self):
        self.propriedades = _ids()
        self.credenciais = os.getenv("GA4_CREDENTIALS_PATH") or ""
        self.client_id = os.getenv("GA4_CLIENT_ID") or os.getenv("GOOGLE_ADS_CLIENT_ID") or ""
        self.client_secret = os.getenv("GA4_CLIENT_SECRET") or os.getenv("GOOGLE_ADS_CLIENT_SECRET") or ""
        self.refresh_token = os.getenv("GA4_REFRESH_TOKEN") or os.getenv("GOOGLE_ADS_REFRESH_TOKEN") or ""
        self.status = None

    def _faltando(self) -> List[str]:
        faltando = []
        if not self.propriedades:
            faltando.append("GA4_PROPERTY_IDS")
        tem_conta = bool(self.credenciais and os.path.exists(self.credenciais))
        tem_oauth = bool(self.client_id and self.client_secret and self.refresh_token)
        if not (tem_conta or tem_oauth):
            faltando.append("GA4_CREDENTIALS_PATH (conta de serviço) ou GA4_CLIENT_ID / GA4_CLIENT_SECRET / GA4_REFRESH_TOKEN")
        return faltando

    def _token(self, client) -> str:
        """Token de acesso: da conta de serviço, se houver; senão, do refresh token do usuário."""
        if self.credenciais and os.path.exists(self.credenciais):
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account

            cred = service_account.Credentials.from_service_account_file(self.credenciais, scopes=[ESCOPO])
            cred.refresh(Request())
            return cred.token
        res = client.post("https://oauth2.googleapis.com/token", data={
            "grant_type": "refresh_token", "client_id": self.client_id,
            "client_secret": self.client_secret, "refresh_token": self.refresh_token,
        })
        if res.status_code != 200:
            raise RuntimeError(f"Falha ao renovar o token OAuth ({res.status_code}): {res.text[:160]}")
        return res.json()["access_token"]

    def _paginas(self, client, headers: dict, propriedade: str, inicio: str, fim: str,
                 dimensoes: List[str], metricas: List[str]):
        """Todas as linhas do relatório, já paginadas."""
        deslocamento = 0
        for _ in range(MAX_PAGINAS):
            corpo = {
                "dateRanges": [{"startDate": inicio, "endDate": fim}],
                "dimensions": [{"name": d} for d in dimensoes],
                "metrics": [{"name": m} for m in metricas],
                "limit": LINHAS_POR_PAGINA,
                "offset": deslocamento,
                "keepEmptyRows": False,
            }
            res = client.post(f"{API}/properties/{propriedade}:runReport", headers=headers, json=corpo)
            if res.status_code != 200:
                raise RuntimeError(_mensagem_erro(res, propriedade))
            dados = res.json()
            for linha in dados.get("rows") or []:
                yield ([v.get("value", "") for v in linha.get("dimensionValues") or []],
                       [v.get("value", "0") for v in linha.get("metricValues") or []])
            deslocamento += LINHAS_POR_PAGINA
            if deslocamento >= int(dados.get("rowCount") or 0):
                break

    def _coletar(self, start_date: datetime, end_date: datetime, dimensoes: List[str], metricas: List[str],
                 montar, resumo) -> List[Dict[str, Any]]:
        faltando = self._faltando()
        if faltando:
            self._set_status("nao_configurado", message="Credenciais faltando: " + ", ".join(faltando) + ".", action=ACAO)
            return []
        try:
            import httpx

            inicio = to_naive_utc(start_date).strftime("%Y-%m-%d")
            fim = to_naive_utc(end_date).strftime("%Y-%m-%d")
            linhas: List[Dict[str, Any]] = []
            with httpx.Client(timeout=120) as client:
                headers = {"Authorization": f"Bearer {self._token(client)}", "Content-Type": "application/json"}
                for propriedade in self.propriedades:
                    for dims, mets in self._paginas(client, headers, propriedade, inicio, fim, dimensoes, metricas):
                        registro = montar(propriedade, dims, mets)
                        if registro is not None:
                            linhas.append(registro)
            self._set_status("real", len(linhas), resumo(linhas))
            return linhas
        except Exception as e:  # noqa: BLE001 — o erro precisa chegar à tela
            self._set_status("erro", message=f"Falha ao consultar o Google Analytics: {e}", action=ACAO)
            return []


class GA4PalavrasExtractor(_GA4Extractor):
    DIMENSOES = ["sessionGoogleAdsKeyword", "sessionManualTerm", "sessionCampaignName",
                 "landingPagePlusQueryString", "yearMonth"]
    METRICAS = ["sessions", "activeUsers", "keyEvents"]

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        def montar(propriedade, dims, mets):
            registro = linha_palavra(propriedade, dims, mets)
            return registro if e_palavra(registro["palavra"]) else None

        def resumo(linhas):
            sessoes = sum(l["sessoes"] for l in linhas)
            palavras = len({l["palavra"] for l in linhas})
            return (f"{palavras} palavra(s) em {sessoes} sessão(ões) no período, segundo o Google Analytics. "
                    "A busca orgânica não traz palavra no GA4.")

        return self._coletar(start_date, end_date, self.DIMENSOES, self.METRICAS, montar, resumo)


class GA4TrafegoExtractor(_GA4Extractor):
    """De onde vêm as sessões e em que aparelho, por dia e por página de entrada."""

    DIMENSOES = ["date", "landingPage", "sessionDefaultChannelGroup", "sessionSourceMedium", "deviceCategory"]
    METRICAS = ["sessions", "activeUsers", "newUsers", "engagedSessions", "keyEvents", "userEngagementDuration"]

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        def resumo(linhas):
            sessoes = sum(l["sessoes"] for l in linhas)
            canais = len({l["canal"] for l in linhas})
            return f"{sessoes} sessão(ões) do site em {canais} canal(is), por dia, página de entrada e aparelho."

        return self._coletar(start_date, end_date, self.DIMENSOES, self.METRICAS, linha_trafego, resumo)


class GA4CidadesExtractor(_GA4Extractor):
    """De que cidade vêm as sessões, por dia e por página de entrada."""

    DIMENSOES = ["date", "landingPage", "city", "region"]
    METRICAS = ["sessions", "activeUsers", "engagedSessions", "keyEvents"]

    def fetch(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        def resumo(linhas):
            sessoes = sum(l["sessoes"] for l in linhas)
            cidades = len({l["cidade"] for l in linhas if l["cidade"] != NAO_INFORMADO})
            return f"{sessoes} sessão(ões) do site vindas de {cidades} cidade(s), por dia e página de entrada."

        return self._coletar(start_date, end_date, self.DIMENSOES, self.METRICAS, linha_cidade, resumo)


def _mensagem_erro(res, propriedade: str) -> str:
    try:
        erro = (res.json() or {}).get("error") or {}
    except Exception:  # noqa: BLE001 — resposta sem JSON
        erro = {}
    mensagem = erro.get("message") or f"HTTP {res.status_code}"
    if res.status_code == 403:
        mensagem += (f" (a credencial não tem acesso à propriedade {propriedade}: adicione o e-mail da conta de "
                     "serviço em Administrador → Acesso à propriedade, com permissão de leitura)")
    return mensagem
