"""
Extrator CRM Construtor de Vendas (CV).

Usa a API "cvio" do CV:
  - GET /api/cvio/empreendimento  -> catálogo oficial de empreendimentos (só token)
  - GET /api/cvio/lead            -> leads (exige token + e-mail do usuário dono do token)
"""

import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from engine.config import CVLeadRecord, SourceStatus
from engine.extractors.base import BaseCVExtractor, in_period, to_naive_utc
from engine.normalizer import normalize_cv_lead, parse_datetime

REGISTROS_POR_PAGINA = 500

CAMPOS_INDICE = (
    "idlead", "data_cad", "email", "telefone", "nome", "idrd_station", "midia_principal", "midias", "origem",
    "situacao", "empreendimento", "link_interesses", "data_venda", "valor_venda", "ultima_data_conversao",
)


RESERVAS_PATH = "/api/v1/comercial/reservas"
RESERVAS_SIMULTANEAS = int(os.getenv("CV_RESERVAS_SIMULTANEAS", "10"))
RESERVAS_BLOCO_SEM_ID = 50  # quantos IDs seguidos sem reserva indicam que acabou


def valor_monetario(valor: Any) -> Optional[float]:
    """'93046.47', '93.046,47' ou '93046,47' -> 93046.47."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def reserva_enxuta(reserva: Dict[str, Any]) -> Dict[str, Any]:
    """Reserva do CV com o que o app usa: situação, venda, unidade, valores, corretor, mídia e lead."""
    unidade = reserva.get("unidade") or {}
    titular = reserva.get("titular") or {}
    corretor = reserva.get("corretor") or {}
    condicoes = reserva.get("condicoes") or {}
    situacao = reserva.get("situacao") or {}
    midia = reserva.get("midia")
    imobiliaria = reserva.get("imobiliaria") or {}
    return {
        "situacao": situacao.get("situacao"),
        "idsituacao": situacao.get("idsituacao"),
        "vendida": str(reserva.get("vendida") or "").upper() == "S",
        "data": reserva.get("data"),
        "data_venda": reserva.get("data_venda"),
        "data_contrato": reserva.get("data_contrato"),
        "data_cancelamento": reserva.get("data_cancelamento"),
        "data_distrato": reserva.get("data_distrato"),
        "empreendimento": unidade.get("empreendimento"),
        "idempreendimento": unidade.get("idempreendimento_cv"),
        "etapa": unidade.get("etapa"),
        "bloco": unidade.get("bloco"),
        "unidade": unidade.get("unidade"),
        "valor_contrato": valor_monetario(condicoes.get("valor_contrato")),
        "vgv_tabela": valor_monetario(condicoes.get("vgv_tabela")),
        "tipo_venda": reserva.get("tipovenda") or None,
        "midia": (midia.get("nome") or midia.get("midia")) if isinstance(midia, dict) else (midia or None),
        "corretor": corretor.get("corretor"),
        "imobiliaria": imobiliaria.get("nome") or corretor.get("imobiliaria"),
        "leads_associados": [
            str(l.get("idlead")) for l in reserva.get("leads_associados") or [] if isinstance(l, dict) and l.get("idlead")
        ],
        "idprecadastro": reserva.get("idprecadastro"),
        # Só para achar o lead quando a reserva não traz o lead associado; nunca é devolvido pela API do app
        "titular_email": titular.get("email"),
        "titular_telefone": titular.get("celular") or titular.get("telefone"),
    }


def lead_do_indice(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Lead enxuto para o índice: identificação, origem (com as UTMs) e situação."""
    enxuto = {k: lead.get(k) for k in CAMPOS_INDICE}
    adicionais = lead.get("campos_adicionais")
    enxuto["campos_adicionais"] = (
        [c for c in adicionais if isinstance(c, dict) and str(c.get("slug") or "").startswith("cf_utm")] or None
        if isinstance(adicionais, list) else None
    )
    return enxuto
MAX_PAGES = 400  # 200 mil leads


def cv_error_message(res) -> str:
    """Traduz a resposta de erro do CV em uma frase legível."""
    try:
        body = res.json()
        detalhe = body.get("mensagem") or body.get("error") or str(body)[:160]
    except Exception:
        detalhe = res.text[:160]
    return f"HTTP {res.status_code}: {detalhe}"


def flatten_cv_lead(item: Dict[str, Any]) -> Dict[str, Any]:
    """Achata o lead do CV (empreendimento, mídia e origem vêm aninhados) para normalize_cv_lead."""
    flat = dict(item)

    emp = item.get("empreendimento") or item.get("empreendimentos")
    if isinstance(emp, list) and emp:
        emp = emp[0]
    if isinstance(emp, dict):
        emp = emp.get("nome") or emp.get("nome_empreendimento")
    flat["empreendimento"] = emp if isinstance(emp, str) else None

    def nome(valor):
        return (valor.get("nome") or valor.get("descricao")) if isinstance(valor, dict) else valor

    # No CV a "origem" é genérica ("Busca Compartilhada", "Outros", "Não Definido");
    # o canal de verdade está na mídia ("Facebook Ads", "Instagram Ads", "Google").
    midias = item.get("midias") or []
    midia = nome(item.get("midia_principal")) or (nome(midias[0]) if midias else None)
    origem = nome(item.get("origem"))
    flat["origem_cv_original"] = origem
    flat["midia"] = midia
    flat["origem"] = midia or origem

    # O CV guarda o UUID do contato na RD Station — a mesma chave que a BeeViral envia
    if item.get("idrd_station") and not item.get("id_externo"):
        flat["id_externo"] = item["idrd_station"]
    return flat


class CVCRMExtractor(BaseCVExtractor):
    def __init__(
        self,
        api_url: Optional[str] = None,
        email: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.api_url = (api_url or os.getenv("CV_CRM_URL") or "").rstrip("/")
        self.email = email or os.getenv("CV_CRM_EMAIL")
        self.token = token or os.getenv("CV_CRM_TOKEN")
        self.status = None
        self.empreendimentos_status: Optional[SourceStatus] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "token": self.token or "",
            "email": self.email or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Empreendimentos
    # ------------------------------------------------------------------
    def fetch_empreendimentos(self) -> List[str]:
        """Nomes oficiais dos empreendimentos cadastrados no CV."""
        from engine.integrations import build_status

        if not (self.api_url and self.token):
            self.empreendimentos_status = build_status(
                "cv_empreendimentos",
                "nao_configurado",
                message="CV_CRM_URL e CV_CRM_TOKEN não configurados.",
                action="Gere um token de API no painel do CV e preencha CV_CRM_URL e CV_CRM_TOKEN.",
            )
            return []
        try:
            import httpx

            res = httpx.get(f"{self.api_url}/api/cvio/empreendimento", headers=self._headers(), timeout=20)
            if res.status_code != 200:
                raise RuntimeError(cv_error_message(res))
            nomes = [str(e.get("nome")).strip() for e in res.json() if isinstance(e, dict) and e.get("nome")]
            self.empreendimentos_status = build_status(
                "cv_empreendimentos", "real", len(nomes), f"{len(nomes)} empreendimento(s) oficiais carregados do CV."
            )
            return nomes
        except Exception as e:
            self.empreendimentos_status = build_status(
                "cv_empreendimentos",
                "erro",
                message=f"Falha ao ler empreendimentos do CV: {e}",
                action="Confira se o CV_CRM_TOKEN continua ativo no painel do CV.",
            )
            return []

    # ------------------------------------------------------------------
    # Leads
    # ------------------------------------------------------------------
    def fetch_raw(self, start_date: datetime, end_date: datetime) -> List[dict]:
        """
        Leads brutos da API, com todos os campos (UTMs, tags, situação, venda), dentro do
        período de cadastro. Registra o estado da consulta em self.status.
        """
        if not (self.api_url and self.token):
            self._set_status(
                "nao_configurado",
                message="CV_CRM_URL e CV_CRM_TOKEN não configurados.",
                action="Gere um token de API no painel do CV e preencha CV_CRM_URL e CV_CRM_TOKEN.",
            )
            return []

        if not self.email:
            self._set_status(
                "erro",
                message="A API de leads do CV exige o e-mail do usuário dono do token "
                "(resposta do CV: email_autenticacao_nao_informado).",
                action="Preencha CV_CRM_EMAIL no arquivo engine/.env com o e-mail do usuário do CV "
                "que gerou o CV_CRM_TOKEN.",
            )
            return []

        try:
            import httpx

            brutos: List[dict] = []
            vistos = set()
            total_conta = 0
            paginas_antigas = 0
            inicio = to_naive_utc(start_date)

            # A API ignora filtros de data e devolve do lead mais novo para o mais antigo:
            # pagina por offset até passar do início do período.
            with httpx.Client(timeout=60) as client:
                for pagina in range(MAX_PAGES):
                    res = client.get(
                        f"{self.api_url}/api/cvio/lead",
                        headers=self._headers(),
                        params={"limit": REGISTROS_POR_PAGINA, "offset": pagina * REGISTROS_POR_PAGINA},
                    )
                    if res.status_code != 200:
                        raise RuntimeError(cv_error_message(res))

                    payload = res.json()
                    if isinstance(payload, dict):
                        total_conta = payload.get("total") or total_conta
                        linhas = payload.get("leads") or []
                    else:
                        linhas = payload
                    novos = [x for x in linhas if isinstance(x, dict) and str(x.get("idlead")) not in vistos]
                    if not novos:
                        break
                    brutos.extend(novos)
                    vistos.update(str(x.get("idlead")) for x in novos)

                    datas = [to_naive_utc(parse_datetime(x["data_cad"])) for x in novos if x.get("data_cad")]
                    if len(linhas) < REGISTROS_POR_PAGINA:
                        break
                    # A API não ordena estritamente pela data de cadastro: só para depois de
                    # duas páginas INTEIRAS anteriores ao início do período
                    paginas_antigas = paginas_antigas + 1 if datas and max(datas) < inicio else 0
                    if paginas_antigas >= 2:
                        break

            brutos = [
                x for x in brutos
                if x.get("data_cad") and in_period(parse_datetime(x["data_cad"]), start_date, end_date)
            ]
            self._set_status(
                "real", len(brutos), f"{len(brutos)} lead(s) do CV no período — a conta tem {total_conta} no total."
            )
            print(f"  [CV CRM API] {len(brutos)} leads reais no período.")
            return brutos

        except Exception as e:
            self._set_status(
                "erro",
                message=f"Falha ao ler leads do CV: {e}",
                action="Confira o CV_CRM_EMAIL, o CV_CRM_TOKEN e se o token tem permissão de leitura de leads.",
            )
            print(f"  [CV CRM API Erro] {e}")
            return []

    def fetch_indice(self, anteriores: Optional[List[dict]] = None) -> List[dict]:
        """
        Índice enxuto de TODOS os leads da conta, de qualquer data: só o necessário para achar
        a pessoa (e-mail, telefone, nome, UUID da RD) e classificar a origem.

        Sem índice anterior lê todas as páginas (~50 mil leads, alguns minutos). Com índice
        anterior lê do lead mais novo para o mais antigo e para após 3 páginas seguidas sem
        nenhum lead novo ou alterado.
        """
        if not (self.api_url and self.token and self.email):
            self._set_status(
                "nao_configurado",
                message="CV_CRM_URL, CV_CRM_TOKEN e CV_CRM_EMAIL são necessários para o índice de leads.",
                action="Preencha CV_CRM_URL, CV_CRM_TOKEN e CV_CRM_EMAIL no engine/.env.",
            )
            return []
        try:
            import time
            import httpx

            conhecidos = {str(x.get("idlead")): x for x in anteriores or []}
            lidos: Dict[str, dict] = {}
            total_conta, sem_novidade, leitura_completa = 0, 0, False
            with httpx.Client(timeout=90) as client:
                for pagina in range(MAX_PAGES):
                    for tentativa in range(3):
                        res = client.get(
                            f"{self.api_url}/api/cvio/lead",
                            headers=self._headers(),
                            params={"limit": REGISTROS_POR_PAGINA, "offset": pagina * REGISTROS_POR_PAGINA},
                        )
                        if res.status_code == 200:
                            break
                        time.sleep(5 * (tentativa + 1))
                    if res.status_code != 200:
                        raise RuntimeError(cv_error_message(res))
                    payload = res.json()
                    total_conta = (payload.get("total") if isinstance(payload, dict) else None) or total_conta
                    linhas = (payload.get("leads") if isinstance(payload, dict) else payload) or []
                    novidade = False
                    for lead in linhas:
                        if not isinstance(lead, dict) or lead.get("idlead") is None:
                            continue
                        enxuto = lead_do_indice(lead)
                        chave = str(lead["idlead"])
                        novidade = novidade or conhecidos.get(chave) != enxuto
                        lidos[chave] = enxuto
                    if len(linhas) < REGISTROS_POR_PAGINA:
                        leitura_completa = True
                        break
                    if conhecidos:
                        sem_novidade = 0 if novidade else sem_novidade + 1
                        if sem_novidade >= 3:
                            break

            registros = list(lidos.values()) if leitura_completa else list({**conhecidos, **lidos}.values())
            aviso = ""
            if leitura_completa and total_conta and len(registros) < total_conta * 0.98:
                aviso = f" Atenção: a conta informa {total_conta} leads e vieram {len(registros)}."
            self._set_status(
                "real",
                len(registros),
                f"{len(registros)} lead(s) no índice ("
                + ("leitura completa" if leitura_completa else f"{len(lidos)} relidos, demais mantidos")
                + f") — a conta tem {total_conta}.{aviso}",
            )
            return registros
        except Exception as e:
            self._set_status("erro", message=f"Falha ao montar o índice de leads do CV: {e}",
                             action="Confira CV_CRM_EMAIL e CV_CRM_TOKEN e tente de novo.")
            return []

    def fetch_reservas(self, anteriores: Optional[List[dict]] = None) -> List[dict]:
        """
        Todas as reservas do CV, uma a uma pelo ID (/api/v1/comercial/reservas/{id}), com o mesmo token
        dos leads. A listagem com situacao=todas só devolve a carga histórica (reservas de 2019) e ignora
        filtros; a busca por ID alcança qualquer reserva. ID inexistente responde 400.

        Sem base anterior (ou com base muito incompleta): varre do ID 1 até o maior (~16 mil IDs, cerca de
        15 minutos com 10 consultas simultâneas). Com base anterior: busca só os IDs novos e relê as
        reservas que ainda podem mudar (não vendidas, ou feitas nos últimos 180 dias).
        """
        if not (self.api_url and self.token and self.email):
            self._set_status(
                "nao_configurado",
                message="CV_CRM_URL, CV_CRM_TOKEN e CV_CRM_EMAIL são necessários para ler as reservas.",
                action="Preencha CV_CRM_URL, CV_CRM_TOKEN e CV_CRM_EMAIL no engine/.env.",
            )
            return []
        try:
            import time
            from concurrent.futures import ThreadPoolExecutor
            from datetime import datetime as _datetime, timedelta as _timedelta

            import httpx

            url = f"{self.api_url}{RESERVAS_PATH}"
            conhecidas: Dict[str, dict] = {str(r["idreserva"]): r for r in anteriores or [] if r.get("idreserva")}

            with httpx.Client(timeout=60, limits=httpx.Limits(max_connections=RESERVAS_SIMULTANEAS)) as client:

                def buscar(idreserva: int) -> Optional[dict]:
                    for tentativa in range(4):
                        try:
                            res = client.get(f"{url}/{idreserva}", headers=self._headers())
                        except httpx.HTTPError:
                            time.sleep(2 * (tentativa + 1))
                            continue
                        if res.status_code == 200:
                            dados = res.json()
                            item = dados.get(str(idreserva)) if isinstance(dados, dict) else None
                            return {"idreserva": str(idreserva), **reserva_enxuta(item)} if isinstance(item, dict) else None
                        if res.status_code in (400, 404, 204):
                            return None  # reserva inexistente ou excluída
                        time.sleep(3 * (tentativa + 1))
                    raise RuntimeError(f"a reserva {idreserva} não respondeu depois de 4 tentativas")

                def buscar_varias(ids: List[int]) -> Dict[int, Optional[dict]]:
                    with ThreadPoolExecutor(max_workers=RESERVAS_SIMULTANEAS) as pool:
                        return dict(zip(ids, pool.map(buscar, ids)))

                # Maior ID: das reservas mais recentes (listagem padrão) e das já conhecidas;
                # depois procura acima dele até um bloco inteiro sem nenhuma reserva
                recentes = client.get(url, headers=self._headers())
                dados_recentes = recentes.json() if recentes.status_code == 200 else {}
                maior = max([0] + [int(k) for k in dados_recentes if str(k).isdigit()] + [int(k) for k in conhecidas])
                novas_no_topo: Dict[int, Optional[dict]] = {}
                while True:
                    bloco = list(range(maior + 1, maior + 1 + RESERVAS_BLOCO_SEM_ID))
                    achadas = buscar_varias(bloco)
                    encontradas = [i for i, r in achadas.items() if r]
                    novas_no_topo.update(achadas)
                    if not encontradas:
                        break
                    maior = max(encontradas)

                varredura_completa = len(conhecidas) < 0.8 * maior
                if varredura_completa:
                    ids = list(range(1, maior + 1))
                else:
                    ultimo_conhecido = max(int(k) for k in conhecidas)
                    limite = (_datetime.now() - _timedelta(days=180)).strftime("%Y-%m-%d")
                    mutaveis = [int(k) for k, r in conhecidas.items() if not r.get("vendida") or str(r.get("data") or "") >= limite]
                    ids = sorted(set(range(ultimo_conhecido + 1, maior + 1)) | set(mutaveis))
                ids = [i for i in ids if i not in novas_no_topo]
                resultados = {**buscar_varias(ids), **novas_no_topo}

            reservas = {} if varredura_completa else dict(conhecidas)
            for idreserva, reserva in resultados.items():
                if reserva:
                    reservas[str(idreserva)] = reserva
                else:
                    reservas.pop(str(idreserva), None)

            vendidas = sum(1 for r in reservas.values() if r["vendida"])
            self._set_status(
                "real",
                len(reservas),
                f"{len(reservas)} reserva(s) do CV, {vendidas} vendida(s) — "
                + ("varredura completa por ID" if varredura_completa else f"{len(resultados)} ID(s) consultados nesta atualização")
                + ".",
            )
            return list(reservas.values())
        except Exception as e:
            self._set_status("erro", message=f"Falha ao ler as reservas do CV: {e}",
                             action="Confira CV_CRM_EMAIL e CV_CRM_TOKEN e tente de novo.")
            return []

    def fetch_cv_leads(self, start_date: datetime, end_date: datetime) -> List[CVLeadRecord]:
        brutos = self.fetch_raw(start_date, end_date)
        if self.status.mode != "real":
            return self._fallback(self._mock_leads)
        return [normalize_cv_lead(flatten_cv_lead(item)) for item in brutos]

    # ------------------------------------------------------------------
    @staticmethod
    def _mock_leads() -> List[CVLeadRecord]:
        sample_cv = [
            {"id": "cv_1001", "email": "carlos.silva@gmail.com", "telefone": "11988881111", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 10:32:00", "id_externo": "fb_click_101", "empreendimento": "Residencial Sol"},
            {"id": "cv_1002", "email": "ana.pereira@outlook.com", "telefone": "11988882222", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 11:17:00", "id_externo": "fb_click_102"},
            {"id": "cv_1003", "email": "marcos.souza@uol.com.br", "telefone": "21977773333", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 14:02:00", "id_externo": "fb_click_103"},
            {"id": "cv_1004", "email": "luciana.lima@hotmail.com", "telefone": "31966664444", "origem": "Facebook Ads", "midia": "cpc", "data_cadastramento": "2026-07-26 09:22:00", "id_externo": "fb_click_104"},
            {"id": "cv_1006", "email": "juliana.mendes@yahoo.com.br", "telefone": "11944446666", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-27 08:12:00", "id_externo": "fb_click_106"},
            {"id": "cv_2001", "email": "fernando.alves@gmail.com", "telefone": "11933331111", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 09:12:00", "id_externo": "gclid_alpha_201", "empreendimento": "Residencial Sol"},
            {"id": "cv_2002", "email": "beatriz.costa@gmail.com", "telefone": "21922223333", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-25 16:32:00", "id_externo": "gclid_alpha_202"},
            {"id": "cv_2003", "email": "ricardo.oliveira@uol.com.br", "telefone": "31911114444", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-26 10:02:00", "id_externo": "gclid_alpha_203"},
            {"id": "cv_2004", "email": "camila.ferreira@outlook.com", "telefone": "41999995555", "origem": "Google Ads", "midia": "cpc", "data_cadastramento": "2026-07-26 22:30:00", "id_externo": "gclid_alpha_204"},
            {"id": "cv_3001", "email": "patricia.rocha@gmail.com", "telefone": "11977778888", "origem": "RD Station", "midia": "inbound", "data_cadastramento": "2026-07-25 12:03:00", "id_externo": "rd_lead_301", "empreendimento": "Residencial Sol"},
            {"id": "cv_3002", "email": "thiago.martins@yahoo.com", "telefone": "21966669999", "origem": "RD Station", "midia": "inbound", "data_cadastramento": "2026-07-26 14:23:00", "id_externo": "rd_lead_302"},
            {"id": "cv_3003", "email": "vanessa.gomes@icloud.com", "telefone": "31955550000", "origem": "RD Station", "midia": "inbound", "data_cadastramento": "2026-07-26 17:48:00", "id_externo": "rd_lead_303"},
            {"id": "cv_4001", "email": "marcelo.indicação1@gmail.com", "telefone": "11944445555", "origem": "BeeViral", "midia": "referral", "data_cadastramento": "2026-07-25 15:35:00", "id_externo": "bee_ref_401"},
            {"id": "cv_4002", "email": "renata.indicação2@hotmail.com", "telefone": "21933334444", "origem": "BeeViral", "midia": "referral", "data_cadastramento": "2026-07-26 11:15:00", "id_externo": "bee_ref_402"},
            {"id": "cv_4004", "email": "sofi.indicada4@yahoo.com", "telefone": "41911112222", "origem": "BeeViral", "midia": "referral", "data_cadastramento": "2026-07-27 07:35:00", "id_externo": "bee_ref_404"},
            {"id": "cv_5001", "email": "eduardo.estande@gmail.com", "telefone": "11987654321", "origem": "Estande Vendas", "midia": "presencial", "data_cadastramento": "2026-07-25 14:30:00"},
            {"id": "cv_5002", "email": "heloisa.evento@outlook.com", "telefone": "21987654322", "origem": "Feirão Imobiliário", "midia": "presencial", "data_cadastramento": "2026-07-26 11:00:00"},
        ]
        return [normalize_cv_lead(item) for item in sample_cv]
