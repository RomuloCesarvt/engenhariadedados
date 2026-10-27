'use client';

import React, { Suspense, useMemo, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, CheckCircle2, ExternalLink, Info, Wrench, XCircle } from 'lucide-react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { Card, ErroCarga, StatTile } from '../../components/bi/ui';
import { fetchDiagnosticos, resolverDiagnostico } from '../../lib/biApi';
import { data, dataHora, numero } from '../../lib/format';
import { CorrecaoSistema, Diagnostico } from '../../types/bi';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Diagnósticos" subtitulo="Tudo o que pode deixar um número errado: o quê, por quê, período, situação e como resolver">
        <Diagnosticos />
      </AppShell>
    </Suspense>
  );
}

const SEVERIDADE = {
  critico: { label: 'Crítico', icone: XCircle, classe: 'text-rose-300 border-rose-500/40 bg-rose-500/10' },
  atencao: { label: 'Atenção', icone: AlertTriangle, classe: 'text-amber-300 border-amber-500/40 bg-amber-500/10' },
  info: { label: 'Informativo', icone: Info, classe: 'text-sky-300 border-sky-500/40 bg-sky-500/10' },
} as const;

type Aba = 'pendente' | 'resolvido' | 'todos';

function Diagnosticos() {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchDiagnosticos(filtros), [chave, versao]);
  const [aba, setAba] = useState<Aba>('pendente');
  const [categoria, setCategoria] = useState<string | null>(null);

  const categorias = useMemo(() => {
    const mapa = new Map<string, string>();
    (dados?.itens ?? []).forEach((i) => mapa.set(i.categoria, i.categoria_label));
    return Array.from(mapa.entries());
  }, [dados]);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Verificando os dados...</p>;

  const r = dados.resumo;
  const visiveis = dados.itens.filter(
    (i) => (aba === 'todos' || i.situacao === aba) && (!categoria || i.categoria === categoria)
  );

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile
          destaque
          label="Pendentes críticos"
          valor={numero(r.pendentes_criticos)}
          sub="podem estar deixando números errados agora"
          alerta={r.pendentes_criticos ? 'critico' : undefined}
          onClick={() => setAba('pendente')}
        />
        <StatTile
          label="Pendentes de atenção"
          valor={numero(r.pendentes_atencao)}
          sub="afetam parte das análises"
          alerta={r.pendentes_atencao ? 'atencao' : undefined}
          onClick={() => setAba('pendente')}
        />
        <StatTile label="Resolvidos" valor={numero(r.resolvidos)} sub="com data e motivo" onClick={() => setAba('resolvido')} />
        <StatTile label="Informativos pendentes" valor={numero(r.pendentes_info)} sub="sem impacto direto nos números" />
      </div>

      <p className="text-[11px] text-slate-500">
        Mostrando os problemas que afetam o período filtrado, além dos que valem para o sistema todo (bases, conexões e regras).
        Verificado em {dataHora(dados.calculado_em)}. A situação muda sozinha quando os dados mostram que o problema parou.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {(['pendente', 'resolvido', 'todos'] as Aba[]).map((a) => (
          <button
            key={a}
            onClick={() => setAba(a)}
            aria-pressed={aba === a}
            className={`px-3 py-1.5 rounded-md text-xs font-medium ${aba === a ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200 bg-slate-800/60'}`}
          >
            {a === 'pendente'
              ? `Pendentes (${numero(dados.itens.filter((i) => i.situacao === 'pendente').length)})`
              : a === 'resolvido'
              ? `Resolvidos (${numero(r.resolvidos)})`
              : `Todos (${numero(r.total)})`}
          </button>
        ))}
        <span className="w-px h-5 bg-slate-700 mx-1" />
        <button
          onClick={() => setCategoria(null)}
          className={`px-2.5 py-1 rounded-full text-[11px] border ${!categoria ? 'border-sky-500 text-sky-200' : 'border-slate-700 text-slate-400'}`}
        >
          Todas as categorias
        </button>
        {categorias.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setCategoria(id)}
            className={`px-2.5 py-1 rounded-full text-[11px] border ${categoria === id ? 'border-sky-500 text-sky-200' : 'border-slate-700 text-slate-400'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {visiveis.length === 0 ? (
        <div className="painel p-8 text-center">
          <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
          <p className="text-sm text-slate-200">
            {aba === 'pendente' ? 'Nenhum problema pendente neste recorte.' : 'Nada para mostrar neste recorte.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visiveis.map((d) => (
            <CartaoDiagnostico key={d.id} d={d} onResolvido={recarregar} />
          ))}
        </div>
      )}

      <Correcoes correcoes={dados.correcoes} />
    </div>
  );
}

function CartaoDiagnostico({ d, onResolvido }: { d: Diagnostico; onResolvido: () => void }) {
  const sev = SEVERIDADE[d.severidade] ?? SEVERIDADE.info;
  const Icone = sev.icone;
  const resolvido = d.situacao === 'resolvido';
  return (
    <div className={`painel p-4 border-l-4 ${resolvido ? 'border-l-emerald-500/60' : d.severidade === 'critico' ? 'border-l-rose-500' : d.severidade === 'atencao' ? 'border-l-amber-500' : 'border-l-sky-500'}`}>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {resolvido ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full border text-emerald-300 border-emerald-500/40 bg-emerald-500/10">
            <CheckCircle2 className="w-3 h-3" /> Resolvido{d.resolvido_em ? ` em ${data(d.resolvido_em)}` : ''}
          </span>
        ) : (
          <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full border ${sev.classe}`}>
            <Icone className="w-3 h-3" /> Pendente · {sev.label}
          </span>
        )}
        <span className="text-[11px] text-slate-500">{d.categoria_label}</span>
        {d.periodo?.inicio && (
          <span className="text-[11px] text-slate-400">
            · Período afetado: {data(d.periodo.inicio)}
            {d.periodo.fim && d.periodo.fim !== d.periodo.inicio ? ` a ${data(d.periodo.fim)}` : ''}
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-white mb-3">{d.titulo}</h3>

      <div className="grid md:grid-cols-2 gap-4 text-xs leading-relaxed">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">O que aconteceu</p>
          <p className="text-slate-200">{d.o_que}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Por quê</p>
          <p className="text-slate-300">{d.por_que}</p>
        </div>
      </div>

      {d.evidencias.length > 0 && (
        <dl className="mt-3 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
          {d.evidencias.map((e) => (
            <div key={e.rotulo} className="rounded-md bg-slate-800/50 px-2 py-1.5">
              <dt className="text-[10px] text-slate-500 truncate" title={e.rotulo}>
                {e.rotulo}
              </dt>
              <dd className="text-[11px] text-slate-200 truncate" title={e.valor}>
                {e.valor}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-3 grid md:grid-cols-2 gap-4 text-xs">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">{resolvido ? 'Se voltar a acontecer' : 'Como resolver'}</p>
          <ol className="list-decimal list-inside space-y-1 text-slate-300">
            {d.como_resolver.map((passo) => (
              <li key={passo}>{passo}</li>
            ))}
          </ol>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Situação</p>
          <p className={resolvido ? 'text-emerald-200' : 'text-slate-300'}>{d.situacao_motivo}</p>
          {d.primeira_deteccao && <p className="text-[11px] text-slate-500 mt-1">Detectado pela primeira vez em {dataHora(d.primeira_deteccao)}.</p>}
          {d.links.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {d.links.map((l) =>
                l.interno ? (
                  <Link key={l.url} href={l.url} className="botao-secundario !py-1 !px-2 text-[11px]">
                    {l.label}
                  </Link>
                ) : (
                  <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="botao-secundario !py-1 !px-2 text-[11px] inline-flex items-center gap-1">
                    {l.label} <ExternalLink className="w-3 h-3" />
                  </a>
                )
              )}
            </div>
          )}
          {!resolvido && d.resolucao_manual && <ResolverManual id={d.id} onResolvido={onResolvido} />}
        </div>
      </div>
    </div>
  );
}

function ResolverManual({ id, onResolvido }: { id: string; onResolvido: () => void }) {
  const [nota, setNota] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <input
        value={nota}
        onChange={(e) => setNota(e.target.value)}
        placeholder="O que foi feito (opcional)"
        className="controle text-xs flex-1 min-w-[180px] bg-transparent outline-none text-slate-200 placeholder:text-slate-600"
      />
      <button
        disabled={enviando}
        onClick={async () => {
          setEnviando(true);
          setErro(null);
          try {
            await resolverDiagnostico(id, nota);
            onResolvido();
          } catch (e) {
            setErro((e as Error).message);
          } finally {
            setEnviando(false);
          }
        }}
        className="botao-primario !py-1 !px-2 text-[11px]"
      >
        {enviando ? 'Salvando...' : 'Marcar como resolvido'}
      </button>
      {erro && <span className="text-[11px] text-rose-300">{erro}</span>}
    </div>
  );
}

function Correcoes({ correcoes }: { correcoes: CorrecaoSistema[] }) {
  const [aberto, setAberto] = useState(false);
  return (
    <Card
      titulo="Correções feitas no sistema"
      subtitulo="Erros de cálculo já encontrados e corrigidos: o que era, por quê e como foi resolvido"
      acao={
        <button onClick={() => setAberto((a) => !a)} className="botao-secundario text-xs">
          {aberto ? 'Recolher' : `Ver as ${numero(correcoes.length)} correções`}
        </button>
      }
    >
      {!aberto ? (
        <p className="text-xs text-slate-400">
          {numero(correcoes.length)} correções registradas. Todas resolvidas, com o impacto nos números.
        </p>
      ) : (
        <div className="space-y-3">
          {correcoes.map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-800 p-3">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full border text-emerald-300 border-emerald-500/40 bg-emerald-500/10">
                  <Wrench className="w-3 h-3" /> Corrigido em {data(c.data)}
                </span>
                <span className="text-sm font-semibold text-white">{c.titulo}</span>
              </div>
              <div className="grid md:grid-cols-3 gap-3 text-xs leading-relaxed mt-2">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">O que era</p>
                  <p className="text-slate-300">{c.o_que}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Por quê</p>
                  <p className="text-slate-300">{c.por_que}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Como foi resolvido</p>
                  <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                    {c.como_foi_resolvido.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                  <p className="text-emerald-200 mt-1">{c.impacto}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
