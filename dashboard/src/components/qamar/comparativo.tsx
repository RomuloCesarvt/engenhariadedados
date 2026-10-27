'use client';

/** Slides do comparativo entre meses: só números e tendência, sem as listas de conteúdos. */

import React from 'react';
import { numero } from '../../lib/format';
import { QamarComparativo, ResumoMes } from '../../types/qamar';
import { Q } from './QuadroQamar';
import { Cartao, Tabela, compactoQ } from './slides';

type Fmt = 'n' | 'pct' | 's' | 'reais' | 'compacto';
interface Metrica {
  nome: string;
  pegar: (r: ResumoMes) => number | null | undefined;
  fmt: Fmt;
}

const MENOS = '−';
const dec = (n: number, casas = 1) => n.toFixed(casas).replace('.', ',');

function fmtValor(v: number | null | undefined, fmt: Fmt): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  if (fmt === 'pct') return `${dec(v, 2)}%`;
  if (fmt === 's') return `${numero(v)}s`;
  if (fmt === 'reais') return `R$ ${numero(Math.round(v))}`;
  if (fmt === 'compacto') return compactoQ(v);
  return numero(v);
}

const pctTexto = (v: number) => `${v >= 0 ? '+' : MENOS}${dec(Math.abs(v))}%`;

/** Meses fechados, com valor, na ordem: o mês em andamento não entra em média nem em tendência. */
function fechados(cmp: QamarComparativo, m: Metrica): { rotulo: string; valor: number }[] {
  return cmp.resumos
    .filter((r) => r.mes !== cmp.mes_em_andamento)
    .map((r) => ({ rotulo: r.rotulo, valor: m.pegar(r) }))
    .filter((p): p is { rotulo: string; valor: number } => typeof p.valor === 'number');
}

function cabecalhos(cmp: QamarComparativo): string[] {
  return cmp.resumos.map((r) => (r.mes === cmp.mes_em_andamento ? `${r.rotulo}*` : r.rotulo));
}

function TabelaMeses({ cmp, metricas }: { cmp: QamarComparativo; metricas: Metrica[] }) {
  const n = cmp.resumos.length;
  const fonte = n > 8 ? 12.5 : n > 6 ? 14 : 15.5;
  const larguraMes = Math.floor(58 / n);
  const linhas = metricas.map((m) => {
    const fech = fechados(cmp, m);
    // Média só com pelo menos dois meses fechados com dado (um mês sozinho não é média)
    const media = fech.length >= 2 ? fech.reduce((t, p) => t + p.valor, 0) / fech.length : null;
    const ultimo = fech.length ? fech[fech.length - 1].valor : null;
    const antes = fech.slice(0, -1);
    const mediaAntes = antes.length ? antes.reduce((t, p) => t + p.valor, 0) / antes.length : null;
    const delta = ultimo !== null && mediaAntes ? ((ultimo - mediaAntes) / mediaAntes) * 100 : null;
    return [
      m.nome,
      ...cmp.resumos.map((r) => fmtValor(m.pegar(r), m.fmt)),
      fmtValor(media === null ? null : m.fmt === 'n' || m.fmt === 'compacto' ? Math.round(media) : media, m.fmt),
      <span key="d" style={{ fontWeight: 800, color: delta === null ? Q.mudo : Q.verde }}>
        {delta === null ? '—' : pctTexto(delta)}
      </span>,
    ];
  });
  return (
    <Tabela
      colunas={['Métrica', ...cabecalhos(cmp), 'Média', 'Último × média']}
      larguras={[`${100 - larguraMes * n - 22}%`, ...cmp.resumos.map(() => `${larguraMes}%`), '11%', '11%']}
      linhas={linhas}
      compacta
      fonte={fonte}
    />
  );
}

function RodapeComparativo({ cmp }: { cmp: QamarComparativo }) {
  return (
    <p style={{ margin: '12px 0 0', fontSize: 13, color: Q.mudo, lineHeight: 1.4 }}>
      Média e "Último × média" usam só meses fechados{cmp.mes_em_andamento ? '; * mês em andamento, ainda parcial' : ''}. "Último × média" compara o último mês fechado com a média dos anteriores.
    </p>
  );
}

/* ------------------------------------------------------------------------------------------------- gráfico */

function GraficoLinha({ titulo, cmp, m }: { titulo: string; cmp: QamarComparativo; m: Metrica }) {
  const pontos = cmp.resumos.map((r) => ({ rotulo: r.rotulo, valor: m.pegar(r), parcial: r.mes === cmp.mes_em_andamento }));
  const valores = pontos.map((p) => p.valor).filter((v): v is number => typeof v === 'number');
  const L = 540;
  const A = 190;
  const mx = 34;
  const topo = 30;
  const base = A - 34;
  const max = Math.max(...valores, 1);
  const min = Math.min(...valores, 0);
  const faixa = max - min || 1;
  const x = (i: number) => mx + (pontos.length === 1 ? (L - 2 * mx) / 2 : (i * (L - 2 * mx)) / (pontos.length - 1));
  const y = (v: number) => base - ((v - min) / faixa) * (base - topo);
  const ligados = pontos.map((p, i) => (typeof p.valor === 'number' ? `${x(i)},${y(p.valor)}` : null)).filter(Boolean) as string[];
  return (
    <Cartao estilo={{ padding: '14px 18px', minWidth: 0 }}>
      <p style={{ margin: 0, fontSize: 16, fontWeight: 800, color: Q.verde }}>{titulo}</p>
      <svg viewBox={`0 0 ${L} ${A}`} style={{ width: '100%', display: 'block', marginTop: 4 }}>
        <line x1={mx} x2={L - mx} y1={base} y2={base} stroke={Q.verdeBorda} strokeWidth={1.5} />
        <polyline points={ligados.join(' ')} fill="none" stroke={Q.verde2} strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
        {pontos.map((p, i) =>
          typeof p.valor === 'number' ? (
            <g key={p.rotulo}>
              <circle cx={x(i)} cy={y(p.valor)} r={5} fill={p.parcial ? '#fff' : Q.laranja} stroke={p.parcial ? Q.laranja : '#fff'} strokeWidth={2} />
              <text x={x(i)} y={y(p.valor) - 11} textAnchor="middle" fontSize={13} fontWeight={700} fill={Q.texto}>
                {fmtValor(p.valor, m.fmt === 'n' ? 'compacto' : m.fmt)}
              </text>
            </g>
          ) : null
        )}
        {pontos.map((p, i) => (
          <text key={`l${p.rotulo}`} x={x(i)} y={A - 12} textAnchor="middle" fontSize={13} fill={Q.mudo}>
            {p.rotulo}
            {p.parcial ? '*' : ''}
          </text>
        ))}
      </svg>
    </Cartao>
  );
}

/* ------------------------------------------------------------------------------------------------- metricas */

const IG = (campo: string) => (r: ResumoMes) => r.instagram?.[campo] as number | null | undefined;
const ST = (campo: string) => (r: ResumoMes) => r.site?.[campo] as number | null | undefined;

const M_VIEWS: Metrica = { nome: 'Visualizações', pegar: IG('visualizacoes'), fmt: 'compacto' };
const M_INTER: Metrica = { nome: 'Interações', pegar: IG('interacoes'), fmt: 'n' };
const M_TAXA: Metrica = { nome: 'Taxa de engajamento', pegar: IG('taxa_engajamento'), fmt: 'pct' };
const M_PERFIL: Metrica = { nome: 'Visitas ao perfil', pegar: IG('visitas_perfil'), fmt: 'n' };
const M_USERS: Metrica = { nome: 'Usuários do site', pegar: ST('usuarios'), fmt: 'n' };

export function CmpInstagram({ cmp }: { cmp: QamarComparativo }) {
  const metricas: Metrica[] = [
    { nome: 'Alcance (contas alcançadas)', pegar: IG('alcance'), fmt: 'compacto' },
    M_VIEWS,
    M_INTER,
    M_TAXA,
    M_PERFIL,
    { nome: 'Toques no link da bio', pegar: IG('toques_link'), fmt: 'n' },
    { nome: 'Visualizações dos stories', pegar: IG('visualizacoes_stories'), fmt: 'compacto' },
    { nome: 'Posts no feed', pegar: IG('posts'), fmt: 'n' },
    { nome: 'Reels', pegar: IG('reels'), fmt: 'n' },
  ];
  return (
    <>
      <TabelaMeses cmp={cmp} metricas={metricas} />
      <RodapeComparativo cmp={cmp} />
    </>
  );
}

export function CmpTendencias({ cmp }: { cmp: QamarComparativo }) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <GraficoLinha titulo="Instagram · visualizações" cmp={cmp} m={M_VIEWS} />
        <GraficoLinha titulo="Instagram · interações" cmp={cmp} m={M_INTER} />
        <GraficoLinha titulo="Instagram · visitas ao perfil" cmp={cmp} m={M_PERFIL} />
        <GraficoLinha titulo="Site · usuários" cmp={cmp} m={M_USERS} />
      </div>
      <p style={{ margin: '8px 0 0', fontSize: 13, color: Q.mudo }}>{cmp.mes_em_andamento ? 'Ponto vazio (*): mês em andamento, ainda parcial.' : ''}</p>
    </>
  );
}

export function CmpSiteEConteudo({ cmp }: { cmp: QamarComparativo }) {
  const yt = (campo: string) => (r: ResumoMes) => (r.youtube?.completo ? (r.youtube?.[campo] as number) : null);
  const metricas: Metrica[] = [
    M_USERS,
    { nome: 'Novos usuários do site', pegar: ST('novos'), fmt: 'n' },
    { nome: 'Tempo médio de engajamento', pegar: ST('tempo_engajamento_s'), fmt: 's' },
    { nome: 'Eventos no site', pegar: ST('eventos'), fmt: 'compacto' },
    { nome: 'Posts no blog', pegar: (r) => r.blog?.posts as number | undefined, fmt: 'n' },
    { nome: 'Vídeos publicados no YouTube', pegar: yt('videos'), fmt: 'n' },
    { nome: 'Visualizações desses vídeos (acumulado)', pegar: yt('visualizacoes'), fmt: 'n' },
  ];
  return (
    <>
      <TabelaMeses cmp={cmp} metricas={metricas} />
      <RodapeComparativo cmp={cmp} />
      <p style={{ margin: '4px 0 0', fontSize: 13, color: Q.mudo }}>YouTube: meses que o feed público não cobre aparecem como "—".</p>
    </>
  );
}

export function CmpPago({ cmp }: { cmp: QamarComparativo }) {
  const metricas: Metrica[] = [
    { nome: 'Investimento em tráfego pago (agência)', pegar: (r) => r.trafego_pago?.investimento_agencia as number | undefined, fmt: 'reais' },
    { nome: 'Alcance dos anúncios (agência)', pegar: (r) => r.trafego_pago?.alcance as number | undefined, fmt: 'n' },
    { nome: 'Impressões dos anúncios no Facebook', pegar: (r) => r.facebook?.impressoes_pagas as number | undefined, fmt: 'compacto' },
    { nome: 'Investimento dos anúncios no Facebook', pegar: (r) => r.facebook?.investimento as number | undefined, fmt: 'reais' },
  ];
  return (
    <>
      <TabelaMeses cmp={cmp} metricas={metricas} />
      <RodapeComparativo cmp={cmp} />
      <p style={{ margin: '4px 0 0', fontSize: 13, color: Q.mudo }}>Tráfego pago da agência: conta CA Moura Leite. Facebook: anúncios de todas as contas de anúncio do sistema no posicionamento Facebook.</p>
    </>
  );
}

/* ------------------------------------------------------------------------------------------------- leitura em frases */

function lerMetrica(cmp: QamarComparativo, m: Metrica, rotulo: string, genero: 'o' | 'a' = 'o'): string | null {
  const f = fechados(cmp, m);
  if (f.length < 3) return null;
  const ultimo = f[f.length - 1];
  const anteriores = f.slice(0, -1);
  const media = anteriores.reduce((t, p) => t + p.valor, 0) / anteriores.length;
  const melhor = f.reduce((a, b) => (b.valor > a.valor ? b : a));
  const pior = f.reduce((a, b) => (b.valor < a.valor ? b : a));
  const metade = Math.floor(f.length / 2);
  const ini = f.slice(0, metade).reduce((t, p) => t + p.valor, 0) / metade;
  const fim = f.slice(-metade).reduce((t, p) => t + p.valor, 0) / metade;
  const tendencia = ini ? ((fim - ini) / ini) * 100 : 0;
  const rumo = Math.abs(tendencia) < 8 ? 'estável' : tendencia > 0 ? 'em alta' : 'em queda';
  const contraMedia = media ? ((ultimo.valor - media) / media) * 100 : 0;
  const vsMedia = Math.abs(contraMedia) < 3 ? 'em linha com a média' : `${pctTexto(contraMedia)} frente à média`;
  return `${rotulo}: ${ultimo.rotulo} ficou ${vsMedia} dos meses anteriores (${fmtValor(ultimo.valor, m.fmt === 'n' ? 'compacto' : m.fmt)}). Melhor mês: ${melhor.rotulo} (${fmtValor(melhor.valor, m.fmt === 'n' ? 'compacto' : m.fmt)}); pior: ${pior.rotulo} (${fmtValor(pior.valor, m.fmt === 'n' ? 'compacto' : m.fmt)}). Tendência no período: ${rumo}.`;
}

export function CmpLeitura({ cmp }: { cmp: QamarComparativo }) {
  const frases = [
    lerMetrica(cmp, M_VIEWS, 'Visualizações no Instagram'),
    lerMetrica(cmp, M_INTER, 'Interações no Instagram'),
    lerMetrica(cmp, M_TAXA, 'Taxa de engajamento'),
    lerMetrica(cmp, M_PERFIL, 'Visitas ao perfil'),
    lerMetrica(cmp, M_USERS, 'Usuários do site'),
    lerMetrica(cmp, { nome: 'Posts no blog', pegar: (r) => r.blog?.posts as number | undefined, fmt: 'n' }, 'Posts no blog'),
  ].filter(Boolean) as string[];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {frases.length === 0 && (
        <Cartao tom="laranja">
          <p style={{ margin: 0, fontSize: 17, color: Q.texto }}>Escolha pelo menos 3 meses fechados para a leitura de tendência aparecer.</p>
        </Cartao>
      )}
      {frases.map((f, i) => (
        <Cartao key={i} tom={i % 2 ? 'laranja' : 'verde'} estilo={{ padding: '12px 20px' }}>
          <p style={{ margin: 0, fontSize: 15.5, lineHeight: 1.4, color: Q.texto }}>{f}</p>
        </Cartao>
      ))}
      <p style={{ margin: 0, fontSize: 13, color: Q.mudo }}>
        Tendência = média da segunda metade do período contra a da primeira (estável quando a diferença é menor que 8%). Mês em andamento fica de fora das contas.
      </p>
    </div>
  );
}
