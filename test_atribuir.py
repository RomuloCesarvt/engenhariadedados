import sys
from engine import anuncios, bi, bases
import datetime

ini = datetime.date(2026, 9, 1)
fim = datetime.date(2026, 9, 28)

def test():
    _, leads_gen = anuncios._leads_com_anuncio(ini, fim, ['Itatinga - Novo Horizonte - 16103'])
    for lead, chave, fonte, info in leads_gen():
        if lead['id'] in [54906, 54753, 54737, 54417]:
            print(f"ID: {lead['id']} -> Chave: {chave} | Fonte: {fonte} | Info: {info}")

test()
