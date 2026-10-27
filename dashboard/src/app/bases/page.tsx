'use client';

import React, { Suspense, useEffect, useRef, useState } from 'react';
import { CheckCircle2, ExternalLink, Loader2, MinusCircle, RefreshCw, Wrench, XCircle } from 'lucide-react';
import { AppShell } from '../../components/bi/AppShell';
import { Aviso, Card, ErroCarga } from '../../components/bi/ui';
import { atualizarBases, fetchBases } from '../../lib/biApi';
import { dataHora, idade, numero } from '../../lib/format';
import { BaseInfo, EstadoAtualizacao } from '../../types/bi';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Bases e integrações" subtitulo="Cada fonte de dados, quando foi atualizada e o link para resolver o que falta" semFiltros>
        <Bases />
      </AppShell>
    </Suspense>
  );
}

const MODO: Record<string, { label: string; classe: string; icone: React.ReactNode }> = {
  real: { label: 'Funcionando', classe: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10', icone: <CheckCircle2 className="w-3.5 h-3.5" /> },
  erro: { label: 'Com erro', classe: 'text-rose-300 border-rose-500/30 bg-rose-500/10', icone: <XCircle className="w-3.5 h-3.5" /> },
  nao_configurado: { label: 'Não configurada', classe: 'text-slate-300 border-slate-600 bg-slate-700/30', icone: <MinusCircle className="w-3.5 h-3.5" /> },
  simulado: { label: 'Simulada', classe: 'text-fuchsia-300 border-fuchsia-500/30 bg-fuchsia-500/10', icone: <MinusCircle className="w-3.5 h-3.5" /> },
};

function Bases() {
  const [bases, setBases] = useState<BaseInfo[] | null>(null);
  const [estado, setEstado] = useState<EstadoAtualizacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function carregar() {
    try {
      const r = await fetchBases();
      setBases(r.bases);
      setEstado(r.atualizacao);
      setErro(null);
      return r.atualizacao;
    } catch (e: any) {
      setErro(e.message);
      return null;
    }
  }

  function acompanhar() {
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(async () => {
      const est = await carregar();
      if (est && !est.em_andamento && timer.current) clearInterval(timer.current);
    }, 3000);
  }

  useEffect(() => {
    carregar().then((est) => est?.em_andamento && acompanhar());
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function atualizar(lista?: string[]) {
    try {
      const r = await atualizarBases(lista);
      setEstado({ ...r, em_andamento: true });
      acompanhar();
    } catch (e: any) {
      setErro(e.message);
    }
  }

  if (erro && !bases) return <ErroCarga mensagem={erro} onTentar={carregar} />;
  if (!bases) return <p className="text-xs text-slate-400">Carregando bases...</p>;

  const funcionando = bases.filter((b) => b.status.mode === 'real').length;
  const rodando = !!estado?.em_andamento;

  return (
    <div className="space-y-5">
      <div className="painel p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-white">
            {funcionando} de {bases.length} bases com dados reais
          </p>
          <p className="text-xs text-slate-400 mt-0.5">
            As bases se atualizam sozinhas a cada hora enquanto a engine está rodando. A base de leads do CV leva cerca de 2 minutos.
          </p>
        </div>
        <button onClick={() => atualizar()} disabled={rodando} className="botao-primario">
          {rodando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          {rodando ? `Atualizando: ${estado?.base_atual ?? '...'}` : 'Atualizar todas agora'}
        </button>
      </div>

      {rodando && estado?.fila?.length ? (
        <Aviso>
          Na fila: {estado.fila.map((f) => bases.find((b) => b.base === f)?.label ?? f).join(' · ')}. Pode continuar usando o painel — os
          números mudam quando a atualização terminar.
        </Aviso>
      ) : null}

      <div className="grid md:grid-cols-2 gap-4">
        {bases.map((b) => {
          const m = MODO[b.status.mode] ?? MODO.erro;
          return (
            <Card
              key={b.base}
              titulo={b.label}
              subtitulo={b.descricao}
              acao={
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium ${m.classe}`}>
                  {m.icone}
                  {m.label}
                </span>
              }
            >
              <dl className="grid grid-cols-3 gap-3 text-xs mb-3">
                <div>
                  <dt className="text-slate-500">Registros</dt>
                  <dd className="text-slate-100 font-semibold tabular-nums">{numero(b.total)}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Dados de</dt>
                  <dd className="text-slate-200">{b.dados_de ? dataHora(b.dados_de) : '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Idade</dt>
                  <dd className="text-slate-200">{idade(b.idade_horas)}</dd>
                </div>
              </dl>
              <p className="text-xs text-slate-400 leading-relaxed break-words">{b.status.message}</p>
              {b.status.mode !== 'real' && b.status.action && (
                <div className="mt-3 flex items-start gap-2 text-xs text-amber-100 bg-amber-500/5 border border-amber-500/20 rounded-xl p-3">
                  <Wrench className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-400" />
                  <span className="leading-relaxed">{b.status.action}</span>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2 items-center">
                {b.status.mode !== 'real' &&
                  b.status.help_links.map((l) => (
                    <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="botao-secundario">
                      {l.label} <ExternalLink className="w-3 h-3" />
                    </a>
                  ))}
                <button onClick={() => atualizar([b.base])} disabled={rodando} className="botao-secundario ml-auto">
                  <RefreshCw className="w-3 h-3" /> Atualizar esta
                </button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
