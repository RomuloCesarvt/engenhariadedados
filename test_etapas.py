import sys
from engine import anuncios
import datetime

ini = datetime.date(2026, 9, 1)
fim = datetime.date(2026, 9, 28)

def test():
    _a, leads = anuncios._leads_com_anuncio(ini, fim, ['Itatinga - Novo Horizonte - 16103'])
    for l, c, f, i in leads():
        if c and 'novo-horizonte_imagem-sucesso' in c:
            print(f"ID: {l['id']} - Etapa: {l['etapa']} - Sit: {l['situacao']} - Data: {l['data']}")

test()
