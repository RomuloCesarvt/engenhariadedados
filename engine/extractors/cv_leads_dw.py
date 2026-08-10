"""
Leads do CV pela API CVDW, em ordem de última alteração: serve para contar SQL como o Power BI da gestão.

O endpoint comum de leads só mostra a situação de hoje; o CVDW devolve os leads do mais antigo para o mais recentemente
alterado, com a data da última alteração. Assim dá para contar quem foi movido para SQL (ou além) dentro de um período,
inclusive lead antigo que só agora foi qualificado — o que o BI conta como SQL do período.

Leitura do fim para trás, devagar e com espera quando o CV pede (HTTP 429); as atualizações seguintes só leem o que foi
alterado depois do que já está guardado.
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from engine.extractors.base import StatusMixin, to_naive_utc
from engine.extractors.cv_crm import CVCRMExtractor, cv_error_message

PAUSA_ENTRE_PAGINAS = 0.6
ESPERAS_429 = (20, 40, 60, 90, 120)
CAMPOS = ("idlead", "idempreendimento_ultimo", "idsituacao", "situacao", "idsituacao_anterior", "nome_situacao_anterior_lead",
          "data_cad", "data_ultima_alteracao", "referencia_data", "data_associacao_corretor")


class CVLeadsDWExtractor(StatusMixin):
    source_key = "cv_crm"

    def __init__(self):
        self.cv = CVCRMExtractor()
        self.status = None

    def _pagina(self, client, pagina: int) -> Dict[str, Any]:
        url = f"{self.cv.api_url}/api/v1/cvdw/leads"
        for espera in (0,) + ESPERAS_429:
            if espera:
                time.sleep(espera)
            res = client.get(url, headers=self.cv._headers(), params={"pagina": pagina, "registros": 30})
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

            guardados = {int(r["idlead"]): r for r in (anteriores or []) if r.get("idlead") is not None}
            ultima_guardada = max((str(r.get("referencia_data") or "") for r in guardados.values()), default="")
            # Com base guardada, relê um dia antes da última alteração (alterações do mesmo instante); sem ela, uns 120 dias
            corte = (ultima_guardada[:10] and (datetime.fromisoformat(ultima_guardada[:10]) - timedelta(days=1)).strftime("%Y-%m-%d")) or (
                to_naive_utc(end_date) - timedelta(days=120)).strftime("%Y-%m-%d")
            novos: Dict[int, Dict[str, Any]] = {}
            with httpx.Client(timeout=90, follow_redirects=True) as client:
                total = int(self._pagina(client, 1).get("total_de_paginas") or 0)
                antigas = 0
                for pagina in range(total, 0, -1):
                    registros = self._pagina(client, pagina).get("dados") or []
                    for r in registros:
                        if r.get("idlead") is not None:
                            novos[int(r["idlead"])] = {c: r.get(c) for c in CAMPOS}
                    datas = [str(r.get("referencia_data") or "")[:10] for r in registros]
                    antigas = antigas + 1 if datas and max(datas) < corte else 0
                    if antigas >= 2:
                        break
                    time.sleep(PAUSA_ENTRE_PAGINAS)
            todos = {**guardados, **novos}
            linhas = sorted(todos.values(), key=lambda r: str(r.get("referencia_data") or ""))
            self._set_status("real", len(linhas), f"{len(linhas)} lead(s) alterados recentemente no CV ({len(novos)} lidos agora), com a situação e a data da última alteração.")
            return linhas
        except Exception as e:  # noqa: BLE001
            self._set_status("erro", message=f"Falha ao ler os leads do CVDW: {e}",
                             action="Confira o token do CV e tente de novo em alguns minutos (o CV limita as requisições).")
            return []
