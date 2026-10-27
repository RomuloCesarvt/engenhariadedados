'use client';

/**
 * Gráficos do BI. Regras: um eixo só (duas medidas → alternar o tipo, nunca dois eixos),
 * marcas finas (barra ≤ 24px com ponta arredondada, linha 2px), vão de 2px na cor da superfície
 * entre segmentos, grade em linha fina, legenda para 2+ séries, rótulos só no que conta
 * (total, pico, último), tooltip com todas as séries e uma visão de tabela equivalente.
 * Cada gráfico pode trocar de forma (colunas, área, linhas, funil...) sem perder a leitura.
 */

import React, { useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertTriangle,
  AlignLeft,
  AreaChart as IconeArea,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Box,
  Filter,
  LineChart as IconeLinhas,
  Square,
  TrendingUp,
} from 'lucide-react';
import { Agrupado, FunilEtapa, Grupo, SeriePonto } from '../../types/bi';
import { GRUPO_COR, GRUPO_LABEL, GRUPO_ORDEM, NEUTRO, SERIES, STATUS, TINTA } from '../../lib/cores';
import { numero, pct, reaisCompacto } from '../../lib/format';
import { Legenda } from './ui';

const eixo = { fill: TINTA.apagada, fontSize: 11 };

// ---------------------------------------------------------------------------
// Peças comuns
// ---------------------------------------------------------------------------

function CaixaTooltip({ titulo, linhas, rodape }: { titulo: string; linhas: { cor: string; label: string; valor: string }[]; rodape?: string }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 shadow-xl text-xs min-w-[190px] backdrop-blur">
      <p className="text-slate-300 font-medium mb-1.5">{titulo}</p>
      {linhas.map((l) => (
        <div key={l.label} className="flex items-center justify-between gap-4 py-0.5">
          <span className="inline-flex items-center gap-2 text-slate-400">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: l.cor }} aria-hidden />
            {l.label}
          </span>
          <span className="font-semibold text-slate-100 tabular-nums">{l.valor}</span>
        </div>
      ))}
      {rodape && <p className="text-slate-400 border-t border-slate-700 mt-1.5 pt-1.5">{rodape}</p>}
    </div>
  );
}

type OpcaoTipo<T extends string> = { id: T; label: string; icone: React.ElementType };

/** Troca a forma do gráfico (colunas, área, linhas, funil...). */
function TiposGrafico<T extends string>({ opcoes, valor, onChange }: { opcoes: OpcaoTipo<T>[]; valor: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-lg bg-slate-800/60 p-0.5 text-[11px]" role="group" aria-label="Tipo de gráfico">
      {opcoes.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          aria-pressed={valor === o.id}
          title={o.label}
          className={`inline-flex items-center gap-1 px-2 py-1 rounded-md transition-colors ${
            valor === o.id ? 'bg-slate-700 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <o.icone className="w-3 h-3" /> {o.label}
        </button>
      ))}
    </div>
  );
}

type ModoProfundidade = '2d' | '3d';

function SeletorProfundidade({ valor, onChange }: { valor: ModoProfundidade; onChange: (valor: ModoProfundidade) => void }) {
  return (
    <div className="inline-flex rounded-lg bg-slate-800/60 p-0.5 text-[11px]" role="group" aria-label="Profundidade do gráfico">
      {([
        { id: '2d' as const, label: '2D', icone: Square },
        { id: '3d' as const, label: '3D', icone: Box },
      ]).map((opcao) => (
        <button
          key={opcao.id}
          type="button"
          onClick={() => onChange(opcao.id)}
          aria-pressed={valor === opcao.id}
          title={`Visualização ${opcao.label}`}
          className={`inline-flex min-w-10 items-center justify-center gap-1 rounded-md px-2 py-1 transition-colors ${
            valor === opcao.id ? 'bg-slate-700 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <opcao.icone className="h-3 w-3" aria-hidden />
          {opcao.label}
        </button>
      ))}
    </div>
  );
}

function ControlesGrafico({
  seletorTipo,
  profundidade,
  onProfundidade,
}: {
  seletorTipo?: React.ReactNode;
  profundidade: ModoProfundidade;
  onProfundidade: (valor: ModoProfundidade) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {seletorTipo}
      <SeletorProfundidade valor={profundidade} onChange={onProfundidade} />
    </div>
  );
}

type Barra3DProps = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  fill?: string;
};

/** Prisma SVG leve: mantém eixos e tooltips do Recharts sem introduzir canvas pesado. */
function Barra3D({ x = 0, y = 0, width = 0, height = 0, fill = SERIES.s1 }: Barra3DProps) {
  if (width <= 0 || height <= 0) return null;
  const profundidade = Math.max(3, Math.min(7, width * 0.26, height * 0.42));
  const frente = Math.max(1, width - profundidade);

  return (
    <g className="barra-3d" aria-hidden>
      <path
        d={`M ${x} ${y + profundidade} L ${x + frente} ${y + profundidade} L ${x + frente} ${y + height} L ${x} ${y + height} Z`}
        fill={fill}
      />
      <path
        d={`M ${x} ${y + profundidade} L ${x + profundidade} ${y} L ${x + width} ${y} L ${x + frente} ${y + profundidade} Z`}
        fill={fill}
        className="barra-3d-topo"
      />
      <path
        d={`M ${x + frente} ${y + profundidade} L ${x + width} ${y} L ${x + width} ${y + height - profundidade} L ${x + frente} ${y + height} Z`}
        fill={fill}
        className="barra-3d-lateral"
      />
      <path d={`M ${x + 1} ${y + profundidade + 1} L ${x + frente - 1} ${y + profundidade + 1}`} className="barra-3d-brilho" />
    </g>
  );
}

/** Linha de resumo acima do gráfico: poucos números grandes que contam a história. */
function Resumo({ itens, acao }: { itens: { rotulo: string; valor: string; detalhe?: string }[]; acao?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
      <dl className="flex flex-wrap gap-x-6 gap-y-2">
        {itens.map((i) => (
          <div key={i.rotulo}>
            <dt className="text-[10px] uppercase tracking-wide text-slate-500">{i.rotulo}</dt>
            <dd className="text-lg font-semibold text-slate-50 leading-tight">
              {i.valor}
              {i.detalhe && <span className="ml-1.5 text-xs font-normal text-slate-400">{i.detalhe}</span>}
            </dd>
          </div>
        ))}
      </dl>
      {acao}
    </div>
  );
}

const semDados = <p className="text-xs text-slate-500 py-10 text-center">Sem dados no período.</p>;

// ---------------------------------------------------------------------------
// Leads por grupo de origem ao longo do tempo
// ---------------------------------------------------------------------------

type TipoTempo = 'colunas' | 'area' | 'linhas';
const TIPOS_TEMPO: OpcaoTipo<TipoTempo>[] = [
  { id: 'colunas', label: 'Colunas', icone: BarChart3 },
  { id: 'area', label: 'Área', icone: IconeArea },
  { id: 'linhas', label: 'Linhas', icone: IconeLinhas },
];

export function LeadsPorGrupoChart({ serie, modo }: { serie: SeriePonto[]; modo: 'grafico' | 'tabela' }) {
  const [tipo, setTipo] = useState<TipoTempo>('colunas');
  const [profundidade, setProfundidade] = useState<ModoProfundidade>('3d');
  const dados = useMemo(() => serie.map((p) => ({ ...p, total: GRUPO_ORDEM.reduce((s, g) => s + p[g], 0), topo: 0 })), [serie]);
  const totais = useMemo(() => Object.fromEntries(GRUPO_ORDEM.map((g) => [g, serie.reduce((s, p) => s + p[g], 0)])) as Record<Grupo, number>, [serie]);
  const grupos = GRUPO_ORDEM.filter((g) => totais[g] > 0);
  const total = dados.reduce((s, p) => s + p.total, 0);
  const pico = dados.reduce((m, p) => (p.total > (m?.total ?? -1) ? p : m), dados[0]);

  if (modo === 'tabela') {
    return (
      <div className="overflow-x-auto">
        <table className="tabela">
          <thead>
            <tr>
              <th>Período</th>
              {grupos.map((g) => (
                <th key={g} className="text-right">
                  {GRUPO_LABEL[g]}
                </th>
              ))}
              <th className="text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {dados.map((p) => (
              <tr key={p.periodo}>
                <td>{p.rotulo}</td>
                {grupos.map((g) => (
                  <td key={g} className="num">
                    {numero(p[g])}
                  </td>
                ))}
                <td className="num font-semibold">{numero(p.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (!total) return semDados;

  const tooltip = (
    <Tooltip
      cursor={tipo === 'colunas' ? { fill: 'rgba(148,163,184,0.08)' } : { stroke: TINTA.eixo }}
      content={({ active, payload }: any) => {
        if (!active || !payload?.length) return null;
        const p = payload[0].payload;
        return (
          <CaixaTooltip
            titulo={p.rotulo}
            linhas={[...grupos].reverse().map((g) => ({ cor: GRUPO_COR[g], label: GRUPO_LABEL[g], valor: numero(p[g]) }))}
            rodape={`${numero(p.total)} leads no período`}
          />
        );
      }}
    />
  );
  const eixos = (
    <>
      <CartesianGrid vertical={false} stroke={TINTA.grade} />
      <XAxis dataKey="rotulo" tick={eixo} axisLine={{ stroke: TINTA.eixo }} tickLine={false} minTickGap={12} />
      <YAxis tick={eixo} axisLine={false} tickLine={false} tickFormatter={(v) => numero(v)} width={44} allowDecimals={false} />
    </>
  );

  return (
    <>
      <Resumo
        itens={[
          { rotulo: 'Leads', valor: numero(total) },
          { rotulo: 'Média por período', valor: numero(Math.round(total / Math.max(dados.length, 1))) },
          { rotulo: 'Pico', valor: numero(pico?.total ?? 0), detalhe: pico?.rotulo },
        ]}
        acao={
          <ControlesGrafico
            seletorTipo={<TiposGrafico opcoes={TIPOS_TEMPO} valor={tipo} onChange={setTipo} />}
            profundidade={profundidade}
            onProfundidade={setProfundidade}
          />
        }
      />
      <Legenda itens={grupos.map((g) => ({ cor: GRUPO_COR[g], label: `${GRUPO_LABEL[g]} · ${numero(totais[g])} (${pct((totais[g] / total) * 100)})` }))} />
      <div className={`h-72 ${profundidade === '3d' ? 'chart-3d-stage' : ''}`}>
        <ResponsiveContainer width="100%" height="100%">
          {tipo === 'colunas' ? (
            <BarChart data={dados} margin={{ top: 20, right: 8, left: 0, bottom: 0 }}>
              {eixos}
              {tooltip}
              {grupos.map((g, i) => (
                <Bar
                  key={g}
                  dataKey={g}
                  stackId="leads"
                  fill={GRUPO_COR[g]}
                  stroke={TINTA.superficie}
                  strokeWidth={2}
                  maxBarSize={24}
                  radius={i === grupos.length - 1 ? [4, 4, 0, 0] : undefined}
                  shape={profundidade === '3d' ? <Barra3D /> : undefined}
                  isAnimationActive={false}
                />
              ))}
              {/* barra de altura zero no topo da pilha: carrega o total de cada coluna */}
              <Bar dataKey="topo" stackId="leads" fill="transparent" isAnimationActive={false}>
                <LabelList dataKey="total" position="top" fill={TINTA.secundaria} fontSize={11} formatter={(v: number) => (v ? numero(v) : '')} />
              </Bar>
            </BarChart>
          ) : tipo === 'area' ? (
            <AreaChart data={dados} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
              <defs>
                {grupos.map((g) => (
                  <linearGradient key={g} id={`grad-${g}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={GRUPO_COR[g]} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={GRUPO_COR[g]} stopOpacity={0.08} />
                  </linearGradient>
                ))}
              </defs>
              {eixos}
              {tooltip}
              {grupos.map((g) => (
                <Area
                  key={g}
                  type="monotone"
                  dataKey={g}
                  stackId="leads"
                  stroke={GRUPO_COR[g]}
                  strokeWidth={2}
                  fill={`url(#grad-${g})`}
                  activeDot={{ r: 4, stroke: TINTA.superficie, strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              ))}
            </AreaChart>
          ) : (
            <LineChart data={dados} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
              {eixos}
              {tooltip}
              {grupos.map((g) => (
                <React.Fragment key={g}>
                  {profundidade === '3d' && (
                    <Line
                      type="monotone"
                      dataKey={g}
                      stroke={GRUPO_COR[g]}
                      strokeWidth={7}
                      dot={false}
                      activeDot={false}
                      className="linha-3d-depth"
                      isAnimationActive={false}
                    />
                  )}
                  <Line
                    type="monotone"
                    dataKey={g}
                    stroke={GRUPO_COR[g]}
                    strokeWidth={profundidade === '3d' ? 3 : 2}
                    dot={
                      profundidade === '3d'
                        ? { r: 3, fill: GRUPO_COR[g], stroke: TINTA.superficie, strokeWidth: 1.5 }
                        : false
                    }
                    activeDot={{ r: 4, stroke: TINTA.superficie, strokeWidth: 2 }}
                    className={profundidade === '3d' ? 'linha-3d-face' : undefined}
                    isAnimationActive={false}
                  />
                  {profundidade === '3d' && (
                    <Line
                      type="monotone"
                      dataKey={g}
                      stroke="#ffffff"
                      strokeWidth={1}
                      dot={false}
                      activeDot={false}
                      className="linha-3d-brilho"
                      isAnimationActive={false}
                    />
                  )}
                </React.Fragment>
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Vendas online no tempo: quantidade ou VGV
// ---------------------------------------------------------------------------

type TipoVendas = 'quantidade' | 'vgv';
const TIPOS_VENDAS: OpcaoTipo<TipoVendas>[] = [
  { id: 'quantidade', label: 'Vendas', icone: BarChart3 },
  { id: 'vgv', label: 'VGV', icone: IconeArea },
];

export function VendasChart({ serie, modo }: { serie: SeriePonto[]; modo: 'grafico' | 'tabela' }) {
  const [tipo, setTipo] = useState<TipoVendas>('quantidade');
  const [profundidade, setProfundidade] = useState<ModoProfundidade>('3d');
  const dados = serie;
  const online = dados.reduce((s, p) => s + p.vendas_online, 0);
  const vgv = dados.reduce((s, p) => s + p.vgv, 0);
  const maiorVgv = Math.max(0, ...dados.map((p) => p.vgv));

  if (modo === 'tabela') {
    return (
      <div className="overflow-x-auto">
        <table className="tabela">
          <thead>
            <tr>
              <th>Período</th>
              <th className="text-right">Vendas online</th>
              <th className="text-right">VGV online</th>
            </tr>
          </thead>
          <tbody>
            {dados.map((p) => (
              <tr key={p.periodo}>
                <td>{p.rotulo}</td>
                <td className="num font-semibold">{numero(p.vendas_online)}</td>
                <td className="num">{reaisCompacto(p.vgv)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const cabecalho = (
    <Resumo
      itens={[
        { rotulo: 'Vendas online', valor: numero(online) },
        { rotulo: 'VGV online', valor: reaisCompacto(vgv) },
      ]}
      acao={
        <ControlesGrafico
          seletorTipo={<TiposGrafico opcoes={TIPOS_VENDAS} valor={tipo} onChange={setTipo} />}
          profundidade={profundidade}
          onProfundidade={setProfundidade}
        />
      }
    />
  );
  if (!online) return <>{cabecalho}{semDados}</>;

  return (
    <>
      {cabecalho}
      {tipo === 'quantidade' && (
        <Legenda
          itens={[
            { cor: SERIES.s1, label: 'Vendas online' },
          ]}
        />
      )}
      <div className={`h-64 ${profundidade === '3d' ? 'chart-3d-stage' : ''}`}>
        <ResponsiveContainer width="100%" height="100%">
          {tipo === 'quantidade' ? (
            <BarChart data={dados} margin={{ top: 20, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={TINTA.grade} />
              <XAxis dataKey="rotulo" tick={eixo} axisLine={{ stroke: TINTA.eixo }} tickLine={false} minTickGap={12} />
              <YAxis tick={eixo} axisLine={false} tickLine={false} allowDecimals={false} width={36} />
              <Tooltip
                cursor={{ fill: 'rgba(148,163,184,0.08)' }}
                content={({ active, payload }: any) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <CaixaTooltip
                      titulo={p.rotulo}
                      linhas={[{ cor: SERIES.s1, label: 'Vendas online', valor: numero(p.vendas_online) }]}
                      rodape={`VGV online ${reaisCompacto(p.vgv)}`}
                    />
                  );
                }}
              />
              <Bar
                dataKey="vendas_online"
                fill={SERIES.s1}
                stroke={TINTA.superficie}
                strokeWidth={2}
                maxBarSize={24}
                shape={profundidade === '3d' ? <Barra3D /> : undefined}
                isAnimationActive={false}
              >
                <LabelList dataKey="vendas_online" position="top" fill={TINTA.secundaria} fontSize={11} formatter={(v: number) => (v ? numero(v) : '')} />
              </Bar>
            </BarChart>
          ) : (
            <AreaChart data={dados} margin={{ top: 20, right: 16, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="grad-vgv" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={SERIES.s1} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={SERIES.s1} stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke={TINTA.grade} />
              <XAxis dataKey="rotulo" tick={eixo} axisLine={{ stroke: TINTA.eixo }} tickLine={false} minTickGap={12} />
              <YAxis tick={eixo} axisLine={false} tickLine={false} width={64} tickFormatter={(v) => reaisCompacto(v)} />
              <Tooltip
                cursor={{ stroke: TINTA.eixo }}
                content={({ active, payload }: any) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return <CaixaTooltip titulo={p.rotulo} linhas={[{ cor: SERIES.s1, label: 'VGV online', valor: reaisCompacto(p.vgv) }]} rodape={`${numero(p.vendas_online)} vendas online`} />;
                }}
              />
              <Area type="monotone" dataKey="vgv" stroke={SERIES.s1} strokeWidth={2} fill="url(#grad-vgv)" activeDot={{ r: 4, stroke: TINTA.superficie, strokeWidth: 2 }} isAnimationActive={false}>
                {/* rótulo só no pico */}
                <LabelList dataKey="vgv" position="top" fill={TINTA.secundaria} fontSize={11} formatter={(v: number) => (v && v === maiorVgv ? reaisCompacto(v) : '')} />
              </Area>
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Funil: forma de funil (padrão) ou barras com a perda de cada etapa
// ---------------------------------------------------------------------------

type TipoFunil = 'funil' | 'barras';
const TIPOS_FUNIL: OpcaoTipo<TipoFunil>[] = [
  { id: 'funil', label: 'Funil', icone: Filter },
  { id: 'barras', label: 'Barras', icone: AlignLeft },
];

/** Etapa com a pior passagem da anterior para ela (onde o funil mais perde). */
function etapaDeMaiorPerda(etapas: FunilEtapa[]): number | null {
  let pior: number | null = null;
  etapas.forEach((e, i) => {
    if (i === 0 || !etapas[i - 1].leads || e.pct_da_etapa_anterior === null) return;
    if (pior === null || (e.pct_da_etapa_anterior ?? 100) < (etapas[pior].pct_da_etapa_anterior ?? 100)) pior = i;
  });
  return pior;
}

export function FunilChart({ etapas, modo, onClickEtapa }: { etapas: FunilEtapa[]; modo: 'grafico' | 'tabela'; onClickEtapa?: (nivel: number) => void }) {
  const [tipo, setTipo] = useState<TipoFunil>('funil');
  const [profundidade, setProfundidade] = useState<ModoProfundidade>('3d');
  const topo = etapas[0]?.leads ?? 0;
  const ultimo = etapas[etapas.length - 1];
  const pior = etapaDeMaiorPerda(etapas);

  if (modo === 'tabela') {
    return (
      <table className="tabela">
        <thead>
          <tr>
            <th>Etapa</th>
            <th className="text-right">Leads</th>
            <th className="text-right">% do topo</th>
            <th className="text-right">% da etapa anterior</th>
            <th className="text-right">Pararam antes</th>
          </tr>
        </thead>
        <tbody>
          {etapas.map((e, i) => (
            <tr key={e.etapa} className={onClickEtapa ? 'cursor-pointer hover:bg-slate-800/40' : ''} onClick={() => onClickEtapa?.(i)}>
              <td>{e.label}</td>
              <td className="num font-semibold">{numero(e.leads)}</td>
              <td className="num">{pct(e.pct_do_topo)}</td>
              <td className="num">{i === 0 ? '—' : pct(e.pct_da_etapa_anterior)}</td>
              <td className="num">{i === 0 ? '—' : numero(etapas[i - 1].leads - e.leads)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (!topo) return semDados;

  return (
    <>
      <Resumo
        itens={[
          { rotulo: 'Entraram', valor: numero(topo), detalhe: 'leads' },
          { rotulo: ultimo.label, valor: numero(ultimo.leads) },
          { rotulo: 'De ponta a ponta', valor: pct((ultimo.leads / topo) * 100) },
        ]}
        acao={
          <ControlesGrafico
            seletorTipo={<TiposGrafico opcoes={TIPOS_FUNIL} valor={tipo} onChange={setTipo} />}
            profundidade={profundidade}
            onProfundidade={setProfundidade}
          />
        }
      />
      {tipo === 'funil' ? (
        <FunilForma etapas={etapas} pior={pior} onClickEtapa={onClickEtapa} profundidade={profundidade} />
      ) : (
        <FunilBarras etapas={etapas} pior={pior} onClickEtapa={onClickEtapa} profundidade={profundidade} />
      )}
    </>
  );
}

function Passagem({ de, para, destaque }: { de: FunilEtapa; para: FunilEtapa; destaque: boolean }) {
  const pararam = de.leads - para.leads;
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-0.5 text-[11px] leading-5 ${
        destaque ? 'border-amber-500/50 bg-amber-500/10 text-amber-100' : 'border-slate-700 bg-slate-900 text-slate-300'
      }`}
    >
      {destaque && <AlertTriangle className="w-3 h-3" style={{ color: STATUS.atencao }} aria-hidden />}
      <span className="font-semibold tabular-nums">{pct(para.pct_da_etapa_anterior)}</span>
      <span className="text-slate-400">avançaram</span>
      <span className="text-slate-600">·</span>
      <span className="tabular-nums">{numero(pararam)}</span>
      <span className="text-slate-400">pararam</span>
      {destaque && <span className="font-medium">· maior perda</span>}
    </div>
  );
}

function FunilForma({
  etapas,
  pior,
  onClickEtapa,
  profundidade,
}: {
  etapas: FunilEtapa[];
  pior: number | null;
  onClickEtapa?: (nivel: number) => void;
  profundidade: ModoProfundidade;
}) {
  const topo = etapas[0].leads;
  // Largura proporcional ao volume, com mínimo para as últimas etapas continuarem visíveis
  const largura = etapas.map((e) => Math.max(10, (e.leads / topo) * 100));
  return (
    <div className={`select-none ${profundidade === '3d' ? 'chart-funnel-3d' : ''}`}>
      {etapas.map((e, i) => {
        const cima = largura[i];
        const baixo = i < etapas.length - 1 ? largura[i + 1] : largura[i] * 0.86;
        const recorte = `polygon(${50 - cima / 2}% 0, ${50 + cima / 2}% 0, ${50 + baixo / 2}% 100%, ${50 - baixo / 2}% 100%)`;
        return (
          <React.Fragment key={e.etapa}>
            <button
              type="button"
              onClick={() => onClickEtapa?.(i)}
              disabled={!onClickEtapa}
              title={onClickEtapa ? `Ver os leads que chegaram a ${e.label}` : undefined}
              className="group grid w-full grid-cols-[minmax(96px,1fr)_minmax(0,2.4fr)_minmax(88px,1fr)] items-center gap-3 text-left disabled:cursor-default"
            >
              <span className="text-right text-xs leading-tight text-slate-300 group-hover:text-white">{e.label}</span>
              <span className="relative block h-11">
                {profundidade === '3d' && (
                  <span
                    className="funil-3d-sombra absolute inset-0"
                    style={{ clipPath: recorte, background: SERIES.s1 }}
                    aria-hidden
                  />
                )}
                <span
                  className={`absolute inset-0 transition-[filter,transform] duration-200 group-hover:brightness-125 ${
                    profundidade === '3d' ? 'funil-3d-face' : ''
                  }`}
                  style={{
                    clipPath: recorte,
                    background: `linear-gradient(90deg, ${SERIES.s1}cc 0%, ${SERIES.s1} 50%, ${SERIES.s1}cc 100%)`,
                  }}
                  aria-hidden
                />
              </span>
              <span className="leading-tight">
                <span className="block text-lg font-semibold text-slate-50">{numero(e.leads)}</span>
                <span className="block text-[10px] text-slate-500">{i === 0 ? 'topo do funil' : `${pct(e.pct_do_topo)} do topo`}</span>
              </span>
            </button>
            {i < etapas.length - 1 && (
              <div className="grid grid-cols-[minmax(96px,1fr)_minmax(0,2.4fr)_minmax(88px,1fr)] gap-3 py-1">
                <span />
                <span className="flex justify-center">
                  <Passagem de={e} para={etapas[i + 1]} destaque={pior === i + 1} />
                </span>
                <span />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function FunilBarras({
  etapas,
  pior,
  onClickEtapa,
  profundidade,
}: {
  etapas: FunilEtapa[];
  pior: number | null;
  onClickEtapa?: (nivel: number) => void;
  profundidade: ModoProfundidade;
}) {
  const topo = etapas[0].leads;
  return (
    <div className={`space-y-3 ${profundidade === '3d' ? 'chart-funnel-3d' : ''}`}>
      {etapas.map((e, i) => {
        const atual = (e.leads / topo) * 100;
        const anterior = i === 0 ? atual : (etapas[i - 1].leads / topo) * 100;
        return (
          <button
            key={e.etapa}
            type="button"
            onClick={() => onClickEtapa?.(i)}
            disabled={!onClickEtapa}
            className="group grid w-full grid-cols-[minmax(96px,1fr)_minmax(0,3fr)] items-center gap-3 text-left disabled:cursor-default"
          >
            <span className="text-right text-xs leading-tight text-slate-300 group-hover:text-white">{e.label}</span>
            <span className="block">
              <span className="relative block h-5 rounded bg-slate-800/60">
                {/* quanto havia na etapa anterior: a parte cinza é quem parou */}
                <span className="absolute inset-y-0 left-0 rounded-r" style={{ width: `${anterior}%`, background: NEUTRO, opacity: 0.35 }} aria-hidden />
                <span
                  className={`absolute inset-y-0 left-0 rounded-r transition-[filter,transform] group-hover:brightness-125 ${
                    profundidade === '3d' ? 'funil-barra-3d' : ''
                  }`}
                  style={{ width: `${Math.max(atual, 0.8)}%`, background: SERIES.s1 }}
                  aria-hidden
                />
              </span>
              <span className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px]">
                <span className="font-semibold text-slate-100 tabular-nums">{numero(e.leads)}</span>
                <span className="text-slate-500">{pct(e.pct_do_topo)} do topo</span>
                {i > 0 && (
                  <span className={pior === i ? 'text-amber-200' : 'text-slate-400'}>
                    · {pct(e.pct_da_etapa_anterior)} da etapa anterior · {numero(etapas[i - 1].leads - e.leads)} pararam
                    {pior === i ? ' · maior perda' : ''}
                  </span>
                )}
              </span>
            </span>
          </button>
        );
      })}
      <Legenda
        itens={[
          { cor: SERIES.s1, label: 'Chegaram à etapa' },
          { cor: NEUTRO, label: 'Pararam na passagem' },
        ]}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Funil: período atual × anterior, etapa a etapa
// ---------------------------------------------------------------------------

export function FunilComparacaoChart({
  atual,
  anterior,
  rotuloAtual,
  rotuloAnterior,
  modo,
}: {
  atual: FunilEtapa[];
  anterior: FunilEtapa[];
  rotuloAtual: string;
  rotuloAnterior: string;
  modo: 'grafico' | 'tabela';
}) {
  const maximo = Math.max(atual[0]?.leads ?? 0, anterior[0]?.leads ?? 0, 1);
  const linhas = atual.map((e, i) => {
    const a = anterior[i];
    const variacao = a && a.leads ? ((e.leads - a.leads) / a.leads) * 100 : null;
    const pp = i > 0 && e.pct_da_etapa_anterior !== null && a?.pct_da_etapa_anterior !== null && a?.pct_da_etapa_anterior !== undefined
      ? e.pct_da_etapa_anterior - a.pct_da_etapa_anterior
      : null;
    return { e, a, variacao, pp };
  });

  if (modo === 'tabela') {
    return (
      <table className="tabela">
        <thead>
          <tr>
            <th>Etapa</th>
            <th className="text-right">{rotuloAtual}</th>
            <th className="text-right">{rotuloAnterior}</th>
            <th className="text-right">Variação</th>
            <th className="text-right">Passagem (atual · anterior)</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map(({ e, a, variacao }, i) => (
            <tr key={e.etapa}>
              <td>{e.label}</td>
              <td className="num font-semibold">{numero(e.leads)}</td>
              <td className="num">{numero(a?.leads ?? 0)}</td>
              <td className="num">{variacao === null ? '—' : `${variacao > 0 ? '+' : ''}${pct(variacao)}`}</td>
              <td className="num">{i === 0 ? '—' : `${pct(e.pct_da_etapa_anterior)} · ${pct(a?.pct_da_etapa_anterior ?? null)}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (!atual[0]?.leads && !anterior[0]?.leads) return semDados;

  return (
    <>
      <Legenda
        itens={[
          { cor: SERIES.s1, label: rotuloAtual },
          { cor: NEUTRO, label: rotuloAnterior },
        ]}
      />
      <div className="space-y-3.5">
        {linhas.map(({ e, a, variacao, pp }, i) => {
          const subiu = (variacao ?? 0) > 0;
          return (
            <div key={e.etapa} className="grid grid-cols-[minmax(96px,1fr)_minmax(0,2.4fr)_minmax(110px,1fr)] items-center gap-3">
              <span className="text-right text-xs leading-tight text-slate-300">{e.label}</span>
              <span className="space-y-1">
                <span className="block h-3 rounded-r" style={{ width: `${Math.max((e.leads / maximo) * 100, 0.8)}%`, background: SERIES.s1 }} aria-hidden />
                <span className="block h-3 rounded-r" style={{ width: `${Math.max(((a?.leads ?? 0) / maximo) * 100, 0.8)}%`, background: NEUTRO }} aria-hidden />
              </span>
              <span className="leading-tight">
                <span className="flex items-baseline gap-1.5">
                  <span className="text-base font-semibold text-slate-50">{numero(e.leads)}</span>
                  <span className="text-[11px] text-slate-500">vs {numero(a?.leads ?? 0)}</span>
                </span>
                <span className="flex flex-wrap items-center gap-x-1.5 text-[10px]">
                  {variacao === null ? (
                    <span className="text-slate-500">sem base</span>
                  ) : (
                    <span className={`inline-flex items-center font-medium ${subiu ? 'text-emerald-400' : variacao < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                      {subiu ? <ArrowUpRight className="w-3 h-3" /> : variacao < 0 ? <ArrowDownRight className="w-3 h-3" /> : null}
                      {subiu ? '+' : ''}
                      {pct(variacao)}
                    </span>
                  )}
                  {i > 0 && pp !== null && (
                    <span className="text-slate-500">
                      passagem {pp > 0 ? '+' : ''}
                      {pp.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} p.p.
                    </span>
                  )}
                </span>
              </span>
            </div>
          );
        })}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Participação por grupo de origem: rosca com o total no centro e lista clicável
// ---------------------------------------------------------------------------

export function ParticipacaoChart({ grupos, onSelecionar }: { grupos: Agrupado[]; onSelecionar?: (g: Agrupado) => void }) {
  const [ativo, setAtivo] = useState<string | null>(null);
  const [profundidade, setProfundidade] = useState<ModoProfundidade>('3d');
  const itens = grupos.filter((g) => g.leads > 0);
  const total = itens.reduce((s, g) => s + g.leads, 0);
  if (!total) return semDados;
  const destaque = itens.find((g) => g.chave === ativo);

  return (
    <>
      <div className="mb-2 flex justify-end">
        <SeletorProfundidade valor={profundidade} onChange={setProfundidade} />
      </div>
      <div className="grid gap-3">
        <div className={`relative mx-auto h-44 w-full max-w-[220px] ${profundidade === '3d' ? 'chart-pie-3d' : ''}`}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              {profundidade === '3d' &&
                [52, 50, 48].map((cy) => (
                  <Pie
                    key={cy}
                    data={itens}
                    dataKey="leads"
                    nameKey="label"
                    innerRadius="68%"
                    outerRadius="100%"
                    cy={`${cy}%`}
                    paddingAngle={itens.length > 1 ? 2 : 0}
                    stroke="none"
                    startAngle={90}
                    endAngle={-270}
                    isAnimationActive={false}
                  >
                    {itens.map((g) => (
                      <Cell
                        key={`${cy}-${g.chave}`}
                        className="pie-3d-depth"
                        fill={GRUPO_COR[g.chave as Grupo] ?? NEUTRO}
                        opacity={0.5}
                        style={{ filter: 'brightness(0.48)', pointerEvents: 'none' }}
                      />
                    ))}
                  </Pie>
                ))}
            <Pie
              data={itens}
              dataKey="leads"
              nameKey="label"
              innerRadius="68%"
              outerRadius="100%"
              cy={profundidade === '3d' ? '46%' : '50%'}
              paddingAngle={itens.length > 1 ? 2 : 0}
              stroke={TINTA.superficie}
              strokeWidth={2}
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
              onMouseEnter={(_: unknown, i: number) => setAtivo(itens[i].chave)}
              onMouseLeave={() => setAtivo(null)}
              onClick={(_: unknown, i: number) => onSelecionar?.(itens[i])}
            >
              {itens.map((g) => (
                <Cell
                  key={g.chave}
                  className={profundidade === '3d' ? 'pie-3d-face' : undefined}
                  fill={GRUPO_COR[g.chave as Grupo] ?? NEUTRO}
                  opacity={ativo && ativo !== g.chave ? 0.35 : 1}
                  style={{ cursor: onSelecionar ? 'pointer' : 'default', outline: 'none' }}
                />
              ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div
            className={`pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center transition-transform ${
              profundidade === '3d' ? '-translate-y-1.5' : ''
            }`}
          >
            <span className="text-2xl font-semibold text-slate-50">{destaque ? pct(destaque.pct_leads) : numero(total)}</span>
            <span className="max-w-[96px] text-[10px] leading-tight text-slate-400">{destaque ? destaque.label : 'leads'}</span>
          </div>
        </div>
        <ul className="space-y-2">
          {itens.map((g) => (
            <li key={g.chave}>
              <button
                type="button"
                onClick={() => onSelecionar?.(g)}
                onMouseEnter={() => setAtivo(g.chave)}
                onMouseLeave={() => setAtivo(null)}
                className={`w-full rounded-lg px-2 py-1.5 text-left transition-colors ${ativo === g.chave ? 'bg-slate-800/70' : 'hover:bg-slate-800/40'}`}
              >
                <span className="flex items-center justify-between gap-3 text-xs">
                  <span className="inline-flex items-center gap-2 text-slate-200">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: GRUPO_COR[g.chave as Grupo] ?? NEUTRO }} aria-hidden />
                    {g.label}
                  </span>
                  <span className="font-semibold tabular-nums text-slate-100">
                    {numero(g.leads)} <span className="font-normal text-slate-500">· {pct(g.pct_leads)}</span>
                  </span>
                </span>
                <span className="mt-1 block h-1.5 rounded-full bg-slate-800">
                  <span className="block h-full rounded-full" style={{ width: `${g.pct_leads ?? 0}%`, background: GRUPO_COR[g.chave as Grupo] ?? NEUTRO }} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Plataforma × CRM por dia (mesma unidade, um eixo): diário ou acumulado
// ---------------------------------------------------------------------------

type TipoPlataforma = 'diario' | 'acumulado';
const TIPOS_PLATAFORMA: OpcaoTipo<TipoPlataforma>[] = [
  { id: 'diario', label: 'Por dia', icone: IconeLinhas },
  { id: 'acumulado', label: 'Acumulado', icone: TrendingUp },
];

export function PlataformaCrmChart({
  serie,
  labelPlataforma,
  modo,
}: {
  serie: { data: string; leads_plataforma: number; leads_crm: number }[];
  labelPlataforma: string;
  modo: 'grafico' | 'tabela';
}) {
  const [tipo, setTipo] = useState<TipoPlataforma>('diario');
  const dados = useMemo(() => {
    let somaPlataforma = 0;
    let somaCrm = 0;
    return serie.map((d) => {
      somaPlataforma += d.leads_plataforma;
      somaCrm += d.leads_crm;
      return { ...d, rotulo: `${d.data.slice(8, 10)}/${d.data.slice(5, 7)}`, acum_plataforma: somaPlataforma, acum_crm: somaCrm };
    });
  }, [serie]);
  const totalPlataforma = dados.length ? dados[dados.length - 1].acum_plataforma : 0;
  const totalCrm = dados.length ? dados[dados.length - 1].acum_crm : 0;

  if (modo === 'tabela') {
    return (
      <div className="overflow-x-auto max-h-80">
        <table className="tabela">
          <thead>
            <tr>
              <th>Dia</th>
              <th className="text-right">Segundo {labelPlataforma}</th>
              <th className="text-right">Chegaram no CV</th>
              <th className="text-right">Diferença</th>
            </tr>
          </thead>
          <tbody>
            {dados.map((d) => (
              <tr key={d.data}>
                <td>{d.rotulo}</td>
                <td className="num">{numero(d.leads_plataforma)}</td>
                <td className="num">{numero(d.leads_crm)}</td>
                <td className="num">{numero(d.leads_crm - d.leads_plataforma)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const chavePlataforma = tipo === 'diario' ? 'leads_plataforma' : 'acum_plataforma';
  const chaveCrm = tipo === 'diario' ? 'leads_crm' : 'acum_crm';
  return (
    <>
      <Resumo
        itens={[
          { rotulo: `Segundo ${labelPlataforma}`, valor: numero(totalPlataforma) },
          { rotulo: 'Chegaram no CV', valor: numero(totalCrm), detalhe: totalPlataforma ? pct((totalCrm / totalPlataforma) * 100) : undefined },
          { rotulo: 'Diferença', valor: numero(totalCrm - totalPlataforma) },
        ]}
        acao={<TiposGrafico opcoes={TIPOS_PLATAFORMA} valor={tipo} onChange={setTipo} />}
      />
      <Legenda
        itens={[
          { cor: SERIES.s1, label: `Leads segundo ${labelPlataforma}` },
          { cor: SERIES.s2, label: 'Leads que chegaram no CV' },
        ]}
      />
      {!dados.length ? (
        semDados
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={dados} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="grad-plataforma" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={SERIES.s1} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={SERIES.s1} stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke={TINTA.grade} />
              <XAxis dataKey="rotulo" tick={eixo} axisLine={{ stroke: TINTA.eixo }} tickLine={false} minTickGap={16} />
              <YAxis tick={eixo} axisLine={false} tickLine={false} allowDecimals={false} width={40} />
              <Tooltip
                cursor={{ stroke: TINTA.eixo }}
                content={({ active, payload }: any) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  const p = d[chavePlataforma];
                  const c = d[chaveCrm];
                  return (
                    <CaixaTooltip
                      titulo={tipo === 'diario' ? d.rotulo : `Até ${d.rotulo}`}
                      linhas={[
                        { cor: SERIES.s1, label: labelPlataforma, valor: numero(p) },
                        { cor: SERIES.s2, label: 'CV', valor: numero(c) },
                      ]}
                      rodape={p ? `${pct((c / p) * 100)} chegaram · diferença ${numero(c - p)}` : undefined}
                    />
                  );
                }}
              />
              <Area type="monotone" dataKey={chavePlataforma} stroke={SERIES.s1} strokeWidth={2} fill="url(#grad-plataforma)" activeDot={{ r: 4, stroke: TINTA.superficie, strokeWidth: 2 }} isAnimationActive={false} />
              <Area type="monotone" dataKey={chaveCrm} stroke={SERIES.s2} strokeWidth={2} fill="transparent" activeDot={{ r: 4, stroke: TINTA.superficie, strokeWidth: 2 }} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </>
  );
}
