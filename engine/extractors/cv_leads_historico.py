"""
Histórico de situações dos leads do CV (CVDW: /api/v1/cvdw/leads/historico/situacoes).

Cada linha é uma mudança de situação ("Novo Lead (MQL)" -> "Em atendimento IA" -> "Lead Qualificado (SQL)" ...) com a data e a hora.
É a tabela que o Power BI da gestão usa para contar SQL no dia em que o lead foi qualificado.

Leitura incremental: a primeira vez baixa uns 150 dias; as seguintes só leem o que é mais novo que o guardado (menos um dia, por segurança).
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from engine.extractors.base import StatusMixin, to_naive_utc
from engine.extractors.cv_crm import CVCRMExtractor, cv_error_message

PAUSA_ENTRE_PAGINAS = 0.5
ESPERAS_429 = (20, 40, 60, 90, 120)
POR_PAGINA = 500
CAMPOS = ("idhistorico", "idlead", "data_cad", "referencia_data", "de", "para", "de_nome", "para_nome")


class CVLeadsHistoricoExtractor(StatusMixin):
    source_key = "cv_crm"

    def __init__(self):
        self.cv = CVCRMExtractor()
        self.status = None

    def _pagina(self, client, pagina: int, a_partir: str) -> Dict[str, Any]:
        url = f"{self.cv.api_url}/api/v1/cvdw/leads/historico/situacoes"
        params = {"pagina": pagina, "registros_por_pagina": POR_PAGINA, "a_partir_data_referencia": a_partir}
        for espera in (0,) + ESPERAS_429:
            if espera:
                time.sleep(espera)
            res = client.get(url, headers=self.cv._headers(), params=params)
            if res.status_code == 200:
                return res.json()
            if res.status_code != 429:
                raise RuntimeError(cv_error_message(res))
        raise RuntimeError("O CV recusou as requisições por excesso (HTTP 429) mesmo depois de esperar.")

    def fetch(self, start_date: datetime, end_date: datetime, anteriores: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        if not (self.cv.api_url and self.cv.token and self.cv.email):
            self._set_status("nao_configurado", message="CV_CRM_URL, CV_CRM_TOKEN e CV_CRM_EMAIL são necessários.", action="Preencha as credenciais do CV em engine/.env.")
            return []
        try:
            import httpx

            guardados = {int(r["idhistorico"]): r for r in (anteriores or []) if r.get("idhistorico") is not None}
            ultima = max((str(r.get("referencia_data") or "") for r in guardados.values()), default="")
            if ultima:
                a_partir = (datetime.fromisoformat(ultima[:10]) - timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                a_partir = (to_naive_utc(end_date) - timedelta(days=150)).strftime("%Y-%m-%d")
            novos: Dict[int, Dict[str, Any]] = {}
            with httpx.Client(timeout=120, follow_redirects=True) as client:
                primeira = self._pagina(client, 1, a_partir)
                total = int(primeira.get("total_de_paginas") or 0)
                for pagina in range(1, total + 1):
                    dados = (primeira if pagina == 1 else self._pagina(client, pagina, a_partir)).get("dados") or []
                    for r in dados:
                        if r.get("idhistorico") is not None:
                            novos[int(r["idhistorico"])] = {c: r.get(c) for c in CAMPOS}
                    time.sleep(PAUSA_ENTRE_PAGINAS)
            todos = {**guardados, **novos}
            linhas = sorted(todos.values(), key=lambda r: str(r.get("referencia_data") or ""))
            self._set_status("real", len(linhas), f"{len(linhas)} mudança(s) de situação de leads ({len(novos)} lidas agora), com a data de cada uma.")
            return linhas
        except Exception as e:  # noqa: BLE001
            self._set_status("erro", message=f"Falha ao ler o histórico de situações dos leads: {e}",
                             action="Confira o token do CV e tente de novo em alguns minutos (o CV limita as requisições).")
            return []
