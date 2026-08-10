'use client';

import React, { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  MinusCircle,
  FlaskConical,
  ExternalLink,
  RefreshCw,
  Loader2,
  Wrench,
} from 'lucide-react';
import { SourceMode, SourceStatus } from '../types';
import { fetchIntegrations } from '../lib/dataService';

/** Fontes que complementam a análise mas não são necessárias para ela funcionar. */
const OPTIONAL_SOURCES = new Set(['sheets_bi', 'firebase']);

const modeStyle: Record<SourceMode, { label: string; text: string; bg: string; border: string; icon: React.ReactNode }> = {
  real: {
    label: 'Funcionando',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
  erro: {
    label: 'Com erro',
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/20',
    icon: <XCircle className="w-4 h-4" />,
  },
  nao_configurado: {
    label: 'Não configurado',
    text: 'text-slate-300',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/20',
    icon: <MinusCircle className="w-4 h-4" />,
  },
  simulado: {
    label: 'Dados simulados',
    text: 'text-fuchsia-300',
    bg: 'bg-fuchsia-500/10',
    border: 'border-fuchsia-500/20',
    icon: <FlaskConical className="w-4 h-4" />,
  },
};

/** Integrações que impedem a análise de refletir a realidade. */
export function sourcesNeedingAttention(sources?: SourceStatus[] | null): SourceStatus[] {
  return (sources ?? []).filter(
    (s) => s.mode === 'erro' || s.mode === 'simulado' || (s.mode === 'nao_configurado' && !OPTIONAL_SOURCES.has(s.source))
  );
}

export const IntegrationsPanel: React.FC<{ initialSources: SourceStatus[]; executionId?: string }> = ({
  initialSources,
  executionId,
}) => {
  const [sources, setSources] = useState<SourceStatus[]>(initialSources);
  const [origin, setOrigin] = useState<'last_report' | 'live'>('last_report');
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function checkNow() {
    setChecking(true);
    setError(null);
    try {
      const res = await fetchIntegrations(true);
      setSources(res.sources);
      setOrigin('live');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setChecking(false);
    }
  }

  const attention = sourcesNeedingAttention(sources);
  const working = sources.filter((s) => s.mode === 'real');
  const optional = sources.filter((s) => s.mode === 'nao_configurado' && OPTIONAL_SOURCES.has(s.source));
  const essenciais = sources.filter((s) => !OPTIONAL_SOURCES.has(s.source));
  const essenciaisReais = essenciais.filter((s) => s.mode === 'real');

  return (
    <div className="space-y-6">
      <div className="card p-5 flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-sm font-bold text-white">
            {essenciaisReais.length} de {essenciais.length} integrações essenciais com dados reais
          </p>
          <p className="text-[11px] text-slate-500 mt-0.5">
            {origin === 'live'
              ? 'Verificado agora, direto em cada API.'
              : sources.length
              ? `Estado registrado na última análise${executionId ? ` (${executionId})` : ''}.`
              : 'Nenhuma análise registrada ainda — teste as integrações agora.'}
          </p>
        </div>
        <button
          onClick={checkNow}
          disabled={checking}
          className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors disabled:opacity-60"
        >
          {checking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          <span>{checking ? 'Testando cada API...' : 'Testar integrações agora'}</span>
        </button>
      </div>

      {error && (
        <p className="text-xs text-rose-300 bg-rose-500/5 border border-rose-500/20 rounded-xl p-3">{error}</p>
      )}

      {attention.length > 0 && (
        <Section title={`Precisa de ação (${attention.length})`}>
          {attention.map((s) => (
            <SourceCard key={s.source} source={s} />
          ))}
        </Section>
      )}

      {working.length > 0 && (
        <Section title={`Funcionando (${working.length})`}>
          {working.map((s) => (
            <SourceCard key={s.source} source={s} />
          ))}
        </Section>
      )}

      {optional.length > 0 && (
        <Section title="Opcionais">
          {optional.map((s) => (
            <SourceCard key={s.source} source={s} />
          ))}
        </Section>
      )}
    </div>
  );
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-3">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function SourceCard({ source }: { source: SourceStatus }) {
  const style = modeStyle[source.mode] ?? modeStyle.erro;
  const showHelp = source.mode !== 'real';

  return (
    <div className={`rounded-2xl border ${style.border} bg-slate-900/60 p-5`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <p className="text-sm font-bold text-white">{source.label}</p>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed break-words">{source.message}</p>
        </div>
        <span
          className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border shrink-0 ${style.text} ${style.bg} ${style.border}`}
        >
          {style.icon}
          <span>{style.label}</span>
          {source.mode === 'real' && <span className="text-slate-400 font-medium">· {source.records}</span>}
        </span>
      </div>

      {showHelp && source.action && (
        <div className="mt-3 flex items-start space-x-2 text-xs text-amber-200 bg-amber-500/5 border border-amber-500/20 rounded-xl p-3">
          <Wrench className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-400" />
          <span className="leading-relaxed">{source.action}</span>
        </div>
      )}

      {showHelp && source.help_links.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {source.help_links.map((link) => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-300 hover:bg-sky-500/20 hover:text-sky-200 text-[11px] font-semibold transition-colors"
            >
              <span>{link.label}</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
