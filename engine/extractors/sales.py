"""
Extrator da Base de Vendas (reservas/contratos).

Ordem de resolução da fonte:
  1. Arquivo indicado explicitamente (--sales-file ou parâmetro da API).
  2. API do CV — GET /api/cvio/reserva.
  3. Planilha carregada pelo dashboard (a mais recente em output/uploads).
  4. Arquivo em SALES_FILE_PATH.
  5. Simulação — somente com ALLOW_SIMULATED_DATA=true.
"""

import glob
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.config import SaleRecord
from engine.extractors.base import StatusMixin, in_period, read_csv_rows
from engine.normalizer import normalize_sale

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "output", "uploads"))
SALES_EXTENSIONS = (".csv", ".xlsx", ".xls")
MAX_PAGES = 100
REGISTROS_POR_PAGINA = 500

ACAO_RESERVAS = (
    "No painel do CV, habilite a permissão de leitura de Reservas para o token de API — "
    "ou carregue a planilha de vendas pelo dashboard (tela Auditar Vendas)."
)


def latest_uploaded_sales_file() -> Optional[str]:
    """Planilha de vendas mais recente carregada pelo dashboard."""
    arquivos = [
        f for f in glob.glob(os.path.join(UPLOAD_DIR, "vendas_*"))
        if f.lower().endswith(SALES_EXTENSIONS)
    ]
    return max(arquivos, key=os.path.getmtime) if arquivos else None


def read_sales_file(path: str) -> List[SaleRecord]:
    """Lê CSV/XLSX de vendas com cabeçalhos no formato do BI (capitalizados, com espaços)."""
    if path.lower().endswith(".csv"):
        linhas = read_csv_rows(path)
    else:
        import pandas as pd

        linhas = pd.read_excel(path).to_dict(orient="records")

    vendas = []
    for row in linhas:
        limpo = {
            str(k).strip().lower().replace(" ", "_"): (None if str(v).strip().lower() in ("", "nan", "none") else v)
            for k, v in row.items()
        }
        if any(limpo.values()):
            vendas.append(normalize_sale(limpo))
    return vendas


def flatten_cv_reserva(item: Dict[str, Any]) -> Dict[str, Any]:
    """Achata a reserva do CV (cliente, empreendimento e unidade vêm aninhados)."""
    if not isinstance(item, dict):
        return {}
    flat = dict(item)

    cliente = item.get("titular") or item.get("cliente") or item.get("lead") or {}
    if isinstance(cliente, list) and cliente:
        cliente = cliente[0]
    if isinstance(cliente, dict):
        flat.setdefault("nome_cliente", cliente.get("nome"))
        flat.setdefault("email", cliente.get("email"))
        flat.setdefault("telefone", cliente.get("telefone") or cliente.get("celular"))
        flat.setdefault("cpf", cliente.get("cpf") or cliente.get("documento") or cliente.get("cnpj"))
        if not flat.get("origem"):
            flat["origem"] = cliente.get("origem") or cliente.get("midia")

    for campo in ("empreendimento", "unidade", "origem", "situacao"):
        valor = item.get(campo)
        if isinstance(valor, dict):
            flat[campo] = valor.get("nome") or valor.get("descricao")

    flat.setdefault("data_venda", item.get("data_venda") or item.get("data_reserva") or item.get("data_contrato") or item.get("data_cad"))
    flat.setdefault("valor", item.get("valor_contrato") or item.get("valor"))
    flat.setdefault("id", item.get("idreserva") or item.get("id"))
    return flat


class SalesExtractor(StatusMixin):
    """Extrai a base de vendas que será cruzada contra a base de leads."""

    source_key = "vendas"

    def __init__(
        self,
        api_url: Optional[str] = None,
        email: Optional[str] = None,
        token: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        self.api_url = (api_url or os.getenv("CV_CRM_URL") or "").rstrip("/")
        self.email = email or os.getenv("CV_CRM_EMAIL")
        self.token = token or os.getenv("CV_CRM_TOKEN")
        self.file_path = file_path
        self.status = None
        self.file_used: Optional[str] = None

    # ------------------------------------------------------------------
    def _from_cv_api(self, start_date: datetime, end_date: datetime) -> Optional[List[SaleRecord]]:
        """Devolve None quando a API não pôde ser usada (e registra o motivo)."""
        if not (self.api_url and self.token):
            self._cv_error = "CV não configurado."
            return None
        try:
            import httpx

            brutos: List[dict] = []
            with httpx.Client(timeout=30) as client:
                for pagina in range(1, MAX_PAGES + 1):
                    res = client.get(
                        f"{self.api_url}/api/cvio/reserva",
                        headers={"token": self.token, "email": self.email or "", "Accept": "application/json"},
                        params={"pagina": pagina, "registros_por_pagina": REGISTROS_POR_PAGINA},
                    )
                    if res.status_code != 200:
                        try:
                            detalhe = res.json().get("mensagem") or res.text[:160]
                        except Exception:
                            detalhe = res.text[:160]
                        self._cv_error = f"CV respondeu HTTP {res.status_code}: {detalhe}"
                        return None
                    payload = res.json()
                    linhas = payload if isinstance(payload, list) else (
                        payload.get("reservas") or payload.get("dados") or payload.get("data") or []
                    )
                    if not linhas:
                        break
                    brutos.extend(linhas)
                    if len(linhas) < REGISTROS_POR_PAGINA:
                        break

            vendas = []
            for item in brutos:
                flat = flatten_cv_reserva(item)
                situacao = str(flat.get("situacao") or "").lower()
                if "cancel" in situacao or "distrat" in situacao:
                    continue
                vendas.append(normalize_sale(flat))
            return [v for v in vendas if in_period(v.sale_date, start_date, end_date)]
        except Exception as e:
            self._cv_error = f"Falha ao consultar reservas no CV: {e}"
            return None

    def _from_file(self, path: str, start_date: datetime, end_date: datetime, origem: str) -> List[SaleRecord]:
        todas = read_sales_file(path)
        vendas = [v for v in todas if in_period(v.sale_date, start_date, end_date)]
        self.file_used = path
        nome = os.path.basename(path)
        alteracao = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d/%m/%Y %H:%M")
        msg = f"{origem} '{nome}' ({alteracao}): {len(vendas)} de {len(todas)} venda(s) no período analisado."
        if todas and not vendas:
            msg += " Nenhuma venda da planilha cai no período — ajuste as datas da análise."
        self._set_status("real", len(vendas), msg)
        print(f"  [Vendas] {msg}")
        return vendas

    def fetch_sales(self, start_date: datetime, end_date: datetime) -> List[SaleRecord]:
        self._cv_error = None
        try:
            if self.file_path:
                return self._from_file(self.file_path, start_date, end_date, "Planilha informada")

            vendas_cv = self._from_cv_api(start_date, end_date)
            if vendas_cv is not None:
                self._set_status("real", len(vendas_cv), f"{len(vendas_cv)} reserva(s) do CV no período.")
                return vendas_cv

            enviado = latest_uploaded_sales_file()
            if enviado:
                vendas = self._from_file(enviado, start_date, end_date, "Planilha carregada no dashboard")
                self.status.message += f" (Reservas do CV indisponíveis: {self._cv_error})"
                return vendas

            env_path = os.getenv("SALES_FILE_PATH")
            if env_path and os.path.exists(env_path):
                return self._from_file(env_path, start_date, end_date, "Planilha de SALES_FILE_PATH")

            self._set_status(
                "erro",
                message=f"Nenhuma base de vendas disponível. {self._cv_error or ''}".strip(),
                action=ACAO_RESERVAS,
            )
            return self._fallback(self._mock_sales)

        except Exception as e:
            self._set_status(
                "erro",
                message=f"Falha ao ler a base de vendas: {e}",
                action="Confira se a planilha tem as colunas cliente, email/telefone/cpf, origem, data_venda e empreendimento.",
            )
            return self._fallback(self._mock_sales)

    # ------------------------------------------------------------------
    @staticmethod
    def _mock_sales() -> List[SaleRecord]:
        """Cenário de demonstração: 5 vendas, 3 declaradas como online."""
        sample_sales = [
            {"id": "venda_9001", "nome_cliente": "Carlos Silva", "email": "carlos.silva@gmail.com", "telefone": "11988881111", "cpf": "123.456.789-01", "origem": "Facebook Ads", "data_venda": "2026-07-28 15:40:00", "valor": "450000,00", "empreendimento": "Residencial Sol", "unidade": "A-402"},
            {"id": "venda_9002", "nome_cliente": "Fernando Alves", "email": "fernando.alves@gmail.com", "telefone": "11933331111", "cpf": "234.567.890-12", "origem": "Google Ads", "data_venda": "2026-07-29 10:05:00", "valor": "620000,00", "empreendimento": "Condomínio Horizonte", "unidade": "B-1201"},
            {"id": "venda_9003", "nome_cliente": "Sérgio Bastos", "email": "sergio.bastos@gmail.com", "telefone": "11955557777", "cpf": "345.678.901-23", "origem": "Facebook Ads", "data_venda": "2026-07-30 11:20:00", "valor": "380000,00", "empreendimento": "Residencial Sol", "unidade": "A-108"},
            {"id": "venda_9004", "nome_cliente": "Eduardo Estande", "email": "eduardo.estande@gmail.com", "telefone": "11987654321", "cpf": "456.789.012-34", "origem": "Estande de Vendas", "data_venda": "2026-07-30 17:00:00", "valor": "512000,00", "empreendimento": "Condomínio Horizonte", "unidade": "B-302"},
            {"id": "venda_9005", "nome_cliente": "Patrícia Rocha", "email": "patricia.rocha@gmail.com", "telefone": "11977778888", "cpf": "567.890.123-45", "origem": "Estande de Vendas", "data_venda": "2026-07-31 09:30:00", "valor": "495000,00", "empreendimento": "Residencial Sol", "unidade": "A-901"},
        ]
        return [normalize_sale(item) for item in sample_sales]
