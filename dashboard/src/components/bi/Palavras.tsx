'use client';

/**
 * As palavras que trazem gente, em dois quadros:
 *
 *  1. as melhores palavras-chave dos anúncios do Google em cada empreendimento — melhor é a que
 *     converte mais barato; as que só gastam aparecem à parte;
 *  2. as palavras mais buscadas de cada praça, segundo o Google Analytics (palavra do Google Ads
 *     ou utm_term; a busca orgânica do Google não tem palavra no GA4).
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { Search, TrendingDown } from 'lucide-react';
import { useDados } from './useFiltros';
import { Card, ErroCarga, Vazio } from './ui';
import { fetchPalavras } from '../../lib/biApi';
import { empreendimentoCurto, numero, pct, reais, reaisCentavos, reaisCompacto } from '../../lib/format';
import { EmpreendimentoPalavras, Filtros, PalavrasResposta, PracaPalavras } from '../../types/bi';

const num = 'py-1.5 px-2 text-right tabular-nums text-slate-300 whitespace-nowrap';

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

/** "2026-09" -> "set/26". */
function mesCurto(mes: string) {
  const [ano, m] = mes.split('-');
  return `${MESES[Number(m) - 1] ?? m}/${ano.slice(2)}`;
}

export function Palavras({ filtros, chave, versao }: { filtros: Filtros; chave: string; versao?: number }) {
  const { dados, erro, recarregar } = useDados(() => fetchPalavras(filtros), [chave, versao]);

  if (erro) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return null;

  return (
    <>
      <PalavrasDoGoogle dados={dados} />
      <PalavrasDoAnalytics dados={dados} />
    </>
  );
}

function SemBase({ titulo, subtitulo, vazio, mensagem }: { titulo: string; subtitulo: string; vazio: string; mensagem?: string }) {
  return (
    <Card titulo={titulo} subtitulo={subtitulo}>
      <Vazio
        titulo={vazio}
        texto={mensagem}
        acao={
          <Link href="/bases" className="botao-primario">
            Ir para Bases e integrações
          </Link>
        }
      />
    </Card>
  );
}

function PalavrasDoGoogle({ dados }: { dados: PalavrasResposta }) {
  const bloco = dados.google;
  const lista = bloco?.empreendimentos ?? [];
  if (!lista.length) {
    const conectada = bloco?.base?.status?.mode === 'real';
    return (
      <SemBase
        titulo="Melhores palavras-chave por empreendimento"
        subtitulo="Google Ads"
        vazio={conectada ? 'Nenhuma palavra-chave com impressão no período' : 'O Google Ads ainda não está conectado'}
        mensagem={conectada ? bloco?.observacao : bloco?.base?.status?.message}
      />
    );
  }
  return (
    <Card
      titulo="Melhores palavras-chave por empreendimento"
      subtitulo={`Google Ads · ${numero(lista.reduce((s, e) => s + e.cliques, 0))} cliques e ${reaisCompacto(
        lista.reduce((s, e) => s + e.investimento, 0)
      )} no período`}
    >
      <div className="space-y-3">
        {lista.map((e) => (
          <QuadroEmpreendimento key={`${e.empreendimento}|${e.praca}`} item={e} meses={bloco?.granularidade?.meses_dos_termos ?? []} />
        ))}
      </div>
      <p className="text-[11px] text-slate-500 mt-3">{bloco?.observacao}</p>
      {lista.some((e) => e.termos.length > 0) && (
        <p className="text-[11px] text-slate-500 mt-1">{bloco?.observacao_termos}</p>
      )}
    </Card>
  );
}

function QuadroEmpreendimento({ item, meses }: { item: EmpreendimentoPalavras; meses: string[] }) {
  const [tudo, setTudo] = useState(false);
  const visiveis = tudo ? item.palavras : item.palavras.slice(0, 5);
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
      <header className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
        <h3 className="text-xs font-semibold text-slate-100">
          {item.empreendimento === 'Não identificado' ? (
            <>
              {item.praca}{' '}
              <span className="text-slate-500 font-normal" title="A campanha é da cidade e anuncia mais de um produto">
                · campanha da praça
              </span>
            </>
          ) : (
            <>
              {empreendimentoCurto(item.empreendimento)} <span className="text-slate-500 font-normal">· {item.praca}</span>
            </>
          )}
        </h3>
        <span className="text-[11px] text-slate-500">
          {reais(item.investimento)} · {numero(item.cliques)} cliques · {numero(item.conversoes)} conversões
          {item.custo_por_conversao ? ` · ${reaisCentavos(item.custo_por_conversao)} por conversão` : ''}
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-700">
              {['Palavra-chave', 'Investimento', 'Cliques', 'CTR', 'CPC', 'Conversões', 'Custo/conversão'].map((c, i) => (
                <th key={c} className={`py-1.5 px-2 font-medium ${i === 0 ? 'text-left pl-0' : 'text-right'}`}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visiveis.map((p) => (
              <tr key={p.palavra} className="border-b border-slate-800/60 last:border-0">
                <td className="py-1.5 pr-2 text-slate-200">
                  {p.palavra}
                  <span className="block text-[10px] text-slate-600">
                    {p.correspondencia}
                    {p.campanhas.length ? ` · ${p.campanhas[0]}` : ''}
                  </span>
                </td>
                <td className={num}>{reais(p.investimento)}</td>
                <td className={num}>{numero(p.cliques)}</td>
                <td className={num}>{pct(p.ctr)}</td>
                <td className={num}>{reaisCentavos(p.cpc)}</td>
                <td className={`${num} ${p.conversoes ? 'text-emerald-300 font-semibold' : 'text-slate-500'}`}>{numero(p.conversoes)}</td>
                <td className={num}>{reaisCentavos(p.custo_por_conversao)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {item.palavras.length > 5 && (
        <button onClick={() => setTudo(!tudo)} className="botao-secundario mt-2 text-[11px]">
          {tudo ? 'Mostrar menos' : `Mostrar as ${numero(item.palavras.length)} palavras`}
        </button>
      )}
      {item.termos.length > 0 && <Termos item={item} meses={meses} />}

      {item.sem_conversao.length > 0 && (
        <p className="mt-2 text-[11px] text-amber-300/90 inline-flex items-start gap-1.5">
          <TrendingDown className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>
            Gastam sem converter:{' '}
            {item.sem_conversao.map((p) => `${p.palavra} (${reais(p.investimento)})`).join(' · ')}
          </span>
        </p>
      )}
    </section>
  );
}

/** O que as pessoas digitaram. É o que existe no Performance Max, que não tem palavra-chave. */
function Termos({ item, meses }: { item: EmpreendimentoPalavras; meses: string[] }) {
  const [aberto, setAberto] = useState(false);
  const visiveis = aberto ? item.termos : item.termos.slice(0, 5);
  return (
    <div className="mt-3 pt-3 border-t border-slate-800">
      <h4 className="text-[11px] font-semibold text-slate-300 mb-1.5">
        O que as pessoas digitaram{' '}
        <span className="text-slate-500 font-normal">
          · {item.termos_canais.join(', ') || 'Google Ads'} · {numero(item.termos_cliques)} cliques ·{' '}
          {numero(item.termos_distintos)} termos · período escolhido
        </span>
      </h4>
      <table className="w-full text-xs">
        <tbody>
          {visiveis.map((t) => (
            <tr key={t.termo} className="border-b border-slate-800/60 last:border-0">
              <td className="py-1 pr-2 text-slate-200">{t.termo}</td>
              <td className={num}>{numero(t.impressoes)} impressões</td>
              <td className={num}>{numero(t.cliques)} cliques</td>
              <td className={`${num} ${t.conversoes ? 'text-emerald-300' : 'text-slate-500'}`}>
                {numero(t.conversoes)} conv.
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {item.termos.length > 5 && (
        <button onClick={() => setAberto(!aberto)} className="botao-secundario mt-2 text-[11px]">
          {aberto ? 'Mostrar menos' : `Mostrar os ${numero(item.termos.length)} termos`}
        </button>
      )}
    </div>
  );
}

function PalavrasDoAnalytics({ dados }: { dados: PalavrasResposta }) {
  const bloco = dados.ga4;
  const [aberta, setAberta] = useState<string | null>(null);
  const pracas = bloco?.pracas ?? [];
  if (!pracas.length) {
    const conectada = bloco?.base?.status?.mode === 'real';
    return (
      <SemBase
        titulo="Palavras mais buscadas por praça"
        subtitulo="Google Analytics"
        vazio={conectada ? 'Nenhuma palavra no período' : 'O Google Analytics ainda não está conectado'}
        mensagem={conectada ? bloco?.observacao : bloco?.base?.status?.message}
      />
    );
  }
  return (
    <Card
      titulo="Palavras mais buscadas por praça"
      subtitulo={`Google Analytics · ${numero(pracas.reduce((s, p) => s + p.sessoes, 0))} sessão(ões) com palavra no período`}
    >
      <div className="space-y-3">
        {pracas.map((p) => (
          <QuadroPraca key={p.praca} praca={p} aberta={aberta === p.praca} onAlternar={() => setAberta(aberta === p.praca ? null : p.praca)} />
        ))}
      </div>
      <p className="text-[11px] text-slate-500 mt-3">{bloco?.observacao}</p>
    </Card>
  );
}

function QuadroPraca({ praca, aberta, onAlternar }: { praca: PracaPalavras; aberta: boolean; onAlternar: () => void }) {
  const visiveis = aberta ? praca.palavras : praca.palavras.slice(0, 5);
  const maior = Math.max(1, ...praca.palavras.map((p) => p.sessoes));
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
      <header className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
        <h3 className="text-xs font-semibold text-slate-100 inline-flex items-center gap-1.5">
          <Search className="w-3.5 h-3.5 text-slate-500" /> {praca.praca}
        </h3>
        <span className="text-[11px] text-slate-500">
          {numero(praca.sessoes)} sessões · {numero(praca.palavras_distintas)} palavras · {numero(praca.conversoes)} conversões
        </span>
      </header>
      <table className="w-full text-xs">
        <tbody>
          {visiveis.map((p) => (
            <tr key={p.palavra} className="border-b border-slate-800/60 last:border-0">
              <td className="py-1.5 pr-2 text-slate-200">
                {p.palavra}
                <span className="block text-[10px] text-slate-600">
                  {p.tipo}
                  {p.empreendimentos.length ? ` · ${p.empreendimentos.map(empreendimentoCurto).join(', ')}` : ''}
                </span>
              </td>
              <td className="py-1.5 w-1/3">
                <span className="block h-1.5 rounded bg-sky-500/70" style={{ width: `${Math.round((p.sessoes / maior) * 100)}%` }} />
              </td>
              <td className="py-1.5 pl-2 text-right tabular-nums text-slate-300 whitespace-nowrap">
                {numero(p.sessoes)} sessões
                {p.conversoes ? <span className="text-emerald-300"> · {numero(p.conversoes)} conv.</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {praca.palavras.length > 5 && (
        <button onClick={onAlternar} className="botao-secundario mt-2 text-[11px]">
          {aberta ? 'Mostrar menos' : `Mostrar as ${numero(praca.palavras.length)} palavras`}
        </button>
      )}
    </section>
  );
}
