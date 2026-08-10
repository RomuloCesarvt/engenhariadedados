import sys
from engine import bi, anuncios
import datetime

ini = datetime.date(2026, 9, 1)
fim = datetime.date(2026, 9, 28)

def test():
    print("Checking SQL leads for Itatinga...")
    leads_preparados = bi.leads_preparados()
    for l in leads_preparados:
        if l['empreendimento'] == 'Itatinga - Novo Horizonte - 16103' and l['data'] and ini <= l['data'] <= fim:
            if l['etapa'] >= 2:
                print(f"SQL Lead: ID {l['id']} - Canal: {l['canal']} - Sit: {l['situacao']} - Campanha: {l.get('campanha', '')}")

test()
