'use client';

/**
 * Analista digital: o que os números do período mostram, em ordem de prioridade.
 * Cada achado traz os números, o que fazer e o link para conferir na tela certa (com os mesmos filtros).
 */

import React, { Suspense, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AlertTriangle, ArrowRight, Info, Lightbulb, TrendingUp } from 'lucide-react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { Card, ErroCarga, StatTile } from '../../components/bi/ui';
import { VendasOnline } from '../../components/bi/VendasOnline';
import { fetchAnalise } from '../../lib/biApi';
import { data, numero, reaisCentavos, reaisCompacto } from '../../lib/format';
import { Achado, TipoAchado } from '../../types/bi';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Analista" subtitulo="O que os números do período mostram, por que importa e o que fazer, em ordem de prioridade">
        <Abas />
      </AppShell>
    </Suspense>
  );
}

type Aba = 'achados' | 'vendas_online';

function Abas() {
  const { filtros } = useFiltros();
  const [aba, setAba] = useState<Aba>('achados');
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Filtro ativo={aba === 'achados'} onClick={() => setAba('achados')}>
          Achados do período
        </Filtro>
        <Filtro ativo={aba === 'vendas_online'} onClick={() => setAba('vendas_online')}>
          Vendas online × leads
        </Filtro>
      </div>
      {aba === 'achados' ? (
        <Analista />
      ) : (
        <VendasOnline
          inicio={filtros.inicio}
          fim={filtros.fim}
          filtrosAtivos={filtros.empreendimentos.length + filtros.pracas.length}
        />
      )}
    </div>
  );
}

const TIPO: Record<TipoAchado, { icone: typeof Info; classe: string; borda: string }> = {
  alerta: { icone: AlertTriangle, classe: 'text-amber-300 bg-amber-500/10 border-amber-500/40', borda: 'border-l-amber-400' },
  oportunidade: { icone: Lightbulb, classe: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/40', borda: 'border-l-emerald-400' },
  destaque: { icone: TrendingUp, classe: 'text-sky-300 bg-sky-500/10 border-sky-500/40', borda: 'border-l-sky-400' },
  contexto: { icone: Info, classe: 'text-slate-300 bg-slate-700/30 border-slate-600', borda: 'border-l-slate-500' },
};

const TELA: Record<string, string> = {
  '/': 'Visão geral',
  '/empreendimentos': 'Empreendimentos',
  '/anuncios': 'Anúncios',
  '/funil': 'Funil e vendas',
  '/conferencias': 'Conferências',
  '/diagnosticos': 'Diagnósticos',
  '/vendas': 'Vendas × leads',
  '/bases': 'Bases e integrações',
};

function Analista() {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const params = useSearchParams();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchAnalise(filtros), [chave, versao]);
  const [tipo, setTipo] = useState<TipoAchado | null>(null);
  const [area, setArea] = useState<string | null>(null);

  const areasPresentes = useMemo(() => {
    const mapa = new Map<string, string>();
    (dados?.achados ?? []).forEach((a) => mapa.set(a.area, a.area_label));
    return Array.from(mapa.entries());
  }, [dados]);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Analisando leads, anúncios, funil, vendas e dados...</p>;

  const query = params.toString();
  const visiveis = dados.achados.filter((a) => (!tipo || a.tipo === tipo) && (!area || a.area === area));
  const p = dados.panorama;

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatTile destaque label="Alertas" valor={numero(dados.contagem.alerta)} sub="pedem ação" onClick={() => setTipo(tipo === 'alerta' ? null : 'alerta')} />
        <StatTile label="Oportunidades" valor={numero(dados.contagem.oportunidade)} sub="onde ganhar mais" onClick={() => setTipo(tipo === 'oportunidade' ? null : 'oportunidade')} />
        <StatTile label="Destaques" valor={numero(dados.contagem.destaque)} sub="o que melhorou" onClick={() => setTipo(tipo === 'destaque' ? null : 'destaque')} />
        <StatTile label="Leads online" valor={numero(p.leads)} delta={p.variacao_leads} sub={`${numero(p.vendas)} vendas · ${reaisCompacto(p.vgv)}`} />
        <StatTile label="Investimento em mídia" valor={reaisCompacto(p.investimento)} sub={p.cpl_meta ? `${reaisCentavos(p.cpl_meta)} por lead da Meta no CV` : 'custo por lead indisponível'} subirEBom={false} />
      </div>

      <Card titulo="Resumo do analista" subtitulo={`${data(dados.periodo.inicio)} a ${data(dados.periodo.fim)}, comparado com ${data(dados.periodo.anterior_inicio)} a ${data(dados.periodo.anterior_fim)}`}>
        <ul className="space-y-1.5 text-sm text-slate-200 leading-relaxed">
          {dados.manchetes.map((m) => (
            <li key={m} className="flex gap-2">
              <span className="text-slate-500">•</span>
              <span>{m}</span>
            </li>
          ))}
        </ul>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Filtro ativo={!tipo && !area} onClick={() => { setTipo(null); setArea(null); }}>
          Todos · {numero(dados.achados.length)}
        </Filtro>
        {areasPresentes.map(([chaveArea, label]) => (
          <Filtro key={chaveArea} ativo={area === chaveArea} onClick={() => setArea(area === chaveArea ? null : chaveArea)}>
            {label} · {numero(dados.achados.filter((a) => a.area === chaveArea).length)}
          </Filtro>
        ))}
      </div>

      <div className="space-y-3">
        {visiveis.map((a) => (
          <CartaoAchado key={a.id} achado={a} query={query} />
        ))}
        {!visiveis.length && (
          <div className="painel p-8 text-center text-xs text-slate-400">
            {dados.achados.length ? 'Nenhum achado com esse filtro.' : 'Nada fora do normal no período: nenhuma variação relevante com amostra suficiente.'}
          </div>
        )}
      </div>

      <Card titulo="Como o analista decide" subtitulo="Para nenhum achado ser alarme falso">
        <ul className="space-y-1 text-xs text-slate-400 leading-relaxed list-disc pl-4">
          {dados.criterios.map((c) => (
            <li key={c}>{c}</li>
          ))}
          {dados.falhas.length > 0 && <li className="text-amber-300">Não foi possível analisar: {dados.falhas.join(', ')}.</li>}
        </ul>
      </Card>
    </div>
  );
}

function Filtro({ ativo, onClick, children }: { ativo: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={ativo}
      className={`px-3 py-1.5 rounded-lg border text-[11px] ${
        ativo ? 'border-sky-500/60 bg-sky-500/10 text-sky-200' : 'border-slate-700 text-slate-400 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  );
}

function CartaoAchado({ achado: a, query }: { achado: Achado; query: string }) {
  const estilo = TIPO[a.tipo];
  const Icone = estilo.icone;
  return (
    <article className={`painel p-4 border-l-4 ${estilo.borda}`}>
      <div className="flex flex-wrap items-center gap-2 mb-1.5">
        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${estilo.classe}`}>
          <Icone className="w-3 h-3" /> {a.tipo_label}
        </span>
        <span className="text-[10px] text-slate-500 uppercase tracking-wide">{a.area_label}</span>
      </div>
      <h3 className="text-sm font-semibold text-white">{a.titulo}</h3>
      <p className="text-xs text-slate-300 mt-1 leading-relaxed">{a.texto}</p>
      {a.evidencias.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-[11px]">
          {a.evidencias.map((e) => (
            <li key={e.rotulo + e.valor} className="flex flex-wrap justify-between gap-x-4 border-b border-slate-800/60 py-1">
              <span className="text-slate-400">{e.rotulo}</span>
              <span className="text-slate-200 tabular-nums">{e.valor}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <p className="text-xs text-slate-200 leading-relaxed max-w-3xl">
          <span className="font-semibold text-slate-100">O que fazer: </span>
          {a.recomendacao}
        </p>
        {a.tela && (
          <Link href={`${a.tela}${query ? `?${query}` : ''}`} className="botao-secundario inline-flex items-center gap-1 whitespace-nowrap">
            Ver em {TELA[a.tela] ?? a.tela} <ArrowRight className="w-3 h-3" />
          </Link>
        )}
      </div>
    </article>
  );
}
