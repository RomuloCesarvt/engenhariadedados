'use client';

/**
 * CPL real × leads no CV: cada ponto é um anúncio com amostra mínima. As medianas dividem
 * o gráfico em quadrantes; os campeões ficam embaixo à direita (muitos leads, CPL baixo).
 * Um eixo de cada medida, cor só para o quadrante (com legenda) e visão de tabela equivalente.
 */

import React from 'react';
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { AnuncioAuditado } from '../../types/bi';
import { NEUTRO, SERIES, TINTA } from '../../lib/cores';
import { empreendimentoCurto, numero, reais, reaisCentavos } from '../../lib/format';
import { Legenda } from './ui';

const eixo = { fill: TINTA.apagada, fontSize: 11 };
const COR_CAMPEAO = SERIES.s3;
const COR_DEMAIS = SERIES.s1;

export function ehCampeaoCplLeads(a: AnuncioAuditado, medianas: { leads_cv: number | null; cpl_real: number | null }) {
  return medianas.leads_cv !== null && medianas.cpl_real !== null && a.cpl_real !== null && a.leads_cv >= medianas.leads_cv && a.cpl_real <= medianas.cpl_real;
}

function Ponto(props: any) {
  const { cx, cy, fill } = props;
  if (cx === undefined || cy === undefined) return null;
  return <circle cx={cx} cy={cy} r={6} fill={fill} stroke={TINTA.superficie} strokeWidth={2} style={{ cursor: 'pointer' }} />;
}

export function CplLeadsChart({
  anuncios,
  medianas,
  minLeads,
  minInvestimento,
  modo,
  onSelecionar,
}: {
  anuncios: AnuncioAuditado[];
  medianas: { leads_cv: number | null; cpl_real: number | null };
  minLeads: number;
  minInvestimento: number;
  modo: 'grafico' | 'tabela';
  onSelecionar: (a: AnuncioAuditado) => void;
}) {
  const pontos = anuncios.filter((a) => a.cpl_real !== null && a.leads_cv >= minLeads && a.investimento >= minInvestimento);
  const campeoes = pontos.filter((a) => ehCampeaoCplLeads(a, medianas));
  const demais = pontos.filter((a) => !ehCampeaoCplLeads(a, medianas));

  if (pontos.length === 0) {
    return (
      <p className="text-xs text-slate-500 py-8 text-center">
        Nenhum anúncio com {minLeads}+ leads no CV e {reais(minInvestimento)}+ investidos no período.
      </p>
    );
  }

  if (modo === 'tabela') {
    const ordenados = [...pontos].sort((a, b) => (b.eficiencia ?? 0) - (a.eficiencia ?? 0));
    return (
      <div className="overflow-x-auto max-h-80">
        <table className="tabela">
          <thead>
            <tr>
              <th>Anúncio</th>
              <th className="text-right">Leads no CV</th>
              <th className="text-right">CPL real</th>
              <th className="text-right">Investimento</th>
              <th>Quadrante</th>
            </tr>
          </thead>
          <tbody>
            {ordenados.map((a) => (
              <tr key={a.chave} className="cursor-pointer hover:bg-slate-800/40" onClick={() => onSelecionar(a)}>
                <td className="max-w-[260px] truncate" title={a.anuncio}>
                  {a.anuncio}
                </td>
                <td className="num">{numero(a.leads_cv)}</td>
                <td className="num">{reaisCentavos(a.cpl_real)}</td>
                <td className="num">{reais(a.investimento)}</td>
                <td className="text-slate-400">{ehCampeaoCplLeads(a, medianas) ? 'Muitos leads e CPL baixo' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <>
      <Legenda
        itens={[
          { cor: COR_CAMPEAO, label: `Muitos leads e CPL baixo (${campeoes.length})` },
          { cor: COR_DEMAIS, label: `Demais anúncios (${demais.length})` },
        ]}
      />
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 12, right: 24, left: 8, bottom: 20 }}>
            <CartesianGrid stroke={TINTA.grade} />
            <XAxis
              type="number"
              dataKey="leads_cv"
              name="Leads no CV"
              tick={eixo}
              axisLine={{ stroke: TINTA.eixo }}
              tickLine={false}
              allowDecimals={false}
              label={{ value: 'Leads que chegaram ao CV', position: 'insideBottom', offset: -12, fill: TINTA.apagada, fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="cpl_real"
              name="CPL real"
              tick={eixo}
              axisLine={false}
              tickLine={false}
              width={64}
              tickFormatter={(v) => reais(v)}
              label={{ value: 'CPL real', angle: -90, position: 'insideLeft', fill: TINTA.apagada, fontSize: 11, offset: 0 }}
            />
            <ZAxis range={[60, 60]} />
            {medianas.leads_cv !== null && (
              <ReferenceLine x={medianas.leads_cv} stroke={NEUTRO} strokeDasharray="4 4" label={{ value: 'mediana de leads', fill: TINTA.apagada, fontSize: 10, position: 'top' }} />
            )}
            {medianas.cpl_real !== null && (
              <ReferenceLine y={medianas.cpl_real} stroke={NEUTRO} strokeDasharray="4 4" label={{ value: 'mediana de CPL', fill: TINTA.apagada, fontSize: 10, position: 'right' }} />
            )}
            <Tooltip
              cursor={{ strokeDasharray: '3 3', stroke: TINTA.eixo }}
              content={({ active, payload }: any) => {
                if (!active || !payload?.length) return null;
                const a: AnuncioAuditado = payload[0].payload;
                return (
                  <div className="rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 shadow-xl text-xs max-w-[300px]">
                    <p className="text-slate-100 font-semibold truncate">{a.anuncio}</p>
                    <p className="text-slate-500 truncate mb-1.5">
                      {a.conjunto ?? '—'} · {empreendimentoCurto(a.empreendimento)}
                    </p>
                    {[
                      ['Leads no CV', numero(a.leads_cv)],
                      ['CPL real', reaisCentavos(a.cpl_real)],
                      ['Investimento', reais(a.investimento)],
                      ['Vendas', numero(a.vendas)],
                    ].map(([rotulo, valor]) => (
                      <div key={rotulo} className="flex justify-between gap-4 py-0.5">
                        <span className="text-slate-400">{rotulo}</span>
                        <span className="font-semibold text-slate-100 tabular-nums">{valor}</span>
                      </div>
                    ))}
                    <p className="text-slate-500 border-t border-slate-700 mt-1.5 pt-1.5">Clique para ver os leads</p>
                  </div>
                );
              }}
            />
            <Scatter data={demais} fill={COR_DEMAIS} shape={<Ponto />} onClick={(p: any) => onSelecionar(p?.payload ?? p)} isAnimationActive={false} />
            <Scatter data={campeoes} fill={COR_CAMPEAO} shape={<Ponto />} onClick={(p: any) => onSelecionar(p?.payload ?? p)} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[11px] text-slate-500 mt-1">
        Só anúncios com {minLeads}+ leads no CV e {reais(minInvestimento)}+ investidos. Embaixo à direita das linhas: mais leads que a mediana e CPL
        abaixo da mediana.
      </p>
    </>
  );
}
