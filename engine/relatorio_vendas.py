"""
Relatório em Excel das vendas online do período, e os mesmos números para a tela Analista.

Segue a planilha revisada com a gestão. Abas: Leia primeiro · Resumo por produto · Casos para
investigar · Não viraram venda online · Todas as vendas · Como foi feito.

Caso para investigar é a venda que não está como online no CV, com conversão online do cliente na
janela, sem corretor atendendo antes, e em que a conversa mostra que o cliente seguiu com a gente e
comprou com o nosso time. As que vieram do online mas o cliente comprou com outro corretor ficam
na aba "Não viraram venda online": em laranja as que atendemos e perdemos.

Todo número dos quadros é fórmula sobre as abas de dados: quem recebe a planilha pode filtrar e
conferir de onde veio cada número.
"""

import os
import re
from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
from openpyxl.worksheet.table import Table, TableStyleInfo

from engine import leitura_conversa
from engine.vendas_online import RESULTADO, TIME_MOURA_LEITE, link_lead

RELATORIOS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output", "relatorios"))

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------

AZUL = "1F3A5F"
F = Font(name="Arial", size=10)
FB = Font(name="Arial", size=10, bold=True)
FT = Font(name="Arial", size=18, bold=True, color=AZUL)
FS = Font(name="Arial", size=12, bold=True, color=AZUL)
FN = Font(name="Arial", size=9, italic=True, color="595959")
FL = Font(name="Arial", size=10, color="0563C1", underline="single")
FK = Font(name="Arial", size=14, bold=True, color=AZUL)
FILL_TOTAL = PatternFill("solid", fgColor="D9E1F2")
FILL_CASO = PatternFill("solid", fgColor="FFF2CC")
FILL_PERDA = PatternFill("solid", fgColor="FCE4D6")
FILL_DISTRATO = PatternFill("solid", fgColor="FFC7CE")
FONT_DISTRATO = Font(name="Arial", size=10, bold=True, color="9C0006")

MOEDA = '"R$" #,##0;-"R$" #,##0;"-"'
DATA = "dd/mm/yyyy"
INT = '#,##0;-#,##0;"-"'
PCT = '0.0%;-0.0%;"-"'
MES = "mm/yyyy"
ESTILO_TABELA = "TableStyleMedium2"
TOPO = Alignment(vertical="top", wrap_text=True)
TOPO_CENTRO = Alignment(horizontal="center", vertical="top", wrap_text=True)
CABEC = Alignment(horizontal="center", vertical="center", wrap_text=True)

CASO, PERDA, NAO_NOSSA, JA_ATENDIA = RESULTADO["caso"], RESULTADO["perda"], RESULTADO["nao_nossa"], RESULTADO["ja_atendia"]
ONLINE_SDR, ONLINE_LEAD = RESULTADO["online_cv_sdr"], RESULTADO["online_cv_lead"]

CANAL = {"SDR": "SDR", "Imobiliária": "Imobiliária", "Corretor (Time Moura Leite)": "Time Moura Leite",
         "Corretor (Espontânea)": "Espontânea (Time)", "Venda Interna": "Venda Interna",
         "Sem tipo de venda": "Sem tipo de venda"}
CANAIS_NAO_SDR = ["Imobiliária", "Time Moura Leite", "Espontânea (Time)", "Venda Interna", "Sem tipo de venda"]
ORIGEM = {"Campanha paga (Meta/Google)": "Campanha paga (Meta/Google)",
          "Site / landing page (formulário)": "Site / landing page",
          "Orgânico (site, chat, redes, e-mail)": "Site, chat ou redes (orgânico)",
          "Indicação BeeViral": "Indicação BeeViral",
          "Mídia offline (outdoor, panfleto, rádio)": "Outdoor, panfleto ou rádio"}
ORIGENS = list(dict.fromkeys(ORIGEM.values()))
FRASE_ORIGEM = {"Campanha paga (Meta/Google)": "de uma campanha paga (Meta/Google)",
                "Site / landing page (formulário)": "do site ou de uma landing page",
                "Orgânico (site, chat, redes, e-mail)": "do site, chat ou redes sociais",
                "Indicação BeeViral": "de uma indicação BeeViral",
                "Mídia offline (outdoor, panfleto, rádio)": "de outdoor, panfleto ou rádio"}
TRATATIVA = ("Com tratativa do SDR", "Só assistente virtual", "Sem tratativa registrada")
PREFIXO = {"caso": "Venda online (a conversa confirma)", "perda": "ATENDEMOS, MAS COMPROU COM OUTRO CORRETOR",
           "nao_nossa": "Não era venda nossa"}
RE_HUMANO_TAG = re.compile(r"\(sal|\(sql\)|tentativa de contato|lead oportunidade", re.I)
# Só as fórmulas do próprio relatório podem entrar como fórmula; texto dos dados nunca.
FORMULA_DO_RELATORIO = re.compile(r"^=(COUNTIFS|SUMIFS|IFERROR|SUM|COUNTA)\(|^='[^']+'!\$?[A-Z]+\$?\d+$")

ABA_LEIA = "Leia primeiro"
ABA_RESUMO = "Resumo por produto"
ABA_CASOS = "Casos para investigar"
ABA_NAO_VIRARAM = "Não viraram venda online"
ABA_VENDAS = "Todas as vendas"
ABA_COMO = "Como foi feito"


def _d(valor: Any) -> Optional[date]:
    return date.fromisoformat(str(valor)[:10]) if valor else None


def _seguro(valor: Any) -> Any:
    if isinstance(valor, str) and not FORMULA_DO_RELATORIO.match(valor):
        valor = valor.strip()
        while valor[:1] in ("=", "+", "@"):
            valor = valor[1:].strip()
    return valor


def _periodo_texto(inicio: date, fim: date) -> str:
    if inicio.year == fim.year and inicio.month == fim.month:
        meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
                 "outubro", "novembro", "dezembro"]
        return f"{meses[inicio.month - 1]} de {inicio.year}"
    return f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"


# ---------------------------------------------------------------------------
# Utilidades de planilha
# ---------------------------------------------------------------------------


def _escrever_tabela(ws, linha, coluna, colunas, linhas, nome, formatos=None, quebra=(), centro=(), alturas=None,
                     altura_cabecalho=48):
    """colunas: [(cabeçalho, largura)]; linhas: listas de valores (ou dicts {valor, link, fill, font})."""
    for j, (h, w) in enumerate(colunas):
        c = ws.cell(row=linha, column=coluna + j, value=h)
        c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        c.alignment = CABEC
        ws.column_dimensions[get_column_letter(coluna + j)].width = w
    ws.row_dimensions[linha].height = altura_cabecalho
    for i, valores in enumerate(linhas, linha + 1):
        for j, v in enumerate(valores):
            extra = v if isinstance(v, dict) else {"valor": v}
            c = ws.cell(row=i, column=coluna + j, value=_seguro(extra["valor"]))
            nome_col = colunas[j][0]
            c.font = extra.get("font", F)
            c.alignment = TOPO if nome_col in quebra else (TOPO_CENTRO if nome_col in centro else Alignment(vertical="top"))
            if formatos and nome_col in formatos:
                c.number_format = formatos[nome_col]
            if extra.get("link"):
                c.hyperlink = extra["link"]
                c.font = FL
            if extra.get("fill"):
                c.fill = extra["fill"]
        if alturas:
            ws.row_dimensions[i].height = alturas[i - linha - 1]
    ultima = linha + max(1, len(linhas))
    ref = f"{get_column_letter(coluna)}{linha}:{get_column_letter(coluna + len(colunas) - 1)}{ultima}"
    tabela = Table(displayName=nome, ref=ref)
    tabela.tableStyleInfo = TableStyleInfo(name=ESTILO_TABELA, showRowStripes=True, showColumnStripes=False)
    ws.add_table(tabela)
    return {h: get_column_letter(coluna + j) for j, (h, _) in enumerate(colunas)}, linha + 1, ultima


def _altura(textos_larguras, minimo=30):
    n = max([1] + [sum(max(1, -(-len(parte) // max(1, int(w * 1.1)))) for parte in str(t or "").split("\n"))
                   for t, w in textos_larguras])
    return max(minimo, 13 * n + 6)


def _linha_total(ws, linha, coluna_ini, n_colunas, formulas, formatos):
    for j in range(n_colunas):
        c = ws.cell(row=linha, column=coluna_ini + j, value=formulas[j])
        c.font, c.fill = FB, FILL_TOTAL
        c.border = Border(top=Side(style="medium", color=AZUL), bottom=Side(style="medium", color=AZUL))
        c.alignment = Alignment(horizontal="left" if j == 0 else "center", vertical="center")
        if formatos[j]:
            c.number_format = formatos[j]
    ws.row_dimensions[linha].height = 20


# ---------------------------------------------------------------------------
# Leitura de uma venda
# ---------------------------------------------------------------------------


def _lead_ref(venda: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return next((q for q in venda["leads"] if q["id"] == venda.get("lead_ref")), None)


def _link_do_lead(lead: Optional[Dict[str, Any]]) -> Optional[str]:
    return (lead.get("link") or link_lead(lead["id"])) if lead else None


def _data_distrato(venda: Dict[str, Any]) -> Optional[date]:
    return _d(venda["data_distrato"]) if venda["situacao_atual"] == "Distrato" else None


def _situacao_cel(venda: Dict[str, Any]):
    if venda["situacao_atual"] == "Distrato":
        return {"valor": "Distrato", "fill": FILL_DISTRATO, "font": FONT_DISTRATO}
    return venda["situacao_atual"]


def _tratativa(venda: Dict[str, Any]) -> str:
    if venda["sdr_humano"]:
        return TRATATIVA[0]
    return TRATATIVA[1] if venda["sdr_assistente"] else TRATATIVA[2]


def _origem(lead: Optional[Dict[str, Any]]) -> str:
    return ORIGEM.get(lead["categoria"], lead["categoria"]) if lead else "—"


def _detalhe_origem(ref: Dict[str, Any]) -> str:
    if ref.get("origem_rd"):
        return ref["origem_rd"].replace("1ª conversão na RD:", "Primeira conversão na RD Station:")
    partes = [f"Mídia no CV: {ref['midia_cv']}" if ref.get("midia_cv") else None,
              f"UTM: {ref['utm']}" if ref.get("utm") else None,
              f"Campanha: {ref['campanha']}" if ref.get("campanha") else None]
    return "; ".join(p for p in partes if p) or ref.get("evidencia") or "—"


def _ligado_por(ref: Dict[str, Any]) -> str:
    nomes = {"email": "e-mail", "fone": "telefone", "nome": "nome", "lead_associado": "lead vinculado"}
    return ", ".join(nomes[k] for k in nomes if k in ref.get("chaves", []))


def _registros_tratativa(venda: Dict[str, Any]) -> str:
    eventos = venda["sdr_eventos"] or []
    linhas, humanos = [], []
    for e in eventos:
        if e[1] == "sdr":
            item = f"{_d(e[0]):%d/%m/%Y}: {e[2]}"
            if item not in humanos:
                humanos.append(item)
    tags = [t for t in venda["sdr_tags"] or [] if RE_HUMANO_TAG.search(t)]
    if humanos or tags or venda["sdr_situacao"]:
        linhas.append("SDR:")
        linhas += [f"• {h}" for h in humanos[:5]]
        if tags:
            linhas.append("• Etapas no lead: " + ", ".join(tags[:6]))
        if venda["sdr_situacao"]:
            linhas.append("• Situação no CV: " + ", ".join(venda["sdr_situacao"]))
    assistente = [e for e in eventos if e[1] == "assistente"]
    if assistente:
        datas = sorted(_d(e[0]) for e in assistente)
        periodo = f"{datas[0]:%d/%m/%Y}" + (f" a {datas[-1]:%d/%m/%Y}" if datas[-1] != datas[0] else "")
        acoes = sorted({e[2].replace("Assistente virtual ", "").lower() for e in assistente
                        if "atendimento da assistente" not in e[2].lower()})
        linhas.append(f"Assistente virtual: {len(assistente)} registro(s) em {periodo}"
                      + (f" ({'; '.join(acoes)})" if acoes else ""))
    return "\n".join(linhas) or "Nenhum registro de tratativa no lead."


def _janela_usada(venda: Dict[str, Any]) -> str:
    if venda["regra_janela"] == "pré-lançamento":
        return f"Pré-campanha do lançamento de {_d(venda['data_lancamento']):%d/%m/%Y}"
    return "Até 90 dias antes da venda"


def _conversao(venda: Dict[str, Any], ref: Dict[str, Any]) -> str:
    origem = FRASE_ORIGEM.get(ref["categoria"], str(ref["categoria"]).lower())
    conv = _d(venda["conv_ref"])
    if venda["regra_janela"] == "pré-lançamento":
        return (f"O cliente virou lead na pré-campanha em {conv:%d/%m/%Y}, vindo {origem}, e comprou na safra do "
                f"lançamento ({venda['dias_conv_venda']} dias depois).")
    return f"O cliente converteu online em {conv:%d/%m/%Y}, {venda['dias_conv_venda']} dias antes da compra, vindo {origem}."


def _resumo_caso(venda: Dict[str, Any], ref: Dict[str, Any]) -> str:
    """O que a conversa mostra primeiro; depois quando e de onde o cliente veio."""
    leitura = venda.get("leitura") or {}
    frases = [f"{PREFIXO[venda['resultado']]}.", leitura.get("texto") or "", _conversao(venda, ref)]
    if venda["situacao_atual"] == "Distrato":
        quando = _data_distrato(venda)
        frases.insert(0, f"ATENÇÃO: venda distratada em {quando:%d/%m/%Y}." if quando else "ATENÇÃO: venda distratada.")
    if venda["venda_online_cv"] and venda["resultado"] in ("perda", "nao_nossa"):
        frases.append("O CV conta essa venda como online pelo lead vinculado à reserva — pela conversa, ela não é.")
    if leitura.get("revisada"):
        frases.append("(Leitura revisada pelo analista.)")
    return " ".join(f for f in frases if f)


def _como_conferir(venda: Dict[str, Any], ref: Dict[str, Any]) -> str:
    texto = f"Clique no nome do cliente para abrir o lead {ref['id']} no CV e leia a conversa."
    if venda["resultado"] == "caso":
        return (texto + f" Se for o mesmo cliente da reserva {venda['idreserva']}, vincule esse lead à reserva para a "
                        "venda contar como online.")
    return texto + " Se a leitura não estiver certa, corrija na tela Analista, em Vendas online."


# ---------------------------------------------------------------------------
# A planilha
# ---------------------------------------------------------------------------


class _Relatorio:
    COLS_CASO = [("Nº", 5), ("Produto", 30), ("Cliente (abre o lead no CV)", 30), ("Reserva (abre no CV)", 11),
                 ("Data da venda", 12), ("Valor do contrato", 14), ("Unidade", 14), ("Canal da venda no CV", 16),
                 ("Corretor", 26), ("Imobiliária", 26), ("Resumo do caso", 62), ("Tratativa do lead", 18),
                 ("Como conferir no CV", 50), ("Lead online (ID)", 11), ("Nome no lead", 26), ("Origem do lead", 24),
                 ("Como a origem foi identificada", 42), ("Data da conversão online", 12), ("Dias até a venda", 10),
                 ("Janela usada", 24), ("SDR tratou?", 9), ("Chegou a SQL?", 9), ("Assistente virtual?", 10),
                 ("Registros de tratativa", 50), ("Pré-cadastro (data)", 12), ("Corretor do pré-cadastro", 26),
                 ("Leads vinculados à venda", 13), ("Origem do lead vinculado", 30), ("Ligado por", 18)]
    QUEBRA_CASO = {"Produto", "Cliente (abre o lead no CV)", "Corretor", "Imobiliária", "Resumo do caso",
                   "Como conferir no CV", "Nome no lead", "Origem do lead", "Como a origem foi identificada",
                   "Janela usada", "Registros de tratativa", "Corretor do pré-cadastro", "Origem do lead vinculado",
                   "Canal da venda no CV", "Tratativa do lead", "Ligado por"}
    CENTRO_CASO = {"Nº", "Reserva (abre no CV)", "Data da venda", "Lead online (ID)", "Data da conversão online",
                   "Dias até a venda", "SDR tratou?", "Chegou a SQL?", "Assistente virtual?", "Pré-cadastro (data)",
                   "Leads vinculados à venda"}
    FORM_CASO = {"Data da venda": DATA, "Valor do contrato": MOEDA, "Data da conversão online": DATA,
                 "Pré-cadastro (data)": DATA}

    def __init__(self, analise: Dict[str, Any]):
        self.analise = analise
        self.vendas = analise["vendas"]
        self.inicio, self.fim = _d(analise["periodo"]["inicio"]), _d(analise["periodo"]["fim"])
        self.produtos = [p for p, _ in Counter(v["produto"] for v in self.vendas).most_common()]
        self.ordem = {p: i for i, p in enumerate(self.produtos)}
        chave = lambda v: (self.ordem[v["produto"]], str(v["data_venda"]), int(v["idreserva"]))
        self.casos = sorted([v for v in self.vendas if v["resultado"] == "caso"], key=chave)
        motivos = list(leitura_conversa.MOTIVOS)
        self.nao_viraram = sorted(
            [v for v in self.vendas if v["resultado"] in ("perda", "nao_nossa")],
            key=lambda v: (v["resultado"] != "perda", motivos.index((v.get("leitura") or {}).get("motivo") or "revisado"),
                           *chave(v)))
        self.wb = Workbook()

    def aba_todas_as_vendas(self):
        ws = self.wb.active
        ws.title = ABA_VENDAS
        ws.sheet_view.showGridLines = False
        colunas = [("Produto", 34), ("Reserva (abre no CV)", 12), ("Data da venda", 12), ("Cliente", 32), ("Unidade", 15),
                   ("Valor do contrato", 15), ("Situação atual", 11), ("Data do distrato", 12),
                   ("Canal da venda no CV", 18), ("Corretor", 28), ("Imobiliária", 28), ("Venda online no CV?", 11),
                   ("Leads vinculados à venda", 14), ("Origem do lead vinculado", 32),
                   ("Conversão online na janela?", 13), ("Data da conversão online", 12), ("Resultado da análise", 36),
                   ("Origem do lead mais recente antes da venda", 34)]
        linhas = []
        for v in sorted(self.vendas, key=lambda r: (self.ordem[r["produto"]], str(r["data_venda"]), int(r["idreserva"]))):
            fill = {"caso": FILL_CASO, "perda": FILL_PERDA}.get(v["resultado"])
            linhas.append([
                v["produto"], {"valor": int(v["idreserva"]), "link": v["link_reserva"]}, _d(v["data_venda"]),
                {"valor": v["cliente"], "fill": fill}, v["unidade"], v["valor"], _situacao_cel(v), _data_distrato(v),
                CANAL.get(v["canal"], v["canal"]), v["corretor"], v["imobiliaria"],
                "Sim" if v["venda_online_cv"] else "Não", ", ".join(v["leads_vinculados"]) or "—", v["origem_vinculado"],
                "Sim" if v["online_90_dias"] else "Não", _d(v["conv_ref"]),
                {"valor": v["resultado_label"], "fill": fill, "font": FB if fill else F},
                v["origem_ultimo_lead"] or "Sem lead no CV",
            ])
        letras, ini, fim = _escrever_tabela(
            ws, 1, 1, colunas, linhas, "TodasAsVendas",
            formatos={"Data da venda": DATA, "Valor do contrato": MOEDA, "Data da conversão online": DATA,
                      "Data do distrato": DATA},
            centro={"Reserva (abre no CV)", "Data da venda", "Situação atual", "Data do distrato", "Venda online no CV?",
                    "Conversão online na janela?", "Data da conversão online"})
        ws.freeze_panes = "E2"
        return letras, ini, fim

    def _linhas_caso(self, lista):
        largura = dict(self.COLS_CASO)
        linhas, alturas = [], []
        for n, v in enumerate(lista, 1):
            ref = _lead_ref(v)
            link = _link_do_lead(ref)
            resumo, conferir = _resumo_caso(v, ref), _como_conferir(v, ref)
            registros, origem_det = _registros_tratativa(v), _detalhe_origem(ref)
            fill = FILL_PERDA if v["resultado"] == "perda" else None
            linhas.append([
                n, {"valor": v["produto"], "fill": fill}, {"valor": v["cliente"], "link": link, "fill": fill},
                {"valor": int(v["idreserva"]), "link": v["link_reserva"]}, _d(v["data_venda"]), v["valor"], v["unidade"],
                CANAL.get(v["canal"], v["canal"]), v["corretor"], v["imobiliaria"], {"valor": resumo, "fill": fill},
                _tratativa(v), conferir, {"valor": int(ref["id"]), "link": link}, ref["nome_lead"], _origem(ref),
                origem_det, _d(v["conv_ref"]), v["dias_conv_venda"], _janela_usada(v),
                "Sim" if v["sdr_humano"] else "Não", "Sim" if v["sdr_sql"] else "Não",
                "Sim" if v["sdr_assistente"] else "Não", registros, _d(v["data_precadastro"]) or "—",
                v["corretor_precadastro"] or "—", ", ".join(v["leads_vinculados"]) or "Nenhum", v["origem_vinculado"],
                _ligado_por(ref),
            ])
            alturas.append(_altura([(resumo, largura["Resumo do caso"]), (conferir, largura["Como conferir no CV"]),
                                    (registros, largura["Registros de tratativa"]),
                                    (origem_det, largura["Como a origem foi identificada"])]))
        return linhas, alturas

    def _aba_de_casos(self, nome_aba, titulo, subtitulo, lista, nome_tabela):
        ws = self.wb.create_sheet(nome_aba)
        ws.sheet_view.showGridLines = False
        ws["A1"] = titulo
        ws["A1"].font = FT
        ws["A2"] = subtitulo
        ws["A2"].font = FN
        linhas, alturas = self._linhas_caso(lista)
        letras, ini, fim = _escrever_tabela(ws, 4, 1, self.COLS_CASO, linhas, nome_tabela, formatos=self.FORM_CASO,
                                            quebra=self.QUEBRA_CASO, centro=self.CENTRO_CASO, alturas=alturas)
        ws.freeze_panes = "D5"
        return letras, ini, fim

    def aba_casos(self):
        return self._aba_de_casos(
            ABA_CASOS, ABA_CASOS,
            "Vendas que não são online no CV, com conversão online do cliente na janela (90 dias antes da compra ou "
            "pré-campanha do lançamento), sem corretor atendendo antes, e em que a conversa no CV mostra que o cliente "
            f"seguiu no atendimento e comprou com o nosso time. As que vieram do online, mas o cliente comprou com outro "
            f"corretor, estão na aba '{ABA_NAO_VIRARAM}'. Clique no nome do cliente para abrir o lead; na reserva, para "
            "abrir a reserva.",
            self.casos, "CasosParaInvestigar")

    def aba_nao_viraram(self):
        return self._aba_de_casos(
            ABA_NAO_VIRARAM, ABA_NAO_VIRARAM,
            "Vieram de lead online, mas pela conversa no CV não são venda online. Em laranja, os que atendemos e "
            "perdemos para outro corretor. Os demais não eram venda nossa (já estavam com outro corretor, não "
            "responderam, não tiveram interesse ou era pós-venda). Entram aqui também as vendas que o CV conta como "
            "online pelo lead vinculado: ter mídia online por trás não basta, quem decide é a conversa.",
            self.nao_viraram, "NaoViraramVendaOnline")

    def aba_resumo(self, LV, V_INI, UV, LC, C_INI, UC):
        ws = self.wb.create_sheet(ABA_RESUMO, 0)
        ws.sheet_view.showGridLines = False
        ws["A1"] = ABA_RESUMO
        ws["A1"].font = FT
        ws["A2"] = (f"Vendas de {self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y} (inclui distratos). Todos os números são "
                    "fórmulas sobre as abas de dados.")
        ws["A2"].font = FN
        vr = lambda n: f"'{ABA_VENDAS}'!${LV[n]}${V_INI}:${LV[n]}${UV}"
        cr = lambda n: f"'{ABA_CASOS}'!${LC[n]}${C_INI}:${LC[n]}${UC}"

        ws["A4"] = "1. Vendas do período: quantas já são online no CV e quantas viraram casos"
        ws["A4"].font = FS
        B1 = [("Produto", 38), ("Vendas", 11), ("VGV", 15), ("Distratos (incluídos)", 11), ("Vendas online no CV", 11),
              ("% online no CV", 10), ("Vendas NÃO online no CV", 12), ("…com conversão online na janela", 14),
              ("…mas o cliente comprou com outro corretor (não entram)", 14), ("CASOS PARA INVESTIGAR (vendas online)", 13),
              ("VGV dos casos", 15), ("Online no CV que a conversa desmente", 14),
              ("VENDAS ONLINE (pela conversa)", 13)]
        L1 = 6
        linhas = []
        for k, p in enumerate(self.produtos):
            i, a = L1 + k, f"$A{L1 + k}"
            base = f"{vr('Produto')},{a}"
            linhas.append([
                p, f"=COUNTIFS({base})", f"=SUMIFS({vr('Valor do contrato')},{base})",
                f'=COUNTIFS({base},{vr("Situação atual")},"Distrato")',
                f'=COUNTIFS({base},{vr("Venda online no CV?")},"Sim")', f"=IFERROR(E{i}/B{i},0)",
                f'=COUNTIFS({base},{vr("Venda online no CV?")},"Não")',
                f'=COUNTIFS({base},{vr("Venda online no CV?")},"Não",{vr("Conversão online na janela?")},"Sim")',
                "=" + "+".join(f'COUNTIFS({base},{vr("Resultado da análise")},"{r}")' for r in (JA_ATENDIA, PERDA, NAO_NOSSA)),
                {"valor": f'=COUNTIFS({base},{vr("Resultado da análise")},"{CASO}")', "font": FB, "fill": FILL_CASO},
                f'=SUMIFS({vr("Valor do contrato")},{base},{vr("Resultado da análise")},"{CASO}")',
                f'=IFERROR(E{i}-COUNTIFS({base},{vr("Resultado da análise")},"{ONLINE_SDR}")'
                f'-COUNTIFS({base},{vr("Resultado da análise")},"{ONLINE_LEAD}"),0)',
                {"valor": "=" + "+".join(f'COUNTIFS({base},{vr("Resultado da análise")},"{r}")'
                                         for r in (ONLINE_SDR, ONLINE_LEAD, CASO)), "font": FB},
            ])
        formatos = {h: (MOEDA if h.startswith("VGV") else PCT if h.startswith("%") else INT) for h, _ in B1 if h != "Produto"}
        _escrever_tabela(ws, 5, 1, B1, linhas, "QuadroVendas", formatos=formatos, centro=set(formatos), altura_cabecalho=66)
        T1 = L1 + len(self.produtos)
        _linha_total(ws, T1, 1, len(B1),
                     ["Total"] + [f"=IFERROR(E{T1}/B{T1},0)" if j == 6 else f"=SUM({get_column_letter(j)}{L1}:{get_column_letter(j)}{T1 - 1})"
                                  for j in range(2, len(B1) + 1)],
                     [None] + [formatos[h] for h, _ in B1[1:]])

        L2T = T1 + 3
        ws.cell(row=L2T, column=1, value="2. Os casos (vendas online não registradas) em detalhe").font = FS
        B2 = ([("Produto", 38), ("Casos", 9)] + [(t, 12) for t in TRATATIVA]
              + [(f"Canal: {c}", 12) for c in CANAIS_NAO_SDR] + [(f"Origem: {o}", 13) for o in ORIGENS])
        L2 = L2T + 2
        linhas = []
        for k, p in enumerate(self.produtos):
            a = f"$A{L2 + k}"
            base = f"{cr('Produto')},{a}"
            linhas.append([p, {"valor": f"=COUNTIFS({base})", "font": FB}]
                          + [f'=COUNTIFS({base},{cr("Tratativa do lead")},"{t}")' for t in TRATATIVA]
                          + [f'=COUNTIFS({base},{cr("Canal da venda no CV")},"{c}")' for c in CANAIS_NAO_SDR]
                          + [f'=COUNTIFS({base},{cr("Origem do lead")},"{o}")' for o in ORIGENS])
        _escrever_tabela(ws, L2T + 1, 1, B2, linhas, "QuadroCasos", formatos={h: INT for h, _ in B2 if h != "Produto"},
                         centro={h for h, _ in B2 if h != "Produto"}, altura_cabecalho=66)
        T2 = L2 + len(self.produtos)
        _linha_total(ws, T2, 1, len(B2),
                     ["Total"] + [f"=SUM({get_column_letter(j)}{L2}:{get_column_letter(j)}{T2 - 1})" for j in range(2, len(B2) + 1)],
                     [None] + [INT] * (len(B2) - 1))
        for j in range(1, max(len(B1), len(B2)) + 1):  # as duas tabelas dividem as colunas
            ws.column_dimensions[get_column_letter(j)].width = max(w for cols in (B1, B2) for idx, (_, w) in enumerate(cols, 1) if idx == j)
        notas = [
            "Venda online no CV: tipo de venda SDR, ou venda cujo lead vinculado à reserva tem origem online (é assim que o BI gerencial conta).",
            "Vendas online (pela conversa): as do tipo SDR, mais as que têm lead online e a conversa confirma que o cliente seguiu "
            "com a gente, mais os casos para investigar. É o número da nossa regra.",
            "Online no CV que a conversa desmente: o lead veio do online, mas não respondeu, não quis, era pós-venda ou já estava "
            "com outro corretor. O CV conta como online; nós não.",
            "Caso para investigar: venda que não é online no CV, com conversão online do cliente na janela, sem corretor atendendo antes "
            "e em que a conversa no CV mostra que o cliente seguiu com a gente e comprou com o nosso time.",
            f"Comprou com outro corretor: o corretor já atendia antes, ou a conversa mostra que o cliente seguiu com outro corretor "
            f"(aba '{ABA_NAO_VIRARAM}').",
            "Distratos continuam na análise, porque estavam vendidos na data da venda; aparecem em vermelho.",
        ]
        for k, nota in enumerate(notas, T2 + 2):
            ws.cell(row=k, column=1, value=nota).font = FN
        ws.freeze_panes = "B1"
        return T1, T2

    def aba_leia_primeiro(self, T1, T2, LV, V_INI, UV):
        ws = self.wb.create_sheet(ABA_LEIA, 0)
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["A"].width = 3
        ws["B2"] = f"Quais vendas do período são mesmo venda online · {_periodo_texto(self.inicio, self.fim)}"
        ws["B2"].font = FT
        ws["B3"] = " · ".join(self.produtos)
        ws["B3"].font = FN
        ws["B5"] = "A pergunta"
        ws["B5"].font = FS
        ws["B6"] = ("Quais vendas do período são de fato venda online — o cliente conversou com a GlorIA ou o SDR, quis seguir com a "
                    "gente e comprou com o nosso time? Ter vindo do online só diz que a venda PODERIA ser SDR: a conversa é que "
                    "decide, tanto nas que o CV não conta como online quanto nas que ele conta.")
        ws["B6"].font, ws["B6"].alignment = F, TOPO
        ws.merge_cells("B6:D6")
        ws.row_dimensions[6].height = 45

        ws["B8"] = "A resposta em números"
        ws["B8"].font = FS
        R = f"'{ABA_RESUMO}'"
        vr = lambda n: f"'{ABA_VENDAS}'!${LV[n]}${V_INI}:${LV[n]}${UV}"
        distratos = sum(1 for v in self.casos if v["situacao_atual"] == "Distrato")
        numeros = [
            ("Vendas analisadas (inclui distratos)", f"={R}!B{T1}", INT, "Lidas direto do CV, reserva a reserva.", None),
            ("Já são vendas online no CV", f"={R}!E{T1}", INT, "Venda SDR ou venda com lead online vinculado à reserva. "
             "É assim que o BI gerencial conta.", None),
            ("…mas a conversa desmente (saem do online)", f"={R}!L{T1}", INT,
             f"O lead veio do online, mas não respondeu, não quis ou seguiu com outro corretor. Aba '{ABA_NAO_VIRARAM}'.", None),
            ("VENDAS ONLINE pela nossa regra", f"={R}!M{T1}", INT,
             "Vendas SDR + vendas com lead online que a conversa confirma + os casos para investigar.", None),
            ("Não são vendas online no CV", f"={R}!G{T1}", INT,
             "Imobiliária, Time Moura Leite, interna ou sem tipo, sem lead online vinculado.", None),
            ("…com conversão online do cliente na janela", f"={R}!H{T1}", INT,
             "Nos 90 dias antes da compra ou na pré-campanha do lançamento.", None),
            ("…mas o cliente comprou com outro corretor (não é venda online)", f"={R}!I{T1}", INT,
             f"O corretor já atendia antes, ou a conversa mostra que o cliente seguiu com outro corretor. Aba '{ABA_NAO_VIRARAM}'.", None),
            ("CASOS PARA INVESTIGAR (vendas online não registradas no CV)", f"={R}!J{T1}", INT,
             f"Venda online confirmada na conversa, uma a uma na aba '{ABA_CASOS}'."
             + (f" {distratos} {'foi distratada' if distratos == 1 else 'foram distratadas'} depois." if distratos else ""),
             FILL_CASO),
            ("VGV dos casos", f"={R}!K{T1}", MOEDA, "Soma do valor de contrato dessas vendas (inclui as distratadas).", None),
            ("O que estamos perdendo: atendemos, mas o cliente comprou com outro corretor",
             f'=COUNTIFS({vr("Resultado da análise")},"{PERDA}")', INT,
             f"Conversaram com a GlorIA ou o SDR e fecharam com outro corretor. Em laranja na aba '{ABA_NAO_VIRARAM}'.", FILL_PERDA),
            ("VGV que perdemos", f'=SUMIFS({vr("Valor do contrato")},{vr("Resultado da análise")},"{PERDA}")', MOEDA,
             "Soma do valor de contrato dessas vendas.", FILL_PERDA),
            ("Casos em que o SDR tratou o lead", f"={R}!C{T2}", INT, "SAL, SQL ou atendente do SDR registrados no lead.", None),
        ]
        linhas = []
        for rotulo, formula, _, obs, fill in numeros:
            forte = fill is FILL_CASO
            linhas.append([{"valor": rotulo, "font": FB if fill else F, "fill": fill},
                           {"valor": formula, "font": FK if forte else FB, "fill": fill}, {"valor": obs, "fill": fill}])
        _escrever_tabela(ws, 9, 2, [("Indicador", 50), ("Número", 16), ("O que significa", 78)], linhas, "RespostaEmNumeros",
                         quebra={"O que significa", "Indicador"}, centro={"Número"})
        for k, (_, _, fmt, _, _) in enumerate(numeros, 10):
            ws.cell(row=k, column=3).number_format = fmt
            ws.row_dimensions[k].height = 30

        linha = 10 + len(numeros) + 1
        blocos = [
            ("Como ler esta planilha", [
                "Resumo por produto: o quadro 1 mostra as vendas de cada produto até chegar aos casos; o quadro 2 detalha os casos por tratativa, canal e origem.",
                f"{ABA_CASOS}: só as vendas que a conversa confirma como venda online, com o resumo do caso e o próximo passo. O nome do cliente abre o lead online no CV; o número da reserva abre a reserva.",
                f"{ABA_NAO_VIRARAM}: vieram do online, mas o cliente comprou com outro corretor (em laranja, os que atendemos e perdemos).",
                f"{ABA_VENDAS}: todas as vendas analisadas com o resultado de cada uma (use o filtro de 'Resultado da análise'). Os casos estão em amarelo e o que perdemos, em laranja.",
                f"{ABA_COMO}: passo a passo do cruzamento, regras, lançamentos e limites.",
            ]),
            ("Regras principais", [
                "Conta como online: campanha paga (Meta/Google, inclusive Click To WhatsApp), site e landing pages, chat, redes, BeeViral, outdoor, panfleto e rádio.",
                "Não conta: cadastro manual do corretor/imobiliária, indicação pessoal, WhatsApp (disparos e repique do comercial), ativação da base e listas importadas.",
                "Janela: conversão nos 90 dias antes da compra; nas vendas da safra de um lançamento, vale também a conversão na pré-campanha.",
                "Não basta ter vindo do online: é venda online quando o cliente conversou com a GlorIA ou o SDR, quis seguir com a gente e comprou com o nosso time. Se não respondeu, não quis ou já foi para outro corretor, não é venda online — mesmo quando o CV a conta como online pelo lead vinculado. A única exceção é o tipo 'Vendas SDR', que o próprio CV registra.",
                "Distratos: as vendas distratadas depois continuam na análise, porque estavam vendidas na data; ficam em vermelho.",
            ]),
            ("Como conferir um caso", [
                f"1. Na aba '{ABA_CASOS}', leia o 'Resumo do caso': ele começa pelo que a conversa mostra.",
                "2. Clique no nome do cliente: abre o lead online dele no CV.",
                "3. Confira se é o mesmo cliente da reserva.",
                "4. Se for, vincule o lead à reserva no CV: a venda passa a contar como online.",
            ]),
        ]
        for titulo, itens in blocos:
            ws.cell(row=linha, column=2, value=titulo).font = FS
            linha += 1
            for item in itens:
                c = ws.cell(row=linha, column=2, value=item)
                c.font, c.alignment = F, TOPO
                ws.merge_cells(start_row=linha, start_column=2, end_row=linha, end_column=4)
                ws.row_dimensions[linha].height = 30 if len(item) > 125 else 17
                linha += 1
            linha += 1
        ws.cell(row=linha, column=2, value="Uso interno: a planilha contém nomes de clientes.").font = FN

    def aba_como_foi_feito(self):
        ws = self.wb.create_sheet(ABA_COMO)
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["A"].width = 3
        ws.column_dimensions["B"].width = 120
        ws["B2"] = ABA_COMO
        ws["B2"].font = FT
        passos = [
            ("1. De onde vêm os dados",
             "Do CV, pela API: as reservas vendidas no período (tipo de venda, corretor, imobiliária, unidade, valor, "
             "compradores, situação e distrato), os pré-cadastros e os leads completos, com tags, tarefas e interações. A "
             "origem dos leads que chegam sem origem no CV é buscada na RD Station."),
            ("2. Quem comprou e quais leads essa pessoa tem",
             "O titular e os associados da reserva são cruzados com todos os leads do CV por quatro chaves: lead vinculado à "
             "reserva, e-mail, telefone (DDD + 8 últimos dígitos, só quando o nome bate com algum comprador) e nome completo "
             "único na base."),
            ("3. Venda online no CV",
             "A venda já é online no CV quando é do tipo SDR ou quando o lead vinculado à reserva tem origem online (mesma "
             "regra do BI gerencial). Essas vendas não entram nos casos."),
            ("4. Conversão online e janela",
             "Conta a conversão online (novo cadastro ou nova conversão de um lead antigo) nos 90 dias antes da compra; nas "
             "vendas da safra de um lançamento (até 90 dias depois da primeira venda), vale também a conversão com interesse "
             "no produto desde o início da pré-campanha."),
            ("5. Corretor que já atendia",
             "Pré-cadastro ou reserva antes da conversão online, lead do comercial nos 180 dias antes, lead atribuído a "
             "corretor antes, ou pré-cadastro até 3 dias depois da conversão sem SQL nem tratativa do SDR."),
            ("6. Leitura da conversa",
             "Nas vendas que sobram, a conversa dos leads online é lida: relatos da GlorIA, anotações do SDR, visitas "
             "agendadas, etapas (SQL, atendimento realizado) e motivo de cancelamento. Se o cliente conversou e seguiu no "
             "atendimento, é venda online quando comprou com o time Moura Leite e venda que perdemos quando comprou com outro "
             "corretor. Se não respondeu, não teve interesse, já estava com outro corretor ou era pós-venda, não era venda "
             "nossa. A leitura é automática e o analista pode corrigi-la na tela; a correção vale para a planilha."),
            ("7. Limites",
             "O CV não mostra o atendimento feito fora dele nem guarda a data em que o lead foi vinculado ao corretor; por isso "
             "a régua usa pré-cadastro, reserva, leads do comercial e interações datadas."),
        ]
        linha = 4
        for titulo, texto in passos:
            ws.cell(row=linha, column=2, value=titulo).font = FS
            c = ws.cell(row=linha + 1, column=2, value=texto)
            c.font, c.alignment = F, TOPO
            ws.row_dimensions[linha + 1].height = 14 * -(-len(texto) // 135) + 4
            linha += 3

        ws.cell(row=linha, column=2, value="8. Time Moura Leite considerado").font = FS
        _, _, fim = _escrever_tabela(ws, linha + 1, 2, [("Corretor", 120)], [[n] for n in TIME_MOURA_LEITE], "TimeMouraLeite")
        linha = fim + 3

        ws.cell(row=linha, column=2, value="9. Lançamentos (datas lidas nos dados)").font = FS
        linhas = []
        for produto in self.produtos:
            info = self.analise["lancamentos"].get(produto) or {}
            lancamento = _d(info.get("lancamento"))
            if not lancamento or (self.fim - lancamento).days > 365:
                continue
            linhas.append([produto, _d(info.get("inicio_pre_campanha")), lancamento, lancamento + timedelta(days=90)])
        if linhas:
            _escrever_tabela(ws, linha + 1, 2,
                             [("Produto", 120), ("Início da pré-campanha", 14), ("Lançamento (1ª venda)", 14),
                              ("Safra considerada até", 14)],
                             linhas, "Lancamentos",
                             formatos={"Início da pré-campanha": MES, "Lançamento (1ª venda)": DATA, "Safra considerada até": DATA},
                             centro={"Início da pré-campanha", "Lançamento (1ª venda)", "Safra considerada até"})
        else:
            ws.cell(row=linha + 1, column=2, value="Nenhum lançamento no último ano entre os produtos do período.").font = FN

    def gerar(self, caminho: str) -> str:
        LV, V_INI, UV = self.aba_todas_as_vendas()
        LC, C_INI, UC = self.aba_casos()
        self.aba_nao_viraram()
        T1, T2 = self.aba_resumo(LV, V_INI, UV, LC, C_INI, UC)
        self.aba_leia_primeiro(T1, T2, LV, V_INI, UV)
        self.aba_como_foi_feito()
        ordem = [ABA_LEIA, ABA_RESUMO, ABA_CASOS, ABA_NAO_VIRARAM, ABA_VENDAS, ABA_COMO]
        self.wb._sheets.sort(key=lambda ws: ordem.index(ws.title))

        self.wb.calculation = CalcProperties(fullCalcOnLoad=True)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        try:
            self.wb.save(caminho)
        except PermissionError:  # arquivo aberto no Excel: salva com outro nome
            caminho = caminho.replace(".xlsx", "_atualizado.xlsx")
            self.wb.save(caminho)
        return caminho


# ---------------------------------------------------------------------------
# Para a tela
# ---------------------------------------------------------------------------


def _cartao(v: Dict[str, Any]) -> Dict[str, Any]:
    """Uma venda de caso ou que não virou venda online, com a leitura da conversa."""
    ref = _lead_ref(v)
    leitura = v.get("leitura") or {}
    return {
        "idreserva": v["idreserva"], "produto": v["produto"], "cliente": v["cliente"], "data_venda": v["data_venda"],
        "valor": v["valor"], "situacao": v["situacao_atual"], "data_distrato": _data_distrato(v),
        "corretor": v["corretor"], "imobiliaria": v["imobiliaria"], "tipo_venda": v["tipo_venda"],
        "canal": CANAL.get(v["canal"], v["canal"]), "link_reserva": v["link_reserva"], "do_time": v["do_time"],
        "resultado": v["resultado"], "resultado_label": v["resultado_label"],
        "leitura": {
            "leitura": leitura.get("leitura"), "leitura_label": leitura_conversa.LEITURAS.get(leitura.get("leitura")),
            "motivo": leitura.get("motivo"), "motivo_label": leitura_conversa.MOTIVOS.get(leitura.get("motivo")),
            "texto": leitura.get("texto"), "destaques": leitura.get("destaques") or [],
            "trechos": leitura.get("trechos") or [], "revisada": bool(leitura.get("revisada")),
            "revisado_em": leitura.get("revisado_em"), "leitura_automatica": leitura.get("leitura_automatica"),
        },
        "conversao": _conversao(v, ref) if ref else None, "conv_ref": v["conv_ref"], "dias_conv_venda": v["dias_conv_venda"],
        "janela": _janela_usada(v), "tratativa": _tratativa(v), "registros_tratativa": _registros_tratativa(v),
        "lead": {"id": ref["id"], "nome": ref["nome_lead"], "origem": _origem(ref), "detalhe_origem": _detalhe_origem(ref),
                 "link": _link_do_lead(ref)} if ref else None,
    }


def para_a_tela(analise: Dict[str, Any]) -> Dict[str, Any]:
    """Os mesmos números e casos da planilha, no formato que a tela Analista mostra."""
    r = _Relatorio(analise)
    por_produto = []
    for produto in r.produtos:
        vendas = [v for v in r.vendas if v["produto"] == produto]
        conta = lambda *chaves: [v for v in vendas if v["resultado"] in chaves]
        online_cv = [v for v in vendas if v["venda_online_cv"]]
        casos = conta("caso")
        online = conta("online_cv_sdr", "online_cv_lead", "caso")
        por_produto.append({
            "produto": produto, "vendas": len(vendas), "vgv": round(sum(v["valor"] for v in vendas), 2),
            "online": len(online), "pct_online": round(len(online) / len(vendas) * 100, 1) if vendas else 0.0,
            "tirados_do_online": sum(1 for v in online_cv if v["resultado"] not in ("online_cv_sdr", "online_cv_lead")),
            "online_cv": len(online_cv), "pct_online_cv": round(len(online_cv) / len(vendas) * 100, 1) if vendas else 0.0,
            "com_conversao": sum(1 for v in vendas if not v["venda_online_cv"] and v["online_90_dias"]),
            "outro_corretor": len(conta("ja_atendia", "perda", "nao_nossa")),
            "casos": len(casos), "vgv_casos": round(sum(v["valor"] for v in casos), 2), "perdas": len(conta("perda")),
        })
    return {"periodo": analise["periodo"], "resumo": analise["resumo"], "por_produto": por_produto,
            "casos": [_cartao(v) for v in r.casos], "nao_viraram": [_cartao(v) for v in r.nao_viraram],
            "produtos": r.produtos, "time": analise.get("time") or list(TIME_MOURA_LEITE)}


def nome_do_arquivo(inicio: date, fim: date) -> str:
    if inicio.year == fim.year and inicio.month == fim.month:
        return f"Vendas_online_{inicio:%Y_%m}.xlsx"
    return f"Vendas_online_{inicio:%Y%m%d}_a_{fim:%Y%m%d}.xlsx"


def gerar(analise: Dict[str, Any], caminho: Optional[str] = None) -> str:
    """Escreve a planilha do período e devolve o caminho do arquivo."""
    inicio, fim = _d(analise["periodo"]["inicio"]), _d(analise["periodo"]["fim"])
    caminho = caminho or os.path.join(RELATORIOS_DIR, nome_do_arquivo(inicio, fim))
    return _Relatorio(analise).gerar(caminho)
