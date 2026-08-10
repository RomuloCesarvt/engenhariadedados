"""
Conversões do CV (API CVDW): uma linha por vez que o lead converteu, com a mídia, a origem e o
empreendimento DAQUELA conversão.

É a mesma tabela de fatos de onde o Power BI da gestão tira MQL e origem. O endpoint comum de leads
(`/api/cvio/lead`) só traz a ÚLTIMA conversão do lead, o que perde a origem de cada vez que ele voltou
a converter — e foi essa a causa de o nosso MQL por origem não bater com o BI.

O CVDW devolve páginas de 30 registros, do mais antigo para o mais novo, e limita as requisições:
por isso a leitura vai do fim para trás, devagar, com espera quando o CV pede (HTTP 429), e as próximas
atualizações só baixam o que é mais novo que o já guardado.
"""

import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from engine.extractors.base import StatusMixin, to_naive_utc
from engine.extractors.cv_crm import CVCRMExtractor, cv_error_message

PAUSA_ENTRE_PAGINAS = 1.3  # o CV bloqueia (HTTP 429) quando a leitura passa de ~1 página por segundo; mais devagar sai mais rápido no total
PAGINAS_POR_CHECKPOINT = 40
ESPERAS_429 = (20, 40, 60, 90, 120)
PAGINAS_ANTIGAS_PARA_PARAR = 4


class CVConversoesExtractor(StatusMixin):
    source_key = "cv_crm"

    def __init__(self):
        self.cv = CVCRMExtractor()
        self.status = None

    def _pagina(self, client, pagina: int) -> Dict[str, Any]:
        url = f"{self.cv.api_url}/api/v1/cvdw/leads/conversoes"
        for espera in (0,) + ESPERAS_429:
            if espera:
                time.sleep(espera)
            res = client.get(url, headers=self.cv._headers(), params={"pagina": pagina, "registros": 30})
            if res.status_code == 200:
                return res.json()
            if res.status_code != 429:
                raise RuntimeError(cv_error_message(res))
        raise RuntimeError("O CV recusou as requisições por excesso (HTTP 429) mesmo depois de esperar.")

    def fetch(self, start_date: datetime, end_date: datetime, anteriores: Optional[List[Dict[str, Any]]] = None,
              ao_progresso: Optional[Callable[[List[Dict[str, Any]]], None]] = None) -> List[Dict[str, Any]]:
        if not (self.cv.api_url and self.cv.token and self.cv.email):
            self._set_status(
                "nao_configurado",
                message="CV_CRM_URL, CV_CRM_TOKEN e CV_CRM_EMAIL são necessários para ler as conversões.",
                action="Preencha as credenciais do CV em engine/.env.",
            )
            return []
        try:
            import httpx

            guardadas = {int(r["idlead_conversao"]): r for r in (anteriores or []) if r.get("idlead_conversao") is not None}
            maior_guardado = max(guardadas, default=0)
            menor_guardado = min(guardadas, default=0)
            menor_data = min((str(r.get("data_cad") or "9999")[:10] for r in guardadas.values()), default="9999")
            inicio = to_naive_utc(start_date).strftime("%Y-%m-%d")
            # O guardado só precisa de passado se começa bem depois do início pedido (uma semana de folga: o ano pode não ter conversão no 1º dia)
            falta_passado = bool(guardadas) and menor_data > (datetime.fromisoformat(inicio) + timedelta(days=7)).strftime("%Y-%m-%d")
            novas: Dict[int, Dict[str, Any]] = {}
            lidas = 0

            def ler(client, de_pagina: int, ate_pagina: int, parar_no_guardado: bool) -> None:
                nonlocal lidas
                antigas = 0
                for pagina in range(de_pagina, ate_pagina - 1, -1):
                    registros = self._pagina(client, pagina).get("dados") or []
                    for r in registros:
                        if r.get("idlead_conversao") is not None:
                            novas[int(r["idlead_conversao"])] = r
                    ids = [int(r["idlead_conversao"]) for r in registros if r.get("idlead_conversao") is not None]
                    datas = [str(r.get("data_cad") or "")[:10] for r in registros]
                    # Leitura do fim: já temos tudo daqui para trás quando a página inteira é mais antiga que o guardado
                    if parar_no_guardado and maior_guardado and ids and max(ids) <= maior_guardado:
                        return
                    antigas = antigas + 1 if datas and max(datas) < inicio else 0
                    if antigas >= PAGINAS_ANTIGAS_PARA_PARAR:
                        return
                    lidas += 1
                    if ao_progresso and lidas % PAGINAS_POR_CHECKPOINT == 0:
                        ao_progresso(sorted({**guardadas, **novas}.values(), key=lambda r: r["idlead_conversao"]))
                    time.sleep(PAUSA_ENTRE_PAGINAS)

            with httpx.Client(timeout=90, follow_redirects=True) as client:
                total = int(self._pagina(client, 1).get("total_de_paginas") or 0)
                # 1) sempre o fim: o que é mais novo que o guardado (é o que as telas mais usam)
                ler(client, total, 1, True)
                # 2) depois, se o guardado não chega ao início pedido, retoma antes do mais antigo que já temos.
                #    Os ids crescem com as páginas, então uma busca binária acha a página certa sem reler tudo.
                if falta_passado:
                    baixo, alto = 1, total
                    while baixo < alto:
                        meio = (baixo + alto + 1) // 2
                        ids_meio = [int(r["idlead_conversao"]) for r in (self._pagina(client, meio).get("dados") or []) if r.get("idlead_conversao") is not None]
                        if ids_meio and max(ids_meio) < menor_guardado:
                            baixo = meio
                        else:
                            alto = meio - 1
                        time.sleep(PAUSA_ENTRE_PAGINAS)
                    ler(client, baixo, 1, False)

            todas = {**guardadas, **novas}
            corte = inicio
            linhas = sorted((r for r in todas.values() if str(r.get("data_cad") or "")[:10] >= corte), key=lambda r: r["idlead_conversao"])
            self._set_status(
                "real", len(linhas),
                f"{len(linhas)} conversão(ões) de leads desde {inicio} ({len(novas)} lidas agora), com a mídia e o empreendimento de cada uma.",
            )
            return linhas
        except Exception as e:  # noqa: BLE001 — o erro precisa chegar à tela
            self._set_status("erro", message=f"Falha ao ler as conversões do CV: {e}",
                             action="Confira o token do CV e tente atualizar de novo em alguns minutos (o CV limita as requisições).")
            return []
