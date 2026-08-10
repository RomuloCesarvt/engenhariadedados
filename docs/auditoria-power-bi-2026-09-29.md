# Auditoria dos Power BIs e do Moura Leite BI

Auditoria feita em 29/09/2026, com o recorte de 01/09/2026 a 30/09/2026, praça e empreendimento sem seleção. No Power BI FM&D, o Gerencial foi analisado com o filtro Online (`tipo = On`).

## Fontes comparadas

- Power BI FM&D: relatório de Follow Up e Gerencial, atualizado em 29/09/2026 às 12:30:03. O Gerencial foi conferido com `tipo = On`.
- Power BI Moura Leite (`comercial-mldu`): metadado do modelo semântico atualizado em 29/09/2026 às 09:15:42; algumas páginas usam fatos com comportamentos de atualização diferentes.
- Moura Leite BI: API direta do CV, Meta, Google, RD Station e BeeViral. Neste snapshot, leads atualizados às 14:23 e reservas às 13:51.

O modelo do Power BI Moura Leite usa tabelas separadas para cada fato:

- `mouraleite vw_dim_leads`
- `mouraleite vw_fato_conversoes`
- `mouraleite vw_fato_qualificacoes`
- `mouraleite vw_fato_opps`
- `mouraleite vw_fato_visitas`
- `mouraleite vw_fato_vendas`
- `mouraleite vw_origens_normalizadas`
- `mouraleite reservas` e `mouraleite vendas`

Isso confirma que os cartões não partem todos da mesma linha, data ou granularidade.

## Resultado da comparação

| Indicador | Power BI FM&D | Power BI Moura Leite | Moura Leite BI local | Conclusão |
|---|---:|---:|---:|---|
| Conversões únicas | 989 | - | não reconstruível pela API atual | O Power BI FM&D usa a fato histórica de conversões; o CV expõe só a última conversão atual do lead. |
| Novo Lead MQL | 825 | - | não reconstruível pela API atual | O Power BI FM&D conta a mudança para a etapa no período, não o cadastro nem apenas o estado atual. |
| MQL por última conversão | - | 890 | 894 | O app reproduz a regra do Power BI Moura Leite em uma extração posterior; a comparação exata exige o mesmo instante de atualização. |
| SQL | 259 | 329 no cartão, 258 na tabela | 279 detectados no histórico | O Power BI FM&D e a tabela do Power BI Moura Leite quase fecham; o app identifica sua medida como estimativa até receber a fato. |
| Agendamentos | 2 | 12 | 42 detectados no histórico | Os três usam datas e sinais diferentes. |
| Atendimentos | 3 | 5 | 24 detectados no histórico | Os três usam datas e sinais diferentes. |
| Vendas SDR online | 8 | não comparável | 9 | O app vincula a reserva 16410 ao lead 21809, cuja mídia no CV é Blip; o Power BI FM&D não inclui essa venda no recorte On. No Power BI Moura Leite, Vendas não responde ao filtro de origem. |
| Unidades vendidas online | não disponível de forma confiável | não disponível de forma confiável | 29 | Os cartões gerais dos dois Power BIs ignoram o filtro de origem e não entram na comparação online. |
| VGV online | não disponível de forma confiável | não disponível de forma confiável | R$ 2.332.040,37 | O app soma apenas reservas vinculadas a leads classificados como online. |

## Causas comprovadas

1. **Os funis da FM&D e da Moura Leite chamam populações diferentes de MQL.** O Power BI FM&D conta a transição para `Novo Lead MQL` (825); o Power BI Moura Leite conta pessoas online por última conversão (890).
2. **O SQL do Power BI Moura Leite se contradiz.** O cartão mostra 329 e a tabela 258 no mesmo recorte. A tabela do Power BI Moura Leite e o Power BI FM&D (259) diferem por uma pessoa, compatível com horário de atualização.
3. **O filtro Online do Power BI FM&D é parcial.** Na página Follow Up, selecionar `On` muda SQL, agendamentos e descartes, mas não muda leads, vendas nem VGV. Por isso esses cartões não são usados como números online.
4. **Vendas e VGV do Power BI Moura Leite ignoram Origem (Online).** Ao selecionar somente Google, MQL, SQL e agendamentos diminuem como esperado, mas Vendas e VGV permanecem iguais. Esses dois cartões não representam a seleção online.
5. **A venda 16410 explica a diferença online mais próxima.** O app liga a reserva ao lead 21809, classificado como Blip, e por isso chega a 9 vendas SDR online; o Power BI FM&D não mostra essa linha entre as 8 vendas filtradas.
6. **O Power BI FM&D quebra Novo Horizonte de Itatinga.** A matriz usa a chave 16101 e o filtro usa a chave oficial 16103.
7. **Investimento não tem o mesmo escopo.** O Power BI FM&D zera Google em parte dos visuais e usa apenas parte das contas Meta; o app consulta as contas conectadas diretamente.

## Contrato adotado no Moura Leite BI

- **Interesses cadastrados:** uma linha por interesse e `data_cad` no período.
- **Pessoas cadastradas:** `DISTINCTCOUNT(idlead)` por `data_cad`.
- **MQL por movimentação:** uma pessoa online por `ultima_data_conversao` no período.
- **Novo Lead MQL por transição:** indisponível até a ingestão da fato histórica; o app não inventa esse número a partir do estado atual.
- **SQL detectado no histórico:** situação, tags e tarefas. Fica identificado como estimativa até o acesso à `vw_fato_qualificacoes`.
- **Unidades vendidas online:** uma reserva vendida, pela `data_venda` e empreendimento da unidade comprada, vinculada a lead com origem online.
- **Vendas SDR online:** `tipo_venda = 'Vendas SDR'`, restrita às reservas vinculadas a leads classificados como online.
- **Venda online sem tipo:** continua no total online e vira pendência de qualidade; nunca é removida silenciosamente.
- **Investimento:** valor direto das APIs Meta e Google, com as contas e o horário da extração visíveis.

## Correções necessárias nos Power BIs

1. Fazer Vendas e VGV receberem a mesma dimensão de origem aplicada a MQL, SQL e OPPS.
2. Usar uma linha por `idreserva` antes de somar quantidade e VGV online.
3. Fazer o cartão SQL reutilizar a mesma medida da tabela e da conversão.
4. Nomear explicitamente cadastro, conversão, qualificação, reserva iniciada, unidade vendida online e tipo SDR online.
5. Corrigir a chave 16101 para 16103 em todas as fatos e dimensões.
6. Exibir data e hora da atualização em todas as páginas.
7. Publicar a fórmula DAX e a data de referência de cada KPI.
8. Fazer o filtro `tipo = On` alcançar todas as medidas da página Follow Up.
