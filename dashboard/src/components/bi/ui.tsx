'use client';

import React from 'react';
import { AlertTriangle, BarChart3, Info, Minus, Table2, TrendingDown, TrendingUp, XCircle } from 'lucide-react';
import { CONFIANCA_LABEL } from '../../lib/cores';
import { pct } from '../../lib/format';

export function Card({
  titulo,
  subtitulo,
  acao,
  children,
  className = '',
}: {
  titulo?: React.ReactNode;
  subtitulo?: React.ReactNode;
  acao?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`painel min-w-0 p-5 ${className}`}>
      {(titulo || acao) && (
        <header className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            {titulo && <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>}
            {subtitulo && <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{subtitulo}</p>}
          </div>
          {acao && <div className="shrink-0 flex items-center gap-2">{acao}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function StatTile({
  label,
  valor,
  sub,
  delta,
  subirEBom = true,
  destaque = false,
  alerta,
  onClick,
}: {
  label: string;
  valor: string;
  sub?: React.ReactNode;
  delta?: number | null;
  subirEBom?: boolean;
  destaque?: boolean;
  alerta?: 'atencao' | 'critico';
  onClick?: () => void;
}) {
  const tamanhoValor = destaque
    ? 'text-5xl leading-tight'
    : valor.length >= 11
      ? 'text-2xl leading-tight'
      : valor.length >= 8
        ? 'text-[26px] leading-tight'
        : 'text-[28px] leading-tight';

  const Conteudo = (
    <>
      <div className="flex min-h-12 items-start justify-between gap-2">
        <span className="text-xs leading-4 text-slate-400">{label}</span>
        {alerta && (
          <span
            className={`inline-flex items-center gap-1 text-[10px] font-semibold ${alerta === 'critico' ? 'text-rose-300' : 'text-amber-300'}`}
          >
            {alerta === 'critico' ? <XCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
            {alerta === 'critico' ? 'Crítico' : 'Atenção'}
          </span>
        )}
      </div>
      <div className={`mt-1 whitespace-nowrap font-semibold text-slate-50 ${tamanhoValor}`}>{valor}</div>
      <div className="mt-1 flex items-center gap-2 flex-wrap text-xs">
        {delta !== undefined && <Delta valor={delta} subirEBom={subirEBom} />}
        {sub && <span className="text-slate-400">{sub}</span>}
      </div>
    </>
  );

  const classe = `painel stat-tile flex min-h-[118px] h-full w-full flex-col items-stretch justify-start p-4 text-left ${destaque ? 'md:col-span-2' : ''} ${onClick ? 'hover:border-sky-500/40 cursor-pointer' : ''}`;
  return onClick ? (
    <button onClick={onClick} className={classe}>
      {Conteudo}
    </button>
  ) : (
    <div className={classe}>{Conteudo}</div>
  );
}

export function Delta({ valor, subirEBom = true, sufixo = 'vs período anterior' }: { valor: number | null | undefined; subirEBom?: boolean; sufixo?: string }) {
  if (valor === null || valor === undefined) {
    return <span className="text-slate-500">sem base de comparação</span>;
  }
  if (valor === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-slate-400">
        <Minus className="w-3 h-3" /> estável {sufixo}
      </span>
    );
  }
  const subiu = valor > 0;
  const bom = subiu === subirEBom;
  return (
    <span className={`inline-flex items-center gap-1 font-medium ${bom ? 'text-emerald-400' : 'text-rose-400'}`}>
      {subiu ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {subiu ? '+' : ''}
      {pct(valor)} <span className="text-slate-500 font-normal">{sufixo}</span>
    </span>
  );
}

export function AlternarVisao({ modo, setModo }: { modo: 'grafico' | 'tabela'; setModo: (m: 'grafico' | 'tabela') => void }) {
  return (
    <div className="inline-flex rounded-lg border border-slate-700 overflow-hidden text-[11px]" role="group" aria-label="Alternar visão">
      <button
        onClick={() => setModo('grafico')}
        className={`px-2 py-1 inline-flex items-center gap-1 ${modo === 'grafico' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'}`}
        aria-pressed={modo === 'grafico'}
      >
        <BarChart3 className="w-3 h-3" /> Gráfico
      </button>
      <button
        onClick={() => setModo('tabela')}
        className={`px-2 py-1 inline-flex items-center gap-1 ${modo === 'tabela' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'}`}
        aria-pressed={modo === 'tabela'}
      >
        <Table2 className="w-3 h-3" /> Tabela
      </button>
    </div>
  );
}

export function Legenda({ itens }: { itens: { cor: string; label: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 mb-3">
      {itens.map((i) => (
        <li key={i.label} className="inline-flex items-center gap-1.5 text-xs text-slate-300">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: i.cor }} aria-hidden />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

export function Aviso({ children, tipo = 'info' }: { children: React.ReactNode; tipo?: 'info' | 'atencao' }) {
  return (
    <div
      className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-xs leading-relaxed ${
        tipo === 'atencao' ? 'border-amber-500/30 bg-amber-500/5 text-amber-100' : 'border-slate-700 bg-slate-800/40 text-slate-300'
      }`}
    >
      {tipo === 'atencao' ? (
        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-400" />
      ) : (
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0 text-sky-400" />
      )}
      <div>{children}</div>
    </div>
  );
}

const CONFIANCA_COR: Record<string, string> = {
  alta: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
  media: 'text-sky-300 border-sky-500/30 bg-sky-500/10',
  baixa: 'text-amber-300 border-amber-500/30 bg-amber-500/10',
  nenhuma: 'text-slate-300 border-slate-600 bg-slate-700/30',
};

export function BadgeConfianca({ confianca }: { confianca: string }) {
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded border text-[10px] font-medium whitespace-nowrap ${CONFIANCA_COR[confianca] ?? CONFIANCA_COR.nenhuma}`}>
      {CONFIANCA_LABEL[confianca] ?? confianca}
    </span>
  );
}

/** Barra de proporção (medidor) com trilho da mesma cor, mais claro. */
export function Medidor({ valor, cor = '#3987e5' }: { valor: number | null; cor?: string }) {
  const largura = Math.max(0, Math.min(100, valor ?? 0));
  return (
    <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ background: `${cor}33` }} aria-hidden>
      <div className="h-full rounded-full" style={{ width: `${largura}%`, background: cor }} />
    </div>
  );
}

export function Vazio({ titulo, texto, acao }: { titulo: string; texto?: React.ReactNode; acao?: React.ReactNode }) {
  return (
    <div className="painel p-10 text-center">
      <p className="text-sm font-semibold text-slate-200">{titulo}</p>
      {texto && <div className="text-xs text-slate-400 mt-2 max-w-xl mx-auto leading-relaxed">{texto}</div>}
      {acao && <div className="mt-4">{acao}</div>}
    </div>
  );
}

export function ErroCarga({ mensagem, onTentar }: { mensagem: string; onTentar?: () => void }) {
  return (
    <div className="painel p-6 border-rose-500/30">
      <p className="text-sm font-semibold text-rose-300">Não foi possível carregar os dados</p>
      <p className="text-xs text-slate-400 mt-1">{mensagem}</p>
      {onTentar && (
        <button onClick={onTentar} className="botao-secundario mt-3">
          Tentar de novo
        </button>
      )}
    </div>
  );
}
