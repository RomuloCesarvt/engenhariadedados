"""Leads de setembro da Reserva dos Ramos com origem fora do BI online (uso: python engine/_leads_outros_ramos.py)."""
import collections
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from engine import leads_bi  # noqa: E402

L = lambda n: json.load(open(f"output/bases/{n}.json", encoding="utf-8"))["registros"]
eid = [k for k, v in leads_bi._ids_de_empreendimento().items() if "Ramos" in v]
le = {int(x["idlead"]): x for x in L("cv_leads")}
dw = {int(x["idlead"]): x for x in L("cv_leads_dw")}
ONLINE = {"meta_ads", "Instagram Ads", "WhatsApp", "Google"}
PASSOU = {"Em tratativa Corretor", "Lead Vinculado ao Corretor", "Lead Qualificado (SQL)", "Vendido"}
CORES = {"Virou venda": "D5F5E3", "Só lead (não conta)": "FFFFFF"}
saida = []
for c in leads_bi._ultima_conversao_de_cada_lead().values():
    if str(c["data_cad"])[:7] != "2026-09" or str(c.get("empreendimento_ultimo")) not in eid or (c["midia_conversao"] or "") in ONLINE:
        continue
    i = int(c["idlead"])
    x, w = le.get(i, {}), dw.get(i, {})
    tags = x.get("tags") or []
    mia = any(t.lower().startswith("mia") for t in tags)
    transf = "mia-transferido-corretor" in tags or w.get("situacao") in PASSOU
    midia = c["midia_conversao"] or "(sem origem)"
    manual = midia.startswith("Painel")
    vendeu = w.get("situacao") == "Vendido"
    if vendeu:
        v = "Virou venda"
    else:
        v = "Só lead (não conta)"
    real = ", ".join(m for m in (x.get("midias") or []) if not str(m).startswith("Painel")) or str(x.get("origem") or "")
    nota = ("reserva vendida no CV" if vendeu else "não há reserva vendida no CV para este lead") + ("; a assistente transferiu para o corretor" if transf else "; sem transferência registrada")
    if manual:
        nota += "; cadastrado/reaberto pelo painel, a origem verdadeira ficou escondida"
    if not c["midia_conversao"]:
        nota += "; o lead chegou sem origem (UTM), a conversão é só 'Não Definido | M.I.A'"
    saida.append(dict(id=i, data=str(c["data_cad"])[:10], midia=midia, real=real or "—", sit=w.get("situacao", ""), corretor=(x.get("corretor") or {}).get("nome") or "", v=v, nota=nota,
                      link=f"https://mouraleite.cvcrm.com.br/gestor/comercial/leads/{i}/administrar"))
saida.sort(key=lambda s: (list(CORES).index(s["v"]), s["data"]))
wb = Workbook()
ws = wb.active
ws.title = "Resumo"
ws.append(["Reserva dos Ramos, setembro: leads com origem fora do online do BI", len(saida)])
for k, n in collections.Counter(s["v"] for s in saida).items():
    ws.append([k, n])
ws.column_dimensions["A"].width = 70
COL = [("Lead", 9), ("Data", 12), ("Origem na conversão", 22), ("Origem real (mídias)", 24), ("Situação no CV", 30), ("Corretor", 36), ("Resultado", 22), ("Por quê", 85), ("Link", 9)]
w = wb.create_sheet("Leads")
w.append([c[0] for c in COL])
for k, (_, larg) in enumerate(COL, 1):
    w.column_dimensions[get_column_letter(k)].width = larg
    w.cell(row=1, column=k).font = Font(bold=True, color="FFFFFF")
    w.cell(row=1, column=k).fill = PatternFill("solid", fgColor="1B4F38")
for s in saida:
    w.append([s["id"], s["data"], s["midia"], s["real"], s["sit"], s["corretor"], s["v"], s["nota"], "abrir"])
    r = w.max_row
    w.cell(row=r, column=9).hyperlink = s["link"]
    w.cell(row=r, column=9).font = Font(color="0563C1", underline="single")
    for k in range(1, 9):
        w.cell(row=r, column=k).fill = PatternFill("solid", fgColor=CORES[s["v"]])
w.freeze_panes = "B2"
wb.save("output/relatorios/Reserva_dos_Ramos_leads_outros_que_viraram_venda_2026_09.xlsx")
print(len(saida), collections.Counter(s["v"] for s in saida))
for s in saida:
    if s["v"] == "Virou venda":
        print(s["id"], s["data"], s["sit"], s["corretor"])
