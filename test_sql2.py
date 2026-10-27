import sys
from engine import bi, bases, normalizer

ini = "2026-09-01"
fim = "2026-09-28"

def test():
    brutos = {str(r.get("idlead")): r for r in bases.registros("cv_leads")}
    leads_preparados = bi.leads_preparados()
    for l in leads_preparados:
        if l['empreendimento'] == 'Itatinga - Novo Horizonte - 16103' and l['data'] and ini <= l['data'].isoformat() <= fim:
            if l['etapa'] >= 2 and l['canal'] == 'meta':
                raw = brutos[str(l['id'])]
                print(f"SQL Lead: ID {l['id']}")
                print(f"  UTMs raw: {raw.get('utms')}")
                print(f"  Origem do lead: {raw.get('origem_do_lead')}, Midia: {raw.get('midia')}")

test()
