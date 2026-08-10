'use client';

/** O conteúdo de cada slide da apresentação. Cada um lê só o que precisa de `Apresentacao`. */

import React, { useEffect, useState } from 'react';
import { fetchCapa, urlImagemAnuncio } from '../../lib/biApi';
import { empreendimentoCurto, numero, pct, reais, reaisCentavos, reaisCompacto } from '../../lib/format';
import {
  Apresentacao,
  Anunciante,
  AnuncioRanking,
  BlocoFonte,
  BlocoCanalMeta,
  MetasLeads,
  AnuncioNovo,
  AnunciosNovos,
  AnuncioGoogle,
  BlocoCenario,
  Cenario,
  CenarioPraca,
  CriterioAnuncio,
  CriterioGoogle,
  GrupoCriativo,
  TermoPesquisa,
  TermosGrupo,
  VariacaoBloco,
} from '../../types/apresentacao';
import { COR } from './Slide';

type Melhor = 'subir' | 'descer' | 'neutro';

// ---------------------------------------------------------------------------
// Peças
// ---------------------------------------------------------------------------

function Var({ valor, melhor = 'subir', tamanho = 14 }: { valor: number | null | undefined; melhor?: Melhor; tamanho?: number }) {
  if (valor === null || valor === undefined) return <span style={{ color: COR.mudo, fontSize: tamanho }}>—</span>;
  const zero = Math.abs(valor) < 0.05;
  const bom = melhor === 'neutro' || zero ? null : melhor === 'subir' ? valor > 0 : valor < 0;
  const cor = bom === null ? COR.mudo : bom ? COR.bom : COR.ruim;
  const seta = zero ? '' : valor > 0 ? '▲ ' : '▼ ';
  return (
    <span style={{ color: cor, fontSize: tamanho, fontWeight: 600, whiteSpace: 'nowrap' }}>
      {seta}
      {Math.abs(valor).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%
    </span>
  );
}

function Tile({
  rotulo,
  valor,
  sub,
  variacao,
  melhor,
  destaque,
}: {
  rotulo: string;
  valor: string;
  sub?: string;
  variacao?: number | null;
  melhor?: Melhor;
  destaque?: boolean;
}) {
  return (
    <div
      style={{
        flex: 1,
        borderRadius: 14,
        padding: '16px 20px',
        background: destaque ? COR.escuro : COR.claro,
        color: destaque ? '#fff' : COR.texto,
        minWidth: 0,
      }}
    >
      <p style={{ fontSize: 14, margin: 0, opacity: destaque ? 0.85 : 1, color: destaque ? '#fff' : COR.mudo, fontWeight: 600 }}>{rotulo}</p>
      <p style={{ fontSize: 40, fontWeight: 800, margin: '4px 0 2px', lineHeight: 1.1 }}>{valor}</p>
      <p style={{ fontSize: 13, margin: 0, display: 'flex', gap: 8, alignItems: 'center', color: destaque ? '#d6ecd2' : COR.mudo }}>
        {variacao !== undefined && (
          <span style={{ background: '#fff', borderRadius: 6, padding: '1px 6px' }}>
            <Var valor={variacao} melhor={melhor} tamanho={13} />
          </span>
        )}
        {sub}
      </p>
    </div>
  );
}

const celula: React.CSSProperties = { padding: '8px 10px', borderBottom: `1px solid ${COR.linha}`, fontSize: 15, verticalAlign: 'middle' };

function Tabela({ colunas, linhas, tamanho = 15 }: { colunas: { rotulo: string; alinhar?: 'left' | 'right'; largura?: number }[]; linhas: React.ReactNode[][]; tamanho?: number }) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
      <thead>
        <tr>
          {colunas.map((c) => (
            <th
              key={c.rotulo}
              style={{
                ...celula,
                fontSize: 12.5,
                fontWeight: 700,
                color: COR.mudo,
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                textAlign: c.alinhar ?? 'left',
                width: c.largura,
                borderBottom: `2px solid ${COR.escuro}`,
              }}
            >
              {c.rotulo}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((l, i) => (
          <tr key={i}>
            {l.map((v, j) => (
              <td key={j} style={{ ...celula, fontSize: tamanho, textAlign: colunas[j].alinhar ?? 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {v}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Barra({ valor, maximo, cor = COR.verde }: { valor: number; maximo: number; cor?: string }) {
  return (
    <div style={{ height: 10, borderRadius: 5, background: COR.claro, overflow: 'hidden', flex: 1 }}>
      <div style={{ height: '100%', width: `${maximo ? Math.max(2, (valor / maximo) * 100) : 0}%`, background: cor, borderRadius: 5 }} />
    </div>
  );
}

function Titulo({ children, sub }: { children: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ fontSize: 19, fontWeight: 700, margin: 0, color: COR.escuro }}>{children}</p>
      {sub && <p style={{ fontSize: 13.5, margin: '2px 0 0', color: COR.mudo }}>{sub}</p>}
    </div>
  );
}

function SemDados({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: '28px 20px', borderRadius: 12, background: COR.laranjaClaro, color: '#8a4a00', fontSize: 16, textAlign: 'center' }}>
      {children}
    </div>
  );
}

const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

// ---------------------------------------------------------------------------
// 1. Resumo
// ---------------------------------------------------------------------------

export function SlideResumo({ d }: { d: Apresentacao }) {
  const { resumo: r } = d;
  const t = r.total;
  const v = r.variacao.total;
  const ordem = d.fontes.filter((f) => r.fontes[f.chave].leads > 0 || r.fontes[f.chave].investimento > 0);

  const linha = (nome: React.ReactNode, b: BlocoFonte, var_: VariacaoBloco, total: number, negrito = false) => {
    const f = negrito ? 700 : 500;
    return [
      <strong key="n" style={{ fontWeight: negrito ? 800 : 600 }}>{nome}</strong>,
      <span key="l" style={{ fontWeight: f }}>{numero(b.leads)}</span>,
      <Var key="v" valor={var_.leads} />,
      <span key="p">{total ? pct((b.leads / total) * 100) : '—'}</span>,
      <span key="i">{b.investimento ? reais(b.investimento) : '—'}</span>,
      <span key="c" style={{ fontWeight: f }}>
        {reaisCentavos(b.cpl)}
        {b.cpl_com_whatsapp ? <span style={{ display: 'block', fontSize: 11, fontWeight: 500, color: COR.mudo }}>piso {reaisCentavos(b.cpl_com_whatsapp)} (+WhatsApp sem marca orgânica)</span> : null}
      </span>,
      <span key="cp" style={{ color: COR.mudo }}>{b.cpl_plataforma !== undefined ? reaisCentavos(b.cpl_plataforma) : '—'}</span>,
      <span key="s" style={{ fontWeight: f }}>{numero(b.sql)}</span>,
      <span key="ps">{pct(b.pct_sql)}</span>,
    ];
  };

  return (
    <>
      <div style={{ display: 'flex', gap: 16 }}>
        <Tile destaque rotulo="Investimento (Meta + Google)" valor={reaisCompacto(t.investimento)} variacao={v.investimento} melhor="neutro" sub="vs mês anterior" />
        <Tile rotulo="Leads online" valor={numero(t.leads)} variacao={v.leads} sub={`${numero(t.leads_pagos)} de mídia paga`} />
        <Tile rotulo="CPL (pago)" valor={reaisCentavos(t.cpl)} variacao={v.cpl} melhor="descer" sub={t.cpl_com_whatsapp ? `piso ${reaisCentavos(t.cpl_com_whatsapp)} com WhatsApp de anúncio provável` : 'investimento ÷ leads pagos'} />
        <Tile rotulo="Leads qualificados (SQL*)" valor={numero(t.sql)} variacao={v.sql} sub={`${pct(t.pct_sql)} dos leads${t.opps != null ? ` · ${t.opps} em OPPS` : ''}`} />
      </div>
      <div style={{ marginTop: 22 }}>
        <Titulo sub="Leads contados pela data de cadastro no CV, como no BI da gestão. Variação contra o mesmo intervalo do mês anterior.">Leads por fonte</Titulo>
        <Tabela
          colunas={[
            { rotulo: 'Fonte', largura: 200 },
            { rotulo: 'Leads', alinhar: 'right', largura: 80 },
            { rotulo: 'vs mês ant.', alinhar: 'right', largura: 110 },
            { rotulo: '% do total', alinhar: 'right', largura: 100 },
            { rotulo: 'Investimento', alinhar: 'right', largura: 130 },
            { rotulo: 'CPL no CV', alinhar: 'right', largura: 120 },
            { rotulo: 'CPL plataforma', alinhar: 'right', largura: 140 },
            { rotulo: 'SQL*', alinhar: 'right', largura: 70 },
            { rotulo: '% SQL', alinhar: 'right', largura: 80 },
          ]}
          linhas={[
            ...ordem.map((f) => linha(f.label, r.fontes[f.chave], r.variacao.fontes[f.chave], t.leads)),
            linha('Total', t, v, t.leads, true),
          ]}
        />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// 2. Origem dos leads
// ---------------------------------------------------------------------------

export function SlideOrigem({ d }: { d: Apresentacao }) {
  const { resumo: r, organicos: o } = d;
  const fontes = d.fontes.map((f) => ({ ...f, b: r.fontes[f.chave] })).filter((f) => f.b.leads > 0).sort((a, b) => b.b.leads - a.b.leads);
  const maxF = Math.max(1, ...fontes.map((f) => f.b.leads));
  const maxO = Math.max(1, ...o.por_origem.map((i) => i.leads));
  const cores: Record<string, string> = { meta: COR.azul, google: '#d9822b', organico: COR.verde, indicacao: '#7a4fb5', pago_outro: COR.mudo };

  return (
    <div style={{ display: 'flex', gap: 40, flex: 1, minHeight: 0 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Titulo sub={`${numero(r.total.leads)} leads online no período`}>De onde vêm os leads</Titulo>
        {fontes.map((f) => (
          <div key={f.chave} style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 16, marginBottom: 5 }}>
              <strong>{f.label}</strong>
              <span>
                <strong>{numero(f.b.leads)}</strong> · {pct((f.b.leads / r.total.leads) * 100)}{' '}
                <Var valor={r.variacao.fontes[f.chave].leads} tamanho={13} />
              </span>
            </div>
            <Barra valor={f.b.leads} maximo={maxF} cor={cores[f.chave]} />
          </div>
        ))}
      </div>

      <div style={{ flex: 1.15, minWidth: 0 }}>
        <Titulo sub={`Origem de cada lead não pago, como no BI · ${numero(d.resumo.fontes.organico.leads)} leads`}>De onde vieram os orgânicos</Titulo>
        {o.por_origem.length === 0 ? (
          <SemDados>Nenhum lead orgânico no período.</SemDados>
        ) : (
          o.por_origem.map((i) => (
            <div key={i.origem} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '6px 0', borderBottom: `1px solid ${COR.linha}` }}>
              <div style={{ width: 290, minWidth: 0 }}>
                <p style={{ fontSize: 15.5, fontWeight: 600, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{i.origem}</p>
                {i.canal && i.canal !== '—' && <p style={{ fontSize: 12, margin: 0, color: COR.mudo }}>{i.canal}</p>}
              </div>
              <Barra valor={i.leads} maximo={maxO} />
              <span style={{ width: 90, textAlign: 'right', fontSize: 15 }}>
                <strong>{numero(i.leads)}</strong> · {pct(i.pct)}
              </span>
              <span style={{ width: 70, textAlign: 'right', fontSize: 13, color: COR.mudo }}>{i.sql} SQL</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Por empreendimento
// ---------------------------------------------------------------------------

export function SlideEmpreendimentos({ d }: { d: Apresentacao }) {
  const linhas = d.por_empreendimento.slice(0, 10);
  if (!linhas.length) return <SemDados>Nenhum lead no período para o filtro escolhido.</SemDados>;
  const tot = linhas.reduce(
    (t, e) => ({ meta: t.meta + e.invest_meta, google: t.google + e.invest_google, leads: t.leads + e.leads, sql: t.sql + e.sql, vendas: t.vendas + e.vendas, pagos: t.pagos + e.meta + e.google, lm: t.lm + e.meta, lg: t.lg + e.google, lo: t.lo + e.organico, lc: t.lc + (e.meta_ctw ?? 0), lf: t.lf + (e.meta_form ?? 0) }),
    { meta: 0, google: 0, leads: 0, sql: 0, vendas: 0, pagos: 0, lm: 0, lg: 0, lo: 0, lc: 0, lf: 0 }
  );
  const investTotal = tot.meta + tot.google;
  return (
    <>
      <Tabela
        tamanho={14}
        colunas={[
          { rotulo: 'Empreendimento' },
          { rotulo: 'Meta (R$)', alinhar: 'right', largura: 92 },
          { rotulo: 'Google (R$)', alinhar: 'right', largura: 96 },
          { rotulo: 'Leads Meta (CTW · form.)', alinhar: 'right', largura: 150 },
          { rotulo: 'Leads Google', alinhar: 'right', largura: 80 },
          { rotulo: 'Orgânico', alinhar: 'right', largura: 76 },
          { rotulo: 'Total', alinhar: 'right', largura: 62 },
          { rotulo: 'CPL', alinhar: 'right', largura: 84 },
          { rotulo: 'SQL', alinhar: 'right', largura: 54 },
          { rotulo: '% SQL', alinhar: 'right', largura: 66 },
          { rotulo: 'Custo/SQL', alinhar: 'right', largura: 92 },
          { rotulo: 'Vendas', alinhar: 'right', largura: 66 },
        ]}
        linhas={[
          ...linhas.map((e) => [
            <strong key="e">{empreendimentoCurto(e.empreendimento)}</strong>,
            e.invest_meta ? reais(e.invest_meta) : '—',
            e.invest_google ? reais(e.invest_google) : '—',
            <span key="m">{numero(e.meta)} <span style={{ color: COR.mudo, fontSize: 11.5 }}>({numero(e.meta_ctw ?? 0)} · {numero(e.meta_form ?? 0)})</span></span>,
            numero(e.google),
            numero(e.organico),
            <strong key="l">{numero(e.leads)}</strong>,
            reaisCentavos(e.cpl),
            numero(e.sql),
            pct(e.pct_sql),
            e.custo_sql ? reais(e.custo_sql) : '—',
            numero(e.vendas),
          ]),
          [
            <strong key="t">Total listado</strong>,
            <strong key="m">{reais(tot.meta)}</strong>,
            <strong key="g">{reais(tot.google)}</strong>,
            <strong key="lm">{numero(tot.lm)} <span style={{ fontWeight: 400, fontSize: 11.5 }}>({numero(tot.lc)} · {numero(tot.lf)})</span></strong>,
            <strong key="lg">{numero(tot.lg)}</strong>,
            <strong key="lo">{numero(tot.lo)}</strong>,
            <strong key="l">{numero(tot.leads)}</strong>,
            <strong key="c">{tot.pagos ? reaisCentavos(investTotal / tot.pagos) : '—'}</strong>,
            <strong key="s">{numero(tot.sql)}</strong>,
            <strong key="p">{tot.leads ? pct((tot.sql / tot.leads) * 100) : '—'}</strong>,
            <strong key="cs">{tot.sql && investTotal ? reais(investTotal / tot.sql) : '—'}</strong>,
            <strong key="v">{numero(tot.vendas)}</strong>,
          ],
        ]}
      />
      <p style={{ fontSize: 12.5, color: COR.mudo, margin: '8px 0 0' }}>
        CPL = (Meta + Google) ÷ leads dessas duas fontes. Custo/SQL = (Meta + Google) ÷ SQL do empreendimento. “Total” inclui orgânicos e indicação. Vendas: leads do período que já viraram venda.
      </p>
    </>
  );
}

// ---------------------------------------------------------------------------
// 4. Anúncios campeões
// ---------------------------------------------------------------------------

function Capa({ ad, tamanho = 150 }: { ad: AnuncioRanking; tamanho?: number }) {
  const [url, setUrl] = useState<string | null>(ad.miniatura);
  const [falhou, setFalhou] = useState(false);
  const id = ad.anuncio_ids[ad.anuncio_ids.length - 1];

  useEffect(() => {
    // A imagem é sempre a do anúncio mostrado: ao trocar de anúncio (ou de praça), volta para a miniatura dele
    setUrl(ad.miniatura);
    setFalhou(false);
    if (!id || ad.sem_dados_da_plataforma) return;
    let vivo = true;
    fetchCapa(id)
      .then((c) => vivo && c.url && setUrl(c.url))
      .catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, [id, ad.miniatura, ad.sem_dados_da_plataforma]);

  return (
    <div style={{ width: tamanho, height: tamanho, flexShrink: 0, borderRadius: 12, background: COR.claro, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {url && !falhou ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={urlImagemAnuncio(url)} alt="" onError={() => setFalhou(true)} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
      ) : (
        <span style={{ fontSize: 13, color: COR.mudo, textAlign: 'center', padding: 10 }}>Sem imagem na Meta</span>
      )}
    </div>
  );
}

const num1 = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString('pt-BR', { maximumFractionDigits: 1 }));

function destaqueDoCriterio(c: CriterioAnuncio, a: AnuncioRanking): { valor: string; detalhe: string } {
  switch (c.metrica) {
    case 'cpl_real':
      return { valor: reaisCentavos(a.cpl_efetivo ?? a.cpl_real), detalhe: a.base_leads === 'Meta' ? 'por lead (leads da Meta)' : 'por lead' };
    case 'leads_cv':
      return { valor: num1(a.leads_efetivos ?? a.leads_cv), detalhe: a.base_leads === 'Meta' ? 'leads (registrados pela Meta)' : 'leads' };
    case 'sql':
      return { valor: num1(a.sql_efetivo ?? a.sql), detalhe: `SQL · ${pct(a.taxa_sql_efetiva ?? a.taxa_sql)} dos leads${(a.sql_est ?? 0) > 0 ? ' (parte estimada)' : ''}` };
    case 'taxa_sql':
      return { valor: pct(a.taxa_sql_efetiva ?? a.taxa_sql), detalhe: `${num1(a.sql_efetivo ?? a.sql)} SQL de ${num1(a.leads_total ?? a.leads_cv)} leads${(a.sql_est ?? 0) > 0 ? ' (estimado)' : ''}` };
    default:
      return { valor: pct(a.taxa_venda), detalhe: `${a.vendas} venda(s) de ${a.leads_cv} leads` };
  }
}

function CartaoCampeao({ c }: { c: CriterioAnuncio }) {
  const [topo, ...resto] = c.ranking;
  return (
    <div style={{ border: `1px solid ${COR.linha}`, borderRadius: 14, padding: '12px 16px', display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0, overflow: 'hidden' }}>
      <p style={{ fontSize: 13, fontWeight: 800, color: COR.laranja, letterSpacing: 0.6, textTransform: 'uppercase', margin: '0 0 8px' }}>{c.titulo}</p>
      {!topo ? (
        <p style={{ fontSize: 14.5, color: COR.mudo, margin: 'auto 0' }}>{c.motivo_vazio}</p>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 16, minHeight: 0 }}>
            <Capa key={topo.chave} ad={topo} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <p style={{ fontSize: 16, fontWeight: 700, margin: 0, lineHeight: 1.25, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {topo.anuncio}
              </p>
              <p style={{ fontSize: 12.5, color: COR.mudo, margin: '2px 0 4px' }}>{empreendimentoCurto(topo.empreendimento)}</p>
              <p style={{ fontSize: 34, fontWeight: 800, color: COR.verde, margin: 0, lineHeight: 1 }}>{destaqueDoCriterio(c, topo).valor}</p>
              <p style={{ fontSize: 13, color: COR.mudo, margin: '2px 0 6px' }}>{destaqueDoCriterio(c, topo).detalhe}</p>
              <p style={{ fontSize: 13, margin: 0, lineHeight: 1.4 }}>
                {num1(topo.leads_efetivos ?? topo.leads_cv)} leads{topo.base_leads === 'Meta' ? ' (Meta)' : ''} · {num1(topo.sql_efetivo ?? topo.sql)} SQL{(topo.sql_est ?? 0) > 0 ? ' (est.)' : ''} · {numero(topo.vendas)} venda(s)
                <br />
                {topo.sem_dados_da_plataforma
                  ? 'Anúncio fora das contas lidas da Meta'
                  : `${reais(topo.investimento)} investidos · CPL ${reaisCentavos(topo.cpl_efetivo ?? topo.cpl_real)}`}
              </p>
            </div>
          </div>
          {resto.length > 0 && (
            <div style={{ marginTop: 'auto', paddingTop: 6, fontSize: 12, color: COR.mudo, lineHeight: 1.45 }}>
              {resto.map((a, i) => (
                <div key={a.chave} style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {i + 2}º {a.anuncio}
                  </span>
                  <strong style={{ color: COR.texto, whiteSpace: 'nowrap' }}>{destaqueDoCriterio(c, a).valor}</strong>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function SlideAnuncios({ d, praca }: { d: Apresentacao; praca?: string }) {
  const bloco = praca ? d.anuncios_por_praca?.[praca] : d.anuncios;
  if (!bloco || (!praca && !d.anuncios.disponivel)) return <SemDados>Sem anúncios da Meta com investimento ou lead nesta praça no período.</SemDados>;
  return (
    <>
      {praca && 'leads_da_plataforma' in bloco && bloco.leads_da_plataforma && (
        <p style={{ fontSize: 12.5, color: '#8a4a00', background: COR.laranjaClaro, borderRadius: 8, padding: '5px 10px', margin: '0 0 8px' }}>
          O CV não ligou leads a anúncios desta praça: o ranking usa os leads que a própria Meta registra em cada anúncio (SQL e conversão em venda não se aplicam).
        </p>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr', gap: 14, flex: 1, minHeight: 0, paddingBottom: 4 }}>
        {bloco.criterios.map((c) => (
          <CartaoCampeao key={c.id} c={c} />
        ))}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// 5. Termos de pesquisa do Google (Performance Max e pesquisa)
// ---------------------------------------------------------------------------

function ListaTermos({ titulo, sub, termos, mostrar }: { titulo: string; sub: string; termos: TermoPesquisa[]; mostrar: 'cliques' | 'conversoes' }) {
  const max = Math.max(1, ...termos.map((t) => (mostrar === 'cliques' ? t.cliques : t.conversoes)));
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <Titulo sub={sub}>{titulo}</Titulo>
      {termos.length === 0 ? (
        <SemDados>Sem termos no período.</SemDados>
      ) : (
        termos.slice(0, 9).map((t) => (
          <div key={t.termo} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '5px 0', borderBottom: `1px solid ${COR.linha}` }}>
            <span style={{ width: 215, fontSize: 14.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.termo}>
              {t.termo}
            </span>
            <Barra valor={mostrar === 'cliques' ? t.cliques : t.conversoes} maximo={max} cor={mostrar === 'cliques' ? COR.verde : COR.laranja} />
            <span style={{ width: 50, textAlign: 'right', fontSize: 14 }}>
              <strong>{mostrar === 'cliques' ? numero(t.cliques) : t.conversoes.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}</strong>
            </span>
            <span style={{ width: 78, textAlign: 'right', fontSize: 12.5, color: COR.mudo }}>
              {mostrar === 'cliques' ? reais(t.investimento) : `${reaisCentavos(t.custo_por_conversao)}`}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

function SlideDeTermos({ g, tipo }: { g: TermosGrupo; tipo: string }) {
  const resumo = `${numero(g.cliques)} cliques · ${reais(g.investimento)} · ${numero(g.conversoes)} conversões · ${numero(g.termos_distintos)} termos${g.cobertura !== null ? ` · explicam ${pct(g.cobertura)} dos cliques da campanha` : ''}`;
  return (
    <div style={{ display: 'flex', gap: 36, flex: 1, minHeight: 0 }}>
      <ListaTermos titulo={`${tipo}: mais buscados`} sub={`${resumo}. À direita: custo no período.`} termos={g.mais_cliques} mostrar="cliques" />
      <ListaTermos titulo={`${tipo}: os que mais converteram`} sub="Conversões da conta do Google. À direita: custo por conversão." termos={g.mais_conversoes} mostrar="conversoes" />
    </div>
  );
}

export function SlideTermosPmax({ d }: { d: Apresentacao }) {
  return <SlideDeTermos g={d.google.termos.pmax} tipo="Performance Max" />;
}

export function SlideTermosPesquisa({ d }: { d: Apresentacao }) {
  return <SlideDeTermos g={d.google.termos.pesquisa} tipo="Pesquisa" />;
}

// ---------------------------------------------------------------------------
// 6. Google: campanhas e palavras-chave
// ---------------------------------------------------------------------------

export function SlideGoogle({ d }: { d: Apresentacao }) {
  const { campanhas, palavras_chave: palavras } = d.google;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <Titulo>Campanhas do Google</Titulo>
        {campanhas.length === 0 ? (
          <SemDados>Sem investimento no Google no período.</SemDados>
        ) : (
          <Tabela
            tamanho={14}
            colunas={[
              { rotulo: 'Campanha' },
              { rotulo: 'Tipo', largura: 130 },
              { rotulo: 'Investimento', alinhar: 'right', largura: 120 },
              { rotulo: 'Cliques', alinhar: 'right', largura: 80 },
              { rotulo: 'CPC', alinhar: 'right', largura: 90 },
              { rotulo: 'Conv.', alinhar: 'right', largura: 70 },
              { rotulo: 'Custo/conv.', alinhar: 'right', largura: 110 },
            ]}
            linhas={campanhas.slice(0, 5).map((c) => [
              <strong key="c" title={c.campanha}>{c.campanha}</strong>,
              c.tipo,
              reais(c.investimento),
              numero(c.cliques),
              reaisCentavos(c.cpc),
              numero(c.leads_plataforma),
              reaisCentavos(c.cpl),
            ])}
          />
        )}
      </div>
      <div>
        <Titulo sub="Palavras-chave das campanhas de pesquisa, das que mais converteram às que mais clicaram">Palavras-chave</Titulo>
        {palavras.length === 0 ? (
          <SemDados>Sem palavras-chave com clique no período.</SemDados>
        ) : (
          <Tabela
            tamanho={14}
            colunas={[
              { rotulo: 'Palavra' },
              { rotulo: 'Empreendimento', largura: 270 },
              { rotulo: 'Investimento', alinhar: 'right', largura: 120 },
              { rotulo: 'Cliques', alinhar: 'right', largura: 80 },
              { rotulo: 'Conv.', alinhar: 'right', largura: 70 },
              { rotulo: 'Custo/conv.', alinhar: 'right', largura: 110 },
            ]}
            linhas={palavras.slice(0, 4).map((p) => [
              <strong key="p">{p.palavra}</strong>,
              empreendimentoCurto(p.empreendimento),
              reais(p.investimento),
              numero(p.cliques),
              numero(p.conversoes),
              reaisCentavos(p.custo_por_conversao),
            ])}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 7. Criativos: tema e formato
// ---------------------------------------------------------------------------

function ListaCriativos({ titulo, itens, exemplo }: { titulo: string; itens: GrupoCriativo[]; exemplo?: boolean }) {
  const max = Math.max(1, ...itens.map((i) => i.leads_cv));
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <Titulo>{titulo}</Titulo>
      {itens.length === 0 ? (
        <SemDados>Sem anúncios com investimento ou lead no período.</SemDados>
      ) : (
        itens.map((i) => (
          <div key={i.nome} style={{ padding: '6px 0', borderBottom: `1px solid ${COR.linha}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
              <span style={{ fontSize: 15.5, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{i.nome}</span>
              <span style={{ fontSize: 14, whiteSpace: 'nowrap' }}>
                <strong>{numero(i.leads_cv)}</strong> leads · CPL <strong>{i.cpl ? reaisCentavos(i.cpl) : '—'}</strong> · {numero(i.sql)} SQL
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
              <Barra valor={i.leads_cv} maximo={max} />
              <span style={{ fontSize: 12, color: COR.mudo, whiteSpace: 'nowrap' }}>
                {i.criativos ?? i.anuncios} criativo(s){i.criativos != null && i.anuncios > i.criativos ? ` em ${i.anuncios} anúncios` : ''} · {reais(i.investimento)}
              </span>
            </div>
            {exemplo && i.exemplo && i.exemplo.leads_cv > 0 && (
              <p style={{ fontSize: 12, color: COR.mudo, margin: '3px 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                Mais leads: {i.exemplo.anuncio} ({i.exemplo.leads_cv})
              </p>
            )}
          </div>
        ))
      )}
    </div>
  );
}

export function SlideCriativos({ d }: { d: Apresentacao }) {
  const c = d.criativos;
  const melhores = c.melhores ?? [];
  // Grupos com CPL de mais do dobro da mediana dos criativos não valem o espaço do slide (continuam nos totais do Resumo)
  const caro = (g: GrupoCriativo) => !!c.cpl_mediana && !!g.cpl && g.cpl > c.cpl_mediana * 2;
  const semNome = (g: GrupoCriativo) => /^(Outros|Tema não|Formato não)/.test(g.nome);   // "não informado" não diz nada: não entra
  const temas = c.por_tema.filter((t) => t.leads_cv > 0 && !caro(t) && !semNome(t));
  const formatos = c.por_formato.filter((f) => f.leads_cv > 0 && !caro(f) && !semNome(f));
  const escondidos = c.por_tema.filter((t) => caro(t)).length;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1, minHeight: 0 }}>
      {c.criativos_total ? <p style={{ fontSize: 13.5, margin: 0, lineHeight: 1.4 }}>
        <strong>{numero(c.criativos_total)}</strong> criativos diferentes no período
        {c.anuncios_total && c.criativos_total && c.anuncios_total > c.criativos_total ? ` (rodando em ${numero(c.anuncios_total)} anúncios: a mesma peça copiada em outras campanhas conta uma vez)` : ''}.
        {c.cpl_mediana ? <> CPL mediano dos criativos: <strong>{reaisCentavos(c.cpl_mediana)}</strong>.</> : null}
      </p> : null}
      <div style={{ display: 'flex', gap: 30, flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <ListaCriativos titulo="Formato do criativo" itens={formatos.slice(0, 3)} />
          <div style={{ height: 14 }} />
          <ListaCriativos titulo="Assunto do criativo" itens={temas.slice(0, 4)} />
        </div>
        {melhores.length > 0 && (
        <div style={{ flex: 1.1, minWidth: 0 }}>
          <Titulo>O que mais funciona</Titulo>
          {(
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {melhores.slice(0, 6).map((m) => (
                <div key={m.chave} style={{ border: `1px solid ${COR.linha}`, borderRadius: 12, padding: 8, display: 'flex', gap: 10, minWidth: 0, overflow: 'hidden' }}>
                  <Capa ad={m} tamanho={84} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <p style={{ fontSize: 12, fontWeight: 800, margin: 0, color: COR.verde }}>{m.formato} · {m.tema}</p>
                    <p style={{ fontSize: 12.5, fontWeight: 700, margin: '1px 0 0', lineHeight: 1.2, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{m.anuncio}</p>
                    <p style={{ fontSize: 12, margin: '3px 0 0', lineHeight: 1.35 }}>
                      <strong>{num1(m.leads_cv)}</strong> leads · CPL <strong>{reais(m.cpl)}</strong> · {num1(m.sql)} SQL
                    </p>
                    <p style={{ fontSize: 11, margin: 0, color: COR.mudo }}>
                      {m.pracas.join(', ')}{(m.variacoes ?? 1) > 1 ? ` · ${m.variacoes} variações somadas` : m.copias > 1 ? ` · em ${m.copias} campanhas` : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        )}
      </div>
      {(c.ocultos?.criativos || escondidos > 0) ? (
        <p style={{ fontSize: 12, margin: 0, color: COR.mudo }}>
          Não aparecem {c.ocultos?.criativos ? `${c.ocultos.criativos} criativo(s) com CPL muito alto ou sem lead (${reais(c.ocultos.investimento)} investidos)` : ''}
          {c.ocultos?.criativos && escondidos > 0 ? ' e ' : ''}
          {escondidos > 0 ? `${escondidos} assunto(s) de CPL muito alto ou sem lead` : ''}; os totais do Resumo continuam incluindo tudo.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 8. Site
// ---------------------------------------------------------------------------

export function SlideSite({ d }: { d: Apresentacao }) {
  const s = d.site;
  if (!s.totais.sessoes) {
    return (
      <SemDados>
        Sem dados do Google Analytics neste período
        {s.dados_ate ? ` (última data baixada: ${dm(s.dados_ate)}/${s.dados_ate.slice(0, 4)})` : ''}. Atualize os dados e gere o slide de novo.
      </SemDados>
    );
  }
  const t = s.totais;
  return (
    <>
      <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
        <Tile rotulo="Sessões" valor={numero(t.sessoes)} variacao={t.variacao.sessoes} sub="vs mês anterior" />
        <Tile rotulo="Usuários" valor={numero(t.usuarios)} variacao={t.variacao.usuarios} />
        <Tile rotulo="Conversões do site" valor={numero(t.conversoes)} variacao={t.variacao.conversoes} sub={`${pct(t.taxa_conversao)} das sessões`} />
      </div>
      <div style={{ display: 'flex', gap: 30, minHeight: 0 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Titulo>Origem do tráfego (UTM / mídia)</Titulo>
          <Tabela
            tamanho={14}
            colunas={[{ rotulo: 'Origem / mídia' }, { rotulo: 'Sessões', alinhar: 'right', largura: 80 }, { rotulo: '%', alinhar: 'right', largura: 64 }, { rotulo: 'Conv.', alinhar: 'right', largura: 60 }]}
            linhas={s.origens.slice(0, 6).map((o) => [<strong key="o">{o.origem}</strong>, numero(o.sessoes), pct(o.pct), numero(o.conversoes)])}
          />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Titulo>Páginas que mais trazem gente</Titulo>
          <Tabela
            tamanho={14}
            colunas={[{ rotulo: 'Página de entrada' }, { rotulo: 'Sessões', alinhar: 'right', largura: 80 }, { rotulo: 'Conv.', alinhar: 'right', largura: 60 }, { rotulo: 'Taxa', alinhar: 'right', largura: 70 }]}
            linhas={s.paginas.slice(0, 6).map((p) => [<strong key="p" title={p.pagina}>{p.pagina || '/'}</strong>, numero(p.sessoes), numero(p.conversoes), pct(p.taxa_conversao)])}
          />
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// 9. Anúncios do Google
// ---------------------------------------------------------------------------

function destaqueGoogle(c: CriterioGoogle, a: AnuncioGoogle): { valor: string; detalhe: string } {
  if (c.metrica === 'custo_por_conversao') return { valor: reaisCentavos(a.custo_por_conversao), detalhe: 'por conversão' };
  if (c.metrica === 'ctr') return { valor: pct(a.ctr), detalhe: `${numero(a.cliques)} cliques em ${numero(a.impressoes)} impressões` };
  return { valor: a.conversoes.toLocaleString('pt-BR', { maximumFractionDigits: 1 }), detalhe: 'conversões' };
}

export function SlideAnunciosGoogle({ d }: { d: Apresentacao }) {
  const { criterios, total } = d.google.anuncios;
  if (!total) return <SemDados>A base de anúncios do Google ainda não foi baixada para este período.</SemDados>;
  return (
    <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0, paddingBottom: 4 }}>
      {criterios.map((c) => {
        const [topo, ...resto] = c.ranking;
        return (
          <div key={c.id} style={{ flex: 1, minWidth: 0, border: `1px solid ${COR.linha}`, borderRadius: 14, padding: '14px 18px', display: 'flex', flexDirection: 'column' }}>
            <p style={{ fontSize: 13, fontWeight: 800, color: COR.laranja, letterSpacing: 0.6, textTransform: 'uppercase', margin: '0 0 10px' }}>{c.titulo}</p>
            {!topo ? (
              <p style={{ fontSize: 14.5, color: COR.mudo, margin: 'auto 0' }}>{c.motivo_vazio}</p>
            ) : (
              <>
                <p style={{ fontSize: 34, fontWeight: 800, color: COR.verde, margin: 0, lineHeight: 1 }}>{destaqueGoogle(c, topo).valor}</p>
                <p style={{ fontSize: 13, color: COR.mudo, margin: '3px 0 10px' }}>{destaqueGoogle(c, topo).detalhe}</p>
                <p style={{ fontSize: 17, fontWeight: 700, margin: 0, lineHeight: 1.25, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{topo.anuncio}</p>
                <p style={{ fontSize: 13, color: COR.mudo, margin: '4px 0 8px' }}>
                  {topo.tipo} · {topo.campanha}
                  {topo.forca ? ` · força ${topo.forca.toLowerCase()}` : ''}
                </p>
                <p style={{ fontSize: 13.5, margin: 0, lineHeight: 1.5 }}>
                  {reais(topo.investimento)} investidos · {numero(topo.cliques)} cliques
                  <br />
                  {topo.conversoes.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} conv. · custo/conv. {reaisCentavos(topo.custo_por_conversao)}
                </p>
                {resto.length > 0 && (
                  <div style={{ marginTop: 'auto', paddingTop: 8, fontSize: 12.5, color: COR.mudo, lineHeight: 1.5 }}>
                    {resto.map((a, i) => (
                      <div key={a.anuncio + i} style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {i + 2}º {a.anuncio}
                        </span>
                        <strong style={{ color: COR.texto, whiteSpace: 'nowrap' }}>{destaqueGoogle(c, a).valor}</strong>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 10. Google: como as conversões acontecem
// ---------------------------------------------------------------------------

export function SlideDetalhesGoogle({ d }: { d: Apresentacao }) {
  const { acoes, aparelhos, participacao } = d.google.detalhes;
  const max = Math.max(1, ...acoes.map((a) => a.todas));
  if (!acoes.length && !aparelhos.length && !participacao.length) {
    return <SemDados>A base de detalhes do Google ainda não foi baixada para este período.</SemDados>;
  }
  return (
    <div style={{ display: 'flex', gap: 30, flex: 1, minHeight: 0 }}>
      <div style={{ flex: 1.1, minWidth: 0 }}>
        <Titulo sub="Todas as conversões registradas na conta do Google">Quais ações convertem</Titulo>
        {acoes.map((a) => (
          <div key={a.acao} style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14.5, marginBottom: 4, gap: 10 }}>
              <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.acao}</strong>
              <span style={{ whiteSpace: 'nowrap' }}>
                <strong>{numero(a.todas)}</strong> · {pct(a.pct)}
              </span>
            </div>
            <Barra valor={a.todas} maximo={max} />
          </div>
        ))}
        <div style={{ marginTop: 16 }}>
          <Titulo>Aparelho</Titulo>
          <Tabela
            tamanho={14}
            colunas={[{ rotulo: 'Aparelho' }, { rotulo: '% cliques', alinhar: 'right', largura: 80 }, { rotulo: 'Conv.', alinhar: 'right', largura: 60 }, { rotulo: 'Custo/conv.', alinhar: 'right', largura: 100 }]}
            linhas={aparelhos.slice(0, 3).map((a) => [<strong key="a">{a.dispositivo}</strong>, pct(a.pct_cliques), numero(a.conversoes), reaisCentavos(a.custo_por_conversao)])}
          />
        </div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Titulo sub="Das buscas em que o anúncio podia aparecer, quanto ele apareceu e por que perdeu o resto">Participação de impressões</Titulo>
        <Tabela
          tamanho={13.5}
          colunas={[{ rotulo: 'Campanha' }, { rotulo: 'Apareceu', alinhar: 'right', largura: 78 }, { rotulo: 'Perdeu: verba', alinhar: 'right', largura: 92 }, { rotulo: 'Perdeu: ranking', alinhar: 'right', largura: 100 }]}
          linhas={participacao.map((c) => [<strong key="c" title={c.campanha}>{c.campanha}</strong>, pct(c.participacao), pct(c.perdida_orcamento), pct(c.perdida_ranking)])}
        />
        <p style={{ fontSize: 12.5, color: COR.mudo, margin: '10px 0 0', lineHeight: 1.45 }}>
          “Perdeu: verba” = o orçamento acabou. “Perdeu: ranking” = o anúncio perdeu o leilão (lance ou qualidade). Média ponderada por impressões.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 12 e 13. Cenário: por que o CPL mudou, eleição e concorrência
// ---------------------------------------------------------------------------

const dmCurto = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

function GraficoLinha({
  titulo,
  pontos,
  referencia,
  marcadores,
  formato,
  largura = 560,
  altura = 215,
}: {
  titulo: string;
  pontos: { x: string; y: number | null }[];
  referencia?: { x: string; y: number | null }[];
  marcadores: { x: string; rotulo: string }[];
  formato: (n: number) => string;
  largura?: number;
  altura?: number;
}) {
  const validos = pontos.filter((p) => p.y !== null) as { x: string; y: number }[];
  if (validos.length < 2) return <SemDados>Sem série suficiente.</SemDados>;
  const pad = { e: 52, d: 12, t: 22, b: 30 };
  const ys = [...validos.map((p) => p.y), ...((referencia ?? []).filter((p) => p.y !== null).map((p) => p.y as number))];
  const max = Math.max(...ys) * 1.1;
  const min = 0;
  const t0 = new Date(validos[0].x).getTime();
  const t1 = new Date(validos[validos.length - 1].x).getTime() + 6 * 86400000;
  const X = (iso: string) => pad.e + ((new Date(iso).getTime() - t0) / (t1 - t0)) * (largura - pad.e - pad.d);
  const Y = (v: number) => pad.t + (1 - (v - min) / (max - min)) * (altura - pad.t - pad.b);
  const linha = (lista: { x: string; y: number }[]) => lista.map((p, i) => `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(' ');
  // a referência de 2025 é deslocada 52 semanas para cair sobre as mesmas semanas do calendário
  const ref = (referencia ?? [])
    .filter((p) => p.y !== null)
    .map((p) => ({ x: new Date(new Date(p.x).getTime() + 364 * 86400000).toISOString().slice(0, 10), y: p.y as number }))
    .filter((p) => new Date(p.x).getTime() >= t0 && new Date(p.x).getTime() <= t1);
  const ticks = [0, 0.5, 1].map((f) => max * f);
  return (
    <div>
      <p style={{ fontSize: 14, fontWeight: 700, color: COR.escuro, margin: '0 0 2px' }}>{titulo}</p>
      <svg width={largura} height={altura} style={{ display: 'block' }}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={pad.e} x2={largura - pad.d} y1={Y(v)} y2={Y(v)} stroke={COR.linha} />
            <text x={pad.e - 6} y={Y(v) + 4} fontSize={11} textAnchor="end" fill={COR.mudo}>
              {formato(v)}
            </text>
          </g>
        ))}
        {marcadores
          .filter((m) => new Date(m.x).getTime() >= t0 && new Date(m.x).getTime() <= t1)
          .map((m) => (
            <g key={m.x}>
              <line x1={X(m.x)} x2={X(m.x)} y1={pad.t - 4} y2={altura - pad.b} stroke={COR.laranja} strokeDasharray="4 3" />
              <text x={X(m.x) + 3} y={pad.t + 6} fontSize={10.5} fill="#b45f00" fontWeight={600}>
                {m.rotulo}
              </text>
            </g>
          ))}
        {ref.length > 1 && <path d={linha(ref)} fill="none" stroke="#9aa79d" strokeWidth={2} strokeDasharray="5 4" />}
        <path d={linha(validos)} fill="none" stroke={COR.verde} strokeWidth={3} />
        {validos.map((p) => (
          <circle key={p.x} cx={X(p.x)} cy={Y(p.y)} r={3.2} fill={COR.verde} />
        ))}
        {[validos[0], validos[Math.floor(validos.length / 2)], validos[validos.length - 1]].map((p) => (
          <text key={p.x} x={X(p.x)} y={altura - 10} fontSize={11} textAnchor="middle" fill={COR.mudo}>
            {dmCurto(p.x)}
          </text>
        ))}
        <text x={X(validos[validos.length - 1].x)} y={Y(validos[validos.length - 1].y) - 8} fontSize={12} textAnchor="end" fontWeight={700} fill={COR.escuro}>
          {formato(validos[validos.length - 1].y)}
        </text>
      </svg>
    </div>
  );
}

function BarraAtribuicao({ rotulo, a }: { rotulo: string; a: NonNullable<BlocoCenario['atribuicao']> }) {
  if (a.sentido !== 'alta') return null;
  const partes = [
    { nome: 'Preço do leilão (CPM)', v: Math.max(a.preco ?? 0, 0), cor: COR.azul },
    { nome: 'Clique (CTR)', v: Math.max(a.clique ?? 0, 0), cor: '#d9822b' },
    { nome: 'Conversão do clique em lead', v: Math.max(a.conversao ?? 0, 0), cor: COR.verde },
  ];
  const soma = partes.reduce((s, p) => s + p.v, 0) || 1;
  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ fontSize: 13.5, fontWeight: 700, margin: '0 0 4px' }}>{rotulo}</p>
      <div style={{ display: 'flex', height: 26, borderRadius: 6, overflow: 'hidden' }}>
        {partes.map((p) => (
          <div key={p.nome} style={{ width: `${(p.v / soma) * 100}%`, background: p.cor, color: '#fff', fontSize: 12.5, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {p.v >= 8 ? `${p.v}%` : ''}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cenário de uma praça
// ---------------------------------------------------------------------------

const ROTULO_TIPO: Record<string, string> = {
  'Loteadora / empreendimento': 'Loteadora',
  'Corretor / imobiliária': 'Corretor/imob.',
  Outro: 'Outro',
};

function TileCompacto({
  rotulo,
  valor,
  variacao,
  melhor = 'neutro',
  sub,
  destaque,
}: {
  rotulo: string;
  valor: string;
  variacao?: number | null;
  melhor?: Melhor;
  sub?: string;
  destaque?: boolean;
}) {
  return (
    <div style={{ flex: 1, minWidth: 0, borderRadius: 12, padding: '10px 13px', background: destaque ? COR.escuro : COR.claro, color: destaque ? '#fff' : COR.texto }}>
      <p style={{ fontSize: 12, fontWeight: 700, margin: 0, color: destaque ? '#d6ecd2' : COR.mudo }}>{rotulo}</p>
      <p style={{ fontSize: 25, fontWeight: 800, margin: '2px 0 3px', lineHeight: 1.1, whiteSpace: 'nowrap' }}>{valor}</p>
      <p style={{ fontSize: 11.5, margin: 0, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', color: destaque ? '#d6ecd2' : COR.mudo }}>
        {variacao !== undefined && variacao !== null && (
          <span style={{ background: '#fff', borderRadius: 5, padding: '0 5px' }}>
            <Var valor={variacao} melhor={melhor} tamanho={11.5} />
          </span>
        )}
        {sub}
      </p>
    </div>
  );
}

export function SlideCenarioPraca({ p }: { p: CenarioPraca }) {
  const m = p.meta;
  const g = p.google;
  const c = p.concorrencia;
  const temMeta = Boolean(m.agora.cpl && m.antes.cpl);
  const intensidade = c ? (c.maior_busca >= 100 ? 'alta' : c.maior_busca >= 30 ? 'média' : 'baixa') : null;
  const ritmo = (b: typeof m) => (b.dias_antes && b.antes.investimento ? `antes ${reais((b.antes.investimento / b.dias_antes) * 7)}/sem.` : 'sem gasto antes');
  return (
    <div style={{ display: 'flex', gap: 24, flex: 1, minHeight: 0 }}>
      <div style={{ flex: 1.3, minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <TileCompacto destaque rotulo="Gasto no Meta (4 sem.)" valor={reais(m.agora.investimento)} variacao={m.variacao.investimento} sub={ritmo(m)} />
          <TileCompacto destaque rotulo="Gasto no Google (4 sem.)" valor={reais(g.agora.investimento)} variacao={g.variacao.investimento} sub={ritmo(g)} />
          <TileCompacto rotulo="CPL no Meta" valor={m.agora.cpl ? reaisCentavos(m.agora.cpl) : '—'} variacao={m.variacao.cpl} melhor="descer" sub={m.antes.cpl ? `antes ${reaisCentavos(m.antes.cpl)}` : undefined} />
          <TileCompacto rotulo="CPL no Google" valor={g.agora.cpl ? reaisCentavos(g.agora.cpl) : '—'} variacao={g.variacao.cpl} melhor="descer" sub={g.antes.cpl ? `antes ${reaisCentavos(g.antes.cpl)}` : g.agora.cpl ? 'sem base antes' : undefined} />
        </div>
        {temMeta ? (
          <>
            <p style={{ fontSize: 12.5, color: COR.mudo, margin: '8px 0 6px' }}>
              Meta: CPM <strong style={{ color: COR.texto }}>{reaisCentavos(m.agora.cpm)}</strong> <Var valor={m.variacao.cpm} melhor="descer" tamanho={12} /> · clique que vira lead{' '}
              <strong style={{ color: COR.texto }}>{pct(m.agora.conversao)}</strong> <Var valor={m.variacao.conversao} tamanho={12} /> · CTR <strong style={{ color: COR.texto }}>{pct(m.agora.ctr)}</strong>{' '}
              <Var valor={m.variacao.ctr} tamanho={12} />
            </p>
            {m.atribuicao && m.atribuicao.sentido === 'alta' && <BarraAtribuicao rotulo="De onde veio a alta do CPL no Meta: preço do leilão · clique · conversão" a={m.atribuicao} />}
            <GraficoLinha
              titulo={`CPM semanal no Meta em ${p.praca} (R$ por mil exibições)`}
              pontos={p.serie.meta.map((x) => ({ x: x.semana, y: x.cpm }))}
              marcadores={[
                { x: '2026-08-16', rotulo: 'Campanha eleitoral' },
                { x: '2026-10-04', rotulo: '1º turno' },
              ]}
              formato={(n) => `R$ ${n.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}`}
              largura={620}
              altura={190}
            />
          </>
        ) : (
          <div style={{ marginTop: 10 }}>
            <SemDados>Sem investimento no Meta em {p.praca} nas duas janelas comparadas.</SemDados>
          </div>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Titulo sub={c ? `Anúncios ativos na Meta que citam ${p.praca} · intensidade ${intensidade}` : 'Sem coleta para esta praça'}>Concorrência</Titulo>
        {c ? (
          <>
            <p style={{ fontSize: 14, margin: '0 0 6px' }}>
              <strong>{numero(c.maior_busca)}</strong> anúncios · <strong>{c.novos_na_campanha}</strong> anunciantes novos desde 16/08 · {c.loteadoras} loteadora(s)
            </p>
            {c.lista.slice(0, 5).map((a) => (
              <div key={a.nome} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5, padding: '3px 0', borderBottom: `1px solid ${COR.linha}` }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <strong>{a.nome}</strong> <span style={{ color: COR.mudo }}>· {ROTULO_TIPO[a.tipo] ?? a.tipo}</span>
                </span>
                <span style={{ color: COR.mudo, whiteSpace: 'nowrap' }}>
                  {a.anuncios} · desde {a.desde.slice(0, 5)}
                </span>
              </div>
            ))}
          </>
        ) : null}
        <div style={{ marginTop: 10 }}>
          <Titulo>Leitura da praça</Titulo>
          {p.leitura
            .filter((l) => !l.texto.startsWith('Concorrência') || !c)
            .slice(0, 5)
            .map((l, i) => (
              <p
                key={i}
                style={{
                  fontSize: 12,
                  lineHeight: 1.38,
                  margin: '0 0 5px',
                  paddingLeft: 9,
                  borderLeft: `3px solid ${l.tipo === 'atencao' ? COR.ruim : l.tipo === 'limite' ? COR.mudo : l.tipo === 'indicio' ? COR.laranja : COR.verde}`,
                }}
              >
                {l.texto}
              </p>
            ))}
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Quadro completo de anúncios de uma praça (Meta e Google)
// ---------------------------------------------------------------------------

export function SlideQuadroAnuncios({ d, praca }: { d: Apresentacao; praca: string }) {
  const p = d.anuncios_por_praca?.[praca];
  if (!p) return <SemDados>Sem anúncios para esta praça no período.</SemDados>;
  const meta = (p.quadro ?? []).slice(0, 7);
  const google = (p.google ?? []).slice(0, 4);
  const nome = (a: AnuncioRanking) => (a.anuncio.length > 38 ? `${a.anuncio.slice(0, 37)}…` : a.anuncio);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 800, color: COR.escuro }}>Meta · anúncios com mais leads <span style={{ fontWeight: 400, fontSize: 12.5, color: COR.mudo }}>· lead de clique no WhatsApp é repartido entre os anúncios com o mesmo título, pelas conversas de cada um (SQL estimado)</span></p>
        <Tabela
          tamanho={13.5}
          colunas={[
            { rotulo: 'Anúncio' },
            { rotulo: 'Investido', alinhar: 'right', largura: 88 },
            { rotulo: 'Leads', alinhar: 'right', largura: 60 },
            { rotulo: 'CPL', alinhar: 'right', largura: 84 },
            { rotulo: 'SQL', alinhar: 'right', largura: 54 },
            { rotulo: '% SQL', alinhar: 'right', largura: 66 },
            { rotulo: 'Custo/SQL', alinhar: 'right', largura: 90 },
            { rotulo: 'Vendas', alinhar: 'right', largura: 66 },
          ]}
          linhas={meta.map((a) => [
            <span key="n">
              <strong>{nome(a)}</strong> <span style={{ color: COR.mudo }}>· {empreendimentoCurto(a.empreendimento).split(' (')[0]}</span>
            </span>,
            a.investimento ? reais(a.investimento) : '—',
            num1(a.leads_efetivos ?? a.leads_cv),
            (a.cpl_efetivo ?? a.cpl_real) ? reaisCentavos(a.cpl_efetivo ?? a.cpl_real) : '—',
            num1(a.sql_efetivo ?? a.sql),
            (a.leads_total ?? a.leads_cv) ? pct(a.taxa_sql_efetiva ?? a.taxa_sql) : '—',
            a.custo_por_sql ? reais(a.custo_por_sql) : '—',
            numero(a.vendas),
          ])}
        />
      </div>
      <div>
        <p style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 800, color: COR.escuro }}>Google · campanhas da praça</p>
        {google.length ? (
          <Tabela
            tamanho={13.5}
            colunas={[
              { rotulo: 'Campanha' },
              { rotulo: 'Tipo', largura: 130 },
              { rotulo: 'Investido', alinhar: 'right', largura: 92 },
              { rotulo: 'Cliques', alinhar: 'right', largura: 76 },
              { rotulo: 'CPC', alinhar: 'right', largura: 76 },
              { rotulo: 'Conv.', alinhar: 'right', largura: 62 },
              { rotulo: 'Custo/conv.', alinhar: 'right', largura: 104 },
            ]}
            linhas={google.map((c) => [
              <strong key="c">{c.campanha}</strong>,
              c.tipo,
              reais(c.investimento),
              numero(c.cliques),
              c.cpc ? reaisCentavos(c.cpc) : '—',
              numero(c.leads_plataforma),
              c.cpl ? reaisCentavos(c.cpl) : '—',
            ])}
          />
        ) : (
          <p style={{ fontSize: 14, color: COR.mudo, margin: 0 }}>Nenhuma campanha do Google com gasto nesta praça no período.</p>
        )}
      </div>
      <p style={{ fontSize: 12.5, color: COR.mudo, margin: '2px 0 0' }}>
        Leads e SQL do Meta são os do CV, ligados ao anúncio pela UTM{p.leads_da_plataforma ? ' (aqui, sem lead do CV ligado ao anúncio, valem os leads que a própria Meta registra)' : ''}. Conversão do Google é a ação principal da conta, não o lead do CV.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Concorrência de uma praça
// ---------------------------------------------------------------------------

function MiniTile({ rotulo, valor, sub, ruim }: { rotulo: string; valor: string; sub?: React.ReactNode; ruim?: boolean }) {
  return (
    <div style={{ background: ruim ? COR.laranjaClaro : COR.claro, borderRadius: 12, padding: '12px 16px', minWidth: 0 }}>
      <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: COR.mudo }}>{rotulo}</p>
      <p style={{ margin: '2px 0', fontSize: 30, fontWeight: 800, color: COR.texto, lineHeight: 1.1 }}>{valor}</p>
      <p style={{ margin: 0, fontSize: 12.5, color: COR.mudo }}>{sub}</p>
    </div>
  );
}

const dmIso = (iso: string | null | undefined) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : '—');

export function SlideConcorrencia({ d, praca }: { d: Apresentacao; praca: string }) {
  const c = d.concorrencia?.pracas?.[praca];
  if (!c) return <SemDados>Sem dados de concorrência para esta praça.</SemDados>;
  const g = c.google.agora;
  const gAntes = c.google.antes;
  const a = c.anunciantes;
  const todos = a?.lista ?? [];
  const grandes = todos.filter((x) => x.grande);
  const lista = [...todos.slice(0, 8), ...grandes.filter((x) => !todos.slice(0, 8).includes(x))].slice(0, 10);
  const topo = (a?.lista ?? []).slice(0, 3);
  const leituraGoogle = g
    ? g.perdida_ranking > g.perdida_orcamento * 1.5
      ? `No Google perdemos ${g.perdida_ranking}% das buscas por ranking e só ${g.perdida_orcamento}% por verba: o que escapa é leilão (concorrência e qualidade do anúncio), não falta de orçamento.`
      : `No Google perdemos ${g.perdida_orcamento}% das buscas por verba e ${g.perdida_ranking}% por ranking: aumentar o orçamento recupera parte do que escapa.`
    : 'Sem campanha de pesquisa do Google com dados nesta praça no período.';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 18 }}>
        <div style={{ flex: 0.95, display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 800, color: COR.escuro }}>Pressão no leilão (a nossa conta)</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <MiniTile rotulo="Google: aparecemos em" valor={g ? `${g.apareceu}%` : '—'} sub={gAntes ? `antes ${gAntes.apareceu}% das buscas` : 'das buscas possíveis'} />
            <MiniTile rotulo="Google: perdido por ranking" valor={g ? `${g.perdida_ranking}%` : '—'} sub={g ? `por verba ${g.perdida_orcamento}%` : ''} ruim />
            <MiniTile
              rotulo="Google: CPC"
              valor={c.google.cpc ? reaisCentavos(c.google.cpc.cpc) : '—'}
              sub={c.google.var_cpc != null ? <Var valor={c.google.var_cpc} melhor="descer" tamanho={12.5} /> : 'sem período anterior'}
            />
            <MiniTile
              rotulo="Meta: CPM"
              valor={c.meta.cpm ? reaisCentavos(c.meta.cpm) : '—'}
              sub={c.meta.var_cpm != null ? <Var valor={c.meta.var_cpm} melhor="descer" tamanho={12.5} /> : 'sem período anterior'}
            />
          </div>
          <p style={{ margin: 0, fontSize: 13.5, color: COR.texto, lineHeight: 1.35 }}>{leituraGoogle}</p>
        </div>
        <div style={{ flex: 1.15, minWidth: 0 }}>
          <p style={{ margin: '0 0 2px', fontSize: 15, fontWeight: 800, color: COR.escuro }}>Quem anuncia na praça (Meta)</p>
          {a && a.anunciantes ? (
            <>
              <p style={{ margin: '0 0 4px', fontSize: 13, color: COR.mudo }}>
                {a.anunciantes} anunciantes do setor · {a.loteadoras} loteadoras/construtoras · {a.corretores} corretores/imobiliárias · {a.novos} com anúncio iniciado desde {dmIso(d.concorrencia?.inicio_campanha)}
              </p>
              <Tabela
                tamanho={12.5}
                colunas={[{ rotulo: 'Anunciante' }, { rotulo: 'Tipo', largura: 88 }, { rotulo: 'Anún.', alinhar: 'right', largura: 52 }, { rotulo: 'Desde', alinhar: 'right', largura: 62 }]}
                linhas={lista.map((x: Anunciante) => [
                  <span key="n">
                    <strong>{x.nome}</strong>
                    {x.grande ? <span style={{ color: COR.ruim, fontWeight: 700 }}> · incorporadora conhecida</span> : null}
                  </span>,
                  x.tipo === 'loteadora' ? 'Loteadora' : 'Corretor',
                  numero(x.anuncios),
                  dmIso(x.desde),
                ])}
              />
            </>
          ) : (
            <p style={{ fontSize: 14, color: COR.mudo, margin: 0 }}>Nenhum anunciante do setor encontrado na Biblioteca de Anúncios para esta praça ({a?.descartados ?? 0} resultados de outros ramos descartados).</p>
          )}
        </div>
      </div>
      {topo.length > 0 && (
        <div style={{ background: COR.laranjaClaro, borderRadius: 12, padding: '10px 16px' }}>
          <p style={{ margin: 0, fontSize: 13.5, color: COR.texto, lineHeight: 1.4 }}>
            <strong>Quem mais aparece nos anúncios da praça:</strong>{' '}
            {topo.map((x, i) => `${i + 1}º ${x.nome} (${x.anuncios} anúncio${x.anuncios === 1 ? '' : 's'}, em ${x.buscas} busca${x.buscas === 1 ? '' : 's'})`).join(' · ')}.
            {' '}É presença nos anúncios, não medida de leilão.
          </p>
        </div>
      )}
      <p style={{ fontSize: 12, color: COR.mudo, margin: 0 }}>
        Fonte: Biblioteca de Anúncios da Meta, {d.concorrencia?.consultas ?? 0} buscas por cidade, termos gerais e nomes de concorrentes{d.concorrencia?.coletado_em ? `, coletadas em ${dmIso(d.concorrencia.coletado_em)}` : ''}; cada busca mostra os ~20 anúncios de maior alcance, então é uma amostra, não o total. Não traz segmentação nem valores. Auction Insights do Google exige acesso aprovado pelo Google.
      </p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Orgânicos e indicação: o que há por trás
// ---------------------------------------------------------------------------

export function SlideOrganicos({ d }: { d: Apresentacao }) {
  const o = d.organicos_origem;
  if (!o || !(o.total || o.reclassificados?.total)) return <SemDados>Nenhum lead orgânico ou de indicação no período.</SemDados>;
  const rc = o.reclassificados;
  return (
    <div style={{ display: 'flex', gap: 22 }}>
      <div style={{ flex: 1.55, minWidth: 0 }}>
        <Tabela
          tamanho={14}
          colunas={[{ rotulo: 'De onde veio de verdade' }, { rotulo: 'Leads', alinhar: 'right', largura: 64 }, { rotulo: '%', alinhar: 'right', largura: 64 }, { rotulo: 'SQL', alinhar: 'right', largura: 54 }, { rotulo: '% SQL', alinhar: 'right', largura: 72 }]}
          linhas={o.categorias.map((c) => [
            <span key="c">
              <strong>{c.categoria}</strong>
              {c.detalhes.length > 0 && c.categoria !== 'WhatsApp direto, sem nenhum rastro de anúncio' ? (
                <span style={{ display: 'block', fontSize: 12, color: COR.mudo, whiteSpace: 'normal', lineHeight: 1.25 }}>{c.detalhes.map((x) => `${x.nome} (${x.leads})`).join(' · ')}</span>
              ) : null}
            </span>,
            numero(c.leads),
            pct(c.pct),
            numero(c.sql),
            c.leads ? pct(c.pct_sql) : '—',
          ])}
        />
      </div>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {rc && rc.total > 0 && (
          <div style={{ background: COR.laranjaClaro, borderRadius: 14, padding: '14px 18px' }}>
            <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: COR.mudo, textTransform: 'uppercase' }}>Reclassificados como mídia paga</p>
            <p style={{ margin: '4px 0 6px', fontSize: 30, fontWeight: 800, color: COR.texto, lineHeight: 1.1 }}>{rc.total} leads</p>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.4, color: COR.texto }}>
              {rc.meta} de Meta e {rc.google} de Google, {rc.sql} já em SQL. Tinham rastro de anúncio no CV (UTM, clique pago, origem de cadastro ou histórico de mídias) e foram contados como mídia paga nesta apresentação. O BI os conta como orgânicos porque usa a <strong>última</strong> conversão (WhatsApp)
              {o.cadastrados_antes_do_periodo ? <>; {o.cadastrados_antes_do_periodo} dos orgânicos já estavam cadastrados antes do período</> : null}.
            </p>
            {rc.anuncios.length > 0 && (
              <p style={{ margin: '8px 0 0', fontSize: 12.5, lineHeight: 1.3, color: COR.mudo }}>{rc.anuncios.map((x) => `${x.nome} (${x.leads})`).join(' · ')}</p>
            )}
          </div>
        )}
        {o.indique_e_ganhe.length > 0 && (
          <div style={{ background: COR.claro, borderRadius: 14, padding: '14px 18px' }}>
            <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: COR.mudo, textTransform: 'uppercase' }}>Indicação = Indique e Ganhe</p>
            {o.indique_e_ganhe.map((x) => (
              <p key={x.campanha} style={{ margin: '6px 0 0', fontSize: 14.5, lineHeight: 1.35, color: COR.texto }}>
                <strong>{x.leads}</strong> lead{x.leads === 1 ? '' : 's'} na campanha <strong>{x.campanha}</strong> (base do BeeViral).
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Custo por origem: pagas com custo, orgânicas abertas
// ---------------------------------------------------------------------------

export function SlideCustoOrigem({ d }: { d: Apresentacao }) {
  const f = d.resumo.fontes;
  const org = d.organicos_origem;
  const pagas = ([['meta', 'Meta Ads'], ['google', 'Google Ads']] as const).filter(([k]) => f[k].leads > 0 || f[k].investimento > 0);
  const investTotal = f.meta.investimento + f.google.investimento;
  const leadsTotal = d.resumo.total.leads;
  const sqlTotal = d.resumo.total.sql;
  const celulaPaga = (k: 'meta' | 'google', nome: string) => [
    <strong key="n">{nome}</strong>,
    numero(f[k].leads),
    reais(f[k].investimento),
    <strong key="c">{f[k].cpl ? reaisCentavos(f[k].cpl) : '—'}</strong>,
    numero(f[k].sql),
    pct(f[k].pct_sql),
    f[k].custo_sql ? reais(f[k].custo_sql) : '—',
  ];
  const organicas = (org?.categorias ?? []).map((c) => [
    <span key="n">{c.categoria}</span>,
    numero(c.leads),
    '—',
    '—',
    numero(c.sql),
    c.leads ? pct(c.pct_sql) : '—',
    '—',
  ]);
  const nOrg = (org?.categorias ?? []).reduce((t, c) => t + c.leads, 0);
  return (
    <div>
      <Tabela
        tamanho={14.5}
        colunas={[
          { rotulo: 'Origem' },
          { rotulo: 'Leads', alinhar: 'right', largura: 70 },
          { rotulo: 'Investimento', alinhar: 'right', largura: 130 },
          { rotulo: 'CPL', alinhar: 'right', largura: 100 },
          { rotulo: 'SQL', alinhar: 'right', largura: 64 },
          { rotulo: '% SQL', alinhar: 'right', largura: 80 },
          { rotulo: 'Custo/SQL', alinhar: 'right', largura: 110 },
        ]}
        linhas={[
          ...pagas.map(([k, nome]) => celulaPaga(k, nome)),
          [<em key="t" style={{ color: COR.mudo }}>Orgânicas e indicação (sem custo direto), abertas:</em>, <strong key="l">{numero(nOrg)}</strong>, '—', '—', <strong key="s">{numero(f.organico.sql + f.indicacao.sql)}</strong>, '', ''],
          ...organicas,
          [<strong key="n">Total</strong>, <strong key="l">{numero(leadsTotal)}</strong>, <strong key="i">{reais(investTotal)}</strong>, <strong key="c">{leadsTotal && investTotal ? reaisCentavos(investTotal / leadsTotal) : '—'}</strong>, <strong key="s">{numero(sqlTotal)}</strong>, <strong key="p">{pct(d.resumo.total.pct_sql)}</strong>, <strong key="cs">{sqlTotal && investTotal ? reais(investTotal / sqlTotal) : '—'}</strong>],
        ]}
      />
      <p style={{ margin: '10px 0 0', fontSize: 13, color: COR.mudo, lineHeight: 1.4 }}>
        Meta e Google já incluem os leads com rastro de anúncio que o BI conta como orgânicos, para o custo por lead não ficar inflado. O CPL do total divide o investimento por todos os leads, pagos e orgânicos.
      </p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Clique no WhatsApp (CTW) contra formulário da Meta
// ---------------------------------------------------------------------------

export function SlideCtwFormulario({ d }: { d: Apresentacao }) {
  const c = d.ctw_x_formulario;
  if (!c || !c.pracas.length) return <SemDados>Sem campanhas de clique no WhatsApp ou formulário com investimento neste período.</SemDados>;
  const linha = (rotulo: string, tipo: string, b: BlocoCanalMeta, forte = false) => {
    const f = forte ? 800 : 500;
    return [
      <span key="p" style={{ fontWeight: forte ? 800 : 700 }}>{rotulo}</span>,
      <span key="t" style={{ color: tipo === 'CTW' ? COR.verde : COR.laranja, fontWeight: 700 }}>{tipo}</span>,
      <span key="i" style={{ fontWeight: f }}>{reais(b.investimento)}</span>,
      <span key="l" style={{ fontWeight: f }}>{numero(b.leads)}</span>,
      <span key="m" style={{ color: COR.mudo, fontSize: 12.5 }}>{tipo === 'CTW' ? `${numero(b.conversas ?? 0)} conversas` : `${numero(b.formularios ?? 0)} formulários`}</span>,
      <strong key="c">{b.cpl ? reaisCentavos(b.cpl) : '—'}</strong>,
      <span key="s" style={{ fontWeight: f }}>{numero(b.sql)}</span>,
      <span key="ps" style={{ fontWeight: f }}>{b.leads ? pct(b.pct_sql) : '—'}</span>,
      <strong key="cs">{b.custo_sql ? reais(b.custo_sql) : '—'}</strong>,
      <span key="o" style={{ fontWeight: f }}>{numero(b.opps)}</span>,
      <span key="v" style={{ fontWeight: f }}>{numero(b.vendas)}</span>,
    ];
  };
  const t = c.total;
  const razao = t.ctw.custo_sql && t.formulario.custo_sql ? t.formulario.custo_sql / t.ctw.custo_sql : null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <Tabela
        tamanho={13.5}
        colunas={[
          { rotulo: 'Praça' }, { rotulo: 'Campanha', largura: 108 },
          { rotulo: 'Investimento', alinhar: 'right', largura: 104 }, { rotulo: 'Leads (CV)', alinhar: 'right', largura: 78 }, { rotulo: 'Meta registra', alinhar: 'right', largura: 112 },
          { rotulo: 'CPL', alinhar: 'right', largura: 86 }, { rotulo: 'SQL', alinhar: 'right', largura: 54 },
          { rotulo: '% SQL', alinhar: 'right', largura: 70 }, { rotulo: 'Custo/SQL', alinhar: 'right', largura: 96 },
          { rotulo: 'OPPS', alinhar: 'right', largura: 56 }, { rotulo: 'Vendas', alinhar: 'right', largura: 66 },
        ]}
        linhas={[
          ...c.pracas.flatMap((p) => [linha(p.praca, 'CTW', p.ctw), linha('', 'Formulário', p.formulario)]),
          linha('Total', 'CTW', t.ctw, true),
          linha('', 'Formulário', t.formulario, true),
        ]}
      />
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.45, color: COR.texto }}>
        <strong>Leitura:</strong> no total, o clique no WhatsApp custa {t.ctw.cpl ? reaisCentavos(t.ctw.cpl) : '—'} por lead e converte {t.ctw.leads ? pct(t.ctw.pct_sql) : '—'} em SQL; o formulário custa {t.formulario.cpl ? reaisCentavos(t.formulario.cpl) : '—'} e converte {t.formulario.leads ? pct(t.formulario.pct_sql) : '—'}.
        {razao ? ` O SQL pelo formulário custa ${razao.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}× o do clique no WhatsApp.` : ''}
      </p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Meta de leads por praça: meta do mês + o que faltou nos meses anteriores
// ---------------------------------------------------------------------------

const MESES_NOME = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const nomeMes = (iso?: string | null) => (iso ? MESES_NOME[Number(iso.slice(5, 7)) - 1] : '');
const curtoSemPraca = (produto: string) => empreendimentoCurto(produto).replace(/ \(.*/, '');

export function SlideMetas({ d }: { d: Apresentacao }) {
  const m: MetasLeads | null | undefined = d.metas_leads;
  if (!m || !m.pracas.length) return <SemDados>Sem meta de leads importada para este filtro.</SemDados>;
  const corPct = (p: number | null) => (p === null ? COR.mudo : p >= 100 ? COR.verde : p >= 70 ? COR.laranja : COR.ruim);
  type L = { meta_base: number; saldo_anterior: number; meta_efetiva: number; atingido: number | null; falta: number; pct: number | null; projecao: number | null; pct_projecao: number | null; cpl_pago?: number | null; investir_a_mais?: number | null };
  const linha = (rotulo: React.ReactNode, o: L, forte: boolean) => [
    <span key="r" style={{ fontWeight: forte ? 800 : 500 }}>{rotulo}</span>,
    numero(o.meta_base),
    o.saldo_anterior ? <span key="s" style={{ color: COR.ruim, fontWeight: 700 }}>+ {numero(o.saldo_anterior)}</span> : '—',
    <strong key="e">{numero(o.meta_efetiva)}</strong>,
    <strong key="a">{o.atingido === null ? '—' : numero(o.atingido)}</strong>,
    <strong key="p" style={{ color: corPct(o.pct) }}>{o.pct === null ? '—' : pct(o.pct)}</strong>,
    numero(o.falta),
    o.projecao === null ? '—' : <span key="pj">{numero(o.projecao)} <span style={{ color: corPct(o.pct_projecao), fontSize: 12 }}>({o.pct_projecao === null ? '—' : pct(o.pct_projecao)})</span></span>,
    o.cpl_pago ? reais(o.cpl_pago) : '—',
    o.investir_a_mais ? <strong key="ia" style={{ color: COR.ruim }}>{reais(o.investir_a_mais)}</strong> : '—',
  ];
  const nomeProduto = (p: { produto: string; sem_dados: boolean }) => `${empreendimentoCurto(p.produto)}${p.sem_dados ? ' (sem leads no sistema)' : ''}`;
  const linhas: React.ReactNode[][] = [];
  m.pracas.forEach((g) => {
    if (g.produtos.length === 1) {
      linhas.push(linha(nomeProduto(g.produtos[0]), { ...g.produtos[0], cpl_pago: g.produtos[0].cpl_usado }, true));
      return;
    }
    linhas.push(linha(g.praca, { ...g, cpl_pago: null }, true));
    g.produtos.forEach((p) => linhas.push(linha(<span key="n" style={{ color: COR.mudo }}>&nbsp;&nbsp;{nomeProduto(p)}</span>, { ...p, cpl_pago: p.cpl_usado }, false)));
  });
  const varias = m.pracas.length > 1 || m.pracas.some((g) => g.produtos.length > 1);
  const tot = m.total;
  if (varias) {
    linhas.push(linha('Total', { ...tot, pct: tot.meta_efetiva ? (tot.atingido / tot.meta_efetiva) * 100 : null, pct_projecao: tot.meta_efetiva ? (tot.projecao / tot.meta_efetiva) * 100 : null, cpl_pago: null, investir_a_mais: tot.investir_a_mais ?? null }, true));
  }

  // Nota só com o que aparece nas linhas: a meta de setembro da agência, Reserva dos Ramos e Itu entram apenas se estiverem no filtro
  const produtos = m.pracas.flatMap((g) => g.produtos);
  const ancora: Record<string, string> = { 'Central Parque II': '334', 'Reserva Central Parque II': '164', 'Jardim dos Ipês III': '151', 'Novo Horizonte': '50' };
  const partidas = produtos.map((p) => curtoSemPraca(p.produto)).filter((n) => ancora[n]);
  const temRamos = produtos.some((p) => p.produto.includes('Ramos'));
  const temItu = produtos.some((p) => p.produto.includes('Altavista'));
  const cplsVisiveis = produtos.filter((p) => p.cpl_usado && !p.sem_dados).map((p) => `${curtoSemPraca(p.produto)} ${reais(p.cpl_usado ?? 0)}${p.cpl_historico && p.cpl_pago ? ` (histórico ${reais(p.cpl_historico)} e do mês ${reais(p.cpl_pago)})` : ''}`).join('; ');
  const nota = [
    'Meta efetiva = meta do mês + o que faltou nos meses anteriores (a sobra não abate).',
    partidas.length ? `O saldo parte da meta de setembro que a agência calculou (${partidas.map((n) => `${n} ${ancora[n]}`).join(', ')}).` : '',
    temRamos ? 'Em Reserva dos Ramos, que a agência não atende, o saldo é calculado mês a mês desde junho.' : '',
    temItu ? 'Itu: a meta de "Terras de Itu II" é a do Altavista.' : '',
    `Atingido até ${m.ate.slice(8)}/${m.ate.slice(5, 7)} (${m.dias_decorridos} de ${m.dias_no_mes} dias, até onde o CV foi atualizado); projeção = ritmo do mês até agora.`,
    `Investir a mais = leads que faltam × CPL de referência: o CPL pago do mês, com peso de ${Math.round((m.peso_cpl_mes ?? 0) * 100)}% (dias decorridos ÷ dias do mês), e o histórico da planilha de metas, com o resto${cplsVisiveis ? `. ${cplsVisiveis}` : ''}. É quanto se investiria a mais, nesse CPL, para chegar na meta.`,
  ].filter(Boolean).join(' ');

  // Próximo mês: meta base + o que não fechar neste mês (projeção) e o investimento estimado para isso
  const proximos = m.pracas.filter((g) => !g.sem_dados && (g.prox_meta_efetiva ?? 0) > 0);
  const linhaProx = (rot: React.ReactNode, o: { prox_meta_base?: number; falta_fim_projetada?: number; prox_meta_efetiva?: number; prox_investimento?: number; investimento_ritmo_mes?: number }, forte: boolean) => {
    const vezes = o.investimento_ritmo_mes && o.prox_investimento ? o.prox_investimento / o.investimento_ritmo_mes : null;
    return [
      <span key="r" style={{ fontWeight: forte ? 800 : 600 }}>{rot}</span>,
      numero(o.prox_meta_base ?? 0),
      o.falta_fim_projetada ? <span key="f" style={{ color: COR.ruim, fontWeight: 700 }}>+ {numero(o.falta_fim_projetada)}</span> : '—',
      <strong key="e">{numero(o.prox_meta_efetiva ?? 0)}</strong>,
      o.investimento_ritmo_mes ? reais(o.investimento_ritmo_mes) : '—',
      o.prox_investimento ? <strong key="i" style={{ color: COR.ruim }}>{reais(o.prox_investimento)}</strong> : '—',
      vezes ? <span key="v">{vezes.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}×</span> : '—',
    ];
  };
  const linhasProx: React.ReactNode[][] = proximos.map((g) => linhaProx(g.produtos.length === 1 ? empreendimentoCurto(g.produtos[0].produto) : g.praca, g, false));
  if (proximos.length > 1) {
    // Total de novembro = as linhas que aparecem (o Itu tem meta em novembro mesmo sem meta em outubro, e o total do mês não o inclui)
    const soma = (k: 'prox_meta_base' | 'falta_fim_projetada' | 'prox_meta_efetiva' | 'prox_investimento' | 'investimento_ritmo_mes') => proximos.reduce((s, g) => s + (g[k] ?? 0), 0);
    linhasProx.push(linhaProx('Total', { prox_meta_base: soma('prox_meta_base'), falta_fim_projetada: soma('falta_fim_projetada'), prox_meta_efetiva: soma('prox_meta_efetiva'), prox_investimento: soma('prox_investimento'), investimento_ritmo_mes: soma('investimento_ritmo_mes') }, true));
  }
  const mesProx = nomeMes(m.prox_mes);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <Tabela
        tamanho={13.5}
        colunas={[
          { rotulo: 'Praça / empreendimento' },
          { rotulo: 'Meta do mês', alinhar: 'right', largura: 88 },
          { rotulo: 'Saldo anterior', alinhar: 'right', largura: 98 },
          { rotulo: 'Meta efetiva', alinhar: 'right', largura: 92 },
          { rotulo: 'Atingido', alinhar: 'right', largura: 80 },
          { rotulo: '% da meta', alinhar: 'right', largura: 84 },
          { rotulo: 'Falta', alinhar: 'right', largura: 58 },
          { rotulo: 'Projeção do mês', alinhar: 'right', largura: 124 },
          { rotulo: 'CPL de referência', alinhar: 'right', largura: 104 },
          { rotulo: 'Investir a mais', alinhar: 'right', largura: 112 },
        ]}
        linhas={linhas}
      />
      {linhasProx.length > 0 && (
        <>
          <p style={{ margin: '6px 0 0', fontSize: 15, fontWeight: 800, color: COR.escuro }}>
            {mesProx ? `${mesProx.charAt(0).toUpperCase()}${mesProx.slice(1)}` : 'Próximo mês'}: meta com o saldo que passa para frente
            <span style={{ fontWeight: 400, fontSize: 13, color: COR.mudo }}> · saldo = projeção do que não fecha este mês</span>
          </p>
          <Tabela
            tamanho={13.5}
            colunas={[
              { rotulo: 'Praça / empreendimento' },
              { rotulo: 'Meta do mês', alinhar: 'right', largura: 100 },
              { rotulo: '+ Saldo projetado', alinhar: 'right', largura: 130 },
              { rotulo: 'Meta efetiva', alinhar: 'right', largura: 104 },
              { rotulo: 'Investimento no ritmo atual', alinhar: 'right', largura: 190 },
              { rotulo: 'Investimento para a meta', alinhar: 'right', largura: 190 },
              { rotulo: 'Vezes o atual', alinhar: 'right', largura: 100 },
            ]}
            linhas={linhasProx}
          />
        </>
      )}
      <p style={{ margin: 0, fontSize: 12.5, color: COR.mudo, lineHeight: 1.4 }}>{nota}</p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Anúncios novos: como estão se comportando os que entraram há pouco
// ---------------------------------------------------------------------------

const diaMes = (iso: string | null) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : '—');

function CartaoNovo({ a, refCusto, capa = 150 }: { a: AnuncioNovo; refCusto: number | null | undefined; capa?: number }) {
  const v = a.custo_resultado_vs_referencia;
  const cor = v == null ? COR.mudo : v <= 0 ? COR.verde : v <= 25 ? COR.laranja : COR.ruim;
  return (
    <div style={{ border: `1px solid ${COR.linha}`, borderRadius: 14, padding: '12px 16px', display: 'flex', gap: 14, minWidth: 0, overflow: 'hidden' }}>
      <Capa ad={a} tamanho={capa} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <p style={{ fontSize: 15.5, fontWeight: 700, margin: 0, lineHeight: 1.25, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{a.anuncio}</p>
        <p style={{ fontSize: 12.5, color: COR.mudo, margin: '2px 0 6px' }}>
          {empreendimentoCurto(a.empreendimento)} · no ar desde {diaMes(a.primeiro_dia)} ({a.dias_no_ar} {a.dias_no_ar === 1 ? 'dia' : 'dias'})
        </p>
        <p style={{ fontSize: 13, margin: 0, lineHeight: 1.45 }}>
          <strong>{reais(a.investimento)}</strong> investidos
          {a.ctr != null ? <> · CTR {pct(a.ctr)}</> : null}
        </p>
        <p style={{ fontSize: 13, margin: '4px 0 0', lineHeight: 1.45 }}>
          Meta: <strong>{numero(a.resultados_meta)}</strong> resultados
          {a.custo_resultado_meta ? <> · <strong style={{ color: cor }}>{reaisCentavos(a.custo_resultado_meta)}</strong> por resultado</> : null}
        </p>
        {v != null && refCusto ? (
          <p style={{ fontSize: 12.5, margin: '1px 0 0', color: cor, fontWeight: 700 }}>
            {v <= 0 ? `${Math.abs(v).toLocaleString('pt-BR')}% mais barato` : `${v.toLocaleString('pt-BR')}% mais caro`} que os anúncios mais antigos ({reaisCentavos(refCusto)})
          </p>
        ) : null}
        <p style={{ fontSize: 12.5, margin: '5px 0 0', color: COR.mudo, lineHeight: 1.4 }}>
          CV: {num1(a.leads_efetivos ?? a.leads_cv)} leads · {num1(a.sql_efetivo ?? a.sql)} SQL{a.cpl_efetivo ? ` · CPL ${reaisCentavos(a.cpl_efetivo)}` : ''}
        </p>
      </div>
    </div>
  );
}

// Um bloco de anúncios novos (de uma praça ou de um produto): os que já têm resultado em destaque e, abaixo, os que ainda não têm
function BlocoNovos({ n, colunas, titulo }: { n: AnunciosNovos; colunas: 1 | 2; titulo?: string }) {
  const semResultado = n.sem_resultado ?? [];
  const ref = n.referencia;
  const limiteSem = colunas === 1 ? 8 : 6;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
      {titulo && <p style={{ fontSize: 17, fontWeight: 800, margin: 0, color: COR.escuro, borderBottom: `2px solid ${COR.laranja}`, paddingBottom: 4 }}>{titulo}</p>}
      <p style={{ fontSize: 13.5, margin: 0, color: COR.texto, lineHeight: 1.4 }}>
        <strong>{n.total_novos ?? n.anuncios.length}</strong> anúncio(s) novo(s) desde {diaMes(n.desde)}
        {n.anuncios.length ? '; em destaque os que já têm resultado (a melhor versão entre as campanhas em que roda)' : ''}
        {n.sem_resultado_ainda ? `${n.anuncios.length ? '; ' : ': '}${n.sem_resultado_ainda} ainda sem resultado` : ''}.
        {ref?.custo_resultado_meta ? <> Régua dos {numero(ref.anuncios_veteranos)} mais antigos: <strong>{reaisCentavos(ref.custo_resultado_meta)}</strong> por resultado na Meta{ref.cpl ? <> e CPL de {reaisCentavos(ref.cpl)} no CV</> : null}.</> : null}
      </p>
      {n.anuncios.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: colunas === 1 ? '1fr 1fr' : '1fr', gap: 12 }}>
          {n.anuncios.slice(0, colunas === 1 ? 4 : 2).map((a) => (
            <CartaoNovo key={a.chave} a={a} refCusto={ref?.custo_resultado_meta} capa={colunas === 1 ? 150 : 112} />
          ))}
        </div>
      )}
      {semResultado.length > 0 && (
        <div>
          <p style={{ fontSize: 13.5, fontWeight: 800, margin: '2px 0 6px', color: COR.escuro }}>
            Também entraram, ainda sem resultado
            <span style={{ fontWeight: 400, color: COR.mudo }}> · recém-subidos, ainda sem lead ou conversa registrada</span>
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: colunas === 1 ? `repeat(${Math.min(semResultado.length, 4)}, 1fr)` : '1fr 1fr 1fr', gap: 8 }}>
            {semResultado.slice(0, limiteSem).map((a) => (
              <div key={a.chave} style={{ border: `1px solid ${COR.linha}`, borderRadius: 12, padding: 8, display: 'flex', gap: 10, minWidth: 0, overflow: 'hidden' }}>
                <Capa ad={a} tamanho={64} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <p style={{ fontSize: 12.5, fontWeight: 700, margin: 0, lineHeight: 1.2, wordBreak: 'break-word', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }} title={a.anuncio}>{colunas === 2 ? a.anuncio.replace(/^[^_]*_/, '').replace(/[-_]/g, ' ') : a.anuncio}</p>
                  <p style={{ fontSize: 11.5, color: COR.mudo, margin: '2px 0 0', lineHeight: 1.3 }}>
                    {a.investimento > 0 ? `desde ${diaMes(a.primeiro_dia)} · ${reais(a.investimento)}` : `no ar desde ${diaMes(a.primeiro_dia)} · ainda sem gasto`}
                  </p>
                </div>
              </div>
            ))}
          </div>
          {(n.sem_resultado_ainda ?? 0) > Math.min(semResultado.length, limiteSem) && (
            <p style={{ fontSize: 12, margin: '4px 0 0', color: COR.mudo }}>+ {(n.sem_resultado_ainda ?? 0) - Math.min(semResultado.length, limiteSem)} outros anúncios novos, também sem resultado.</p>
          )}
        </div>
      )}
    </div>
  );
}

export function SlideAnunciosNovos({ d, praca }: { d: Apresentacao; praca: string }) {
  const p = d.anuncios_por_praca?.[praca];
  const n = p?.novos;
  const vazio = (x?: AnunciosNovos) => !x || (!x.anuncios.length && !(x.sem_resultado ?? []).length);
  if (!n || vazio(n)) return <SemDados>Nenhum anúncio entrou neste mês em {praca}.</SemDados>;
  // Praça com mais de um produto: cada produto no seu bloco, com os seus anúncios e a sua régua
  const produtos = Object.entries(p?.novos_por_produto ?? {}).filter(([, x]) => !vazio(x));
  if (produtos.length > 1) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${produtos.length}, 1fr)`, gap: 28 }}>
        {produtos.map(([emp, x]) => (
          <BlocoNovos key={emp} n={x} colunas={2} titulo={empreendimentoCurto(emp)} />
        ))}
      </div>
    );
  }
  return <BlocoNovos n={n} colunas={1} />;
}
