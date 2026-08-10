'use client';

import React, { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowDown, ArrowUp, ExternalLink, ImageOff, Play, Trophy, X } from 'lucide-react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { AlternarVisao, Aviso, Card, ErroCarga, StatTile, Vazio } from '../../components/bi/ui';
import { CplLeadsChart } from '../../components/bi/AnunciosChart';
import { CriativoAnuncio } from '../../components/bi/CriativoAnuncio';
import { Palavras } from '../../components/bi/Palavras';
import { fetchAnuncios, fetchCapa, fetchLeadsDoAnuncio } from '../../lib/biApi';
import { data, empreendimentoCurto, numero, pct, reais, reaisCentavos, reaisCompacto } from '../../lib/format';
import { AnuncioAuditado, CampeaoAnuncio, CapaAnuncio, Filtros, LeadsDoAnuncioResponse } from '../../types/bi';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Anúncios" subtitulo="Auditoria de cada anúncio: o que a Meta diz × o que chegou ao CV, virou SQL e venda">
        <Anuncios />
      </AppShell>
    </Suspense>
  );
}

const SEM_ANUNCIO = '__sem_anuncio__';

const STATUS_ANUNCIO: Record<string, string> = {
  ACTIVE: 'Ativo',
  PAUSED: 'Pausado',
  CAMPAIGN_PAUSED: 'Campanha pausada',
  ADSET_PAUSED: 'Conjunto pausado',
  ARCHIVED: 'Arquivado',
  DELETED: 'Excluído',
  WITH_ISSUES: 'Com problemas',
  IN_PROCESS: 'Em análise',
  PENDING_REVIEW: 'Em análise',
  DISAPPROVED: 'Reprovado',
};

const roas = (v: number | null) => (v === null ? '—' : `${v.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}x`);

function formatarMetrica(metrica: string, valor: number | null) {
  if (valor === null) return '—';
  if (metrica === 'cpl_real' || metrica === 'custo_por_venda') return reaisCentavos(valor);
  if (metrica === 'taxa_sql' || metrica === 'taxa_venda') return pct(valor);
  if (metrica === 'eficiencia') return valor.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  return numero(valor);
}

type Coluna = { campo: keyof AnuncioAuditado; label: string; formato: (a: AnuncioAuditado) => string; menorEMelhor?: boolean };

const COLUNAS: Coluna[] = [
  { campo: 'investimento', label: 'Investimento', formato: (a) => reais(a.investimento) },
  { campo: 'impressoes', label: 'Impressões', formato: (a) => numero(a.impressoes) },
  { campo: 'ctr', label: 'CTR', formato: (a) => pct(a.ctr) },
  { campo: 'leads_plataforma', label: 'Leads (Meta)', formato: (a) => numero(a.leads_plataforma) },
  { campo: 'leads_cv', label: 'Leads no CV', formato: (a) => numero(a.leads_cv) },
  { campo: 'pct_chegou', label: 'Chegou ao CV', formato: (a) => pct(a.pct_chegou) },
  { campo: 'cpl_plataforma', label: 'CPL (Meta)', formato: (a) => reaisCentavos(a.cpl_plataforma), menorEMelhor: true },
  { campo: 'cpl_real', label: 'CPL real', formato: (a) => reaisCentavos(a.cpl_real), menorEMelhor: true },
  { campo: 'taxa_sql', label: 'SQL', formato: (a) => `${numero(a.sql)} · ${pct(a.taxa_sql)}` },
  { campo: 'agendamentos', label: 'Visitas', formato: (a) => numero(a.agendamentos) },
  { campo: 'vendas', label: 'Vendas', formato: (a) => numero(a.vendas) },
  { campo: 'taxa_venda', label: 'Conversão', formato: (a) => pct(a.taxa_venda) },
  { campo: 'custo_por_venda', label: 'Custo/venda', formato: (a) => reaisCompacto(a.custo_por_venda), menorEMelhor: true },
  { campo: 'vgv', label: 'VGV', formato: (a) => reaisCompacto(a.vgv) },
  { campo: 'roas', label: 'ROAS', formato: (a) => roas(a.roas) },
];

function Miniatura({ url, tamanho = 40 }: { url: string | null; tamanho?: number }) {
  const [erro, setErro] = useState(false);
  if (!url || erro) {
    return (
      <span className="shrink-0 rounded-md bg-slate-800 inline-flex items-center justify-center text-slate-600" style={{ width: tamanho, height: tamanho }}>
        <ImageOff className="w-4 h-4" />
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt="" referrerPolicy="no-referrer" onError={() => setErro(true)} className="shrink-0 rounded-md object-cover bg-slate-800" style={{ width: tamanho, height: tamanho }} />;
}

function Anuncios() {
  const { filtros, chave, setEmpreendimentos, limpar } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchAnuncios(filtros), [chave, versao]);
  const [modoGrafico, setModoGrafico] = useState<'grafico' | 'tabela'>('grafico');
  const [selecionado, setSelecionado] = useState<{ chave: string; titulo: string; anuncio?: AnuncioAuditado } | null>(null);
  const [ordem, setOrdem] = useState<{ campo: keyof AnuncioAuditado; desc: boolean }>({ campo: 'leads_cv', desc: true });
  const [busca, setBusca] = useState('');

  const lista = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    const filtrados = (dados?.anuncios ?? []).filter(
      (a) => !termo || [a.anuncio, a.conjunto, a.campanha, a.empreendimento].some((v) => (v ?? '').toLowerCase().includes(termo))
    );
    return [...filtrados].sort((a, b) => {
      const va = a[ordem.campo] as number | null;
      const vb = b[ordem.campo] as number | null;
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return ordem.desc ? vb - va : va - vb;
    });
  }, [dados, busca, ordem]);

  const campeoes = useMemo(() => {
    if (!dados) return [];
    const melhorSqlComCriativo = [...dados.anuncios]
      .filter(
        (a) =>
          a.leads_cv >= dados.criterios.min_leads_conversao &&
          a.sql > 0 &&
          !a.sem_dados_da_plataforma &&
          Boolean(a.miniatura || a.anuncio_ids.length)
      )
      .sort((a, b) => (b.taxa_sql ?? 0) - (a.taxa_sql ?? 0) || b.sql - a.sql)[0];

    return dados.campeoes.map((campeao) => {
      const semCriativo =
        campeao.id === 'maior_qualificacao' &&
        campeao.anuncio &&
        !campeao.anuncio.miniatura &&
        campeao.anuncio.anuncio_ids.length === 0;
      if (!semCriativo || !melhorSqlComCriativo) return campeao;
      return {
        ...campeao,
        valor: melhorSqlComCriativo.taxa_sql,
        anuncio: melhorSqlComCriativo,
        criterio: `Maior % de leads que chegaram a SQL, entre anúncios com ${dados.criterios.min_leads_conversao}+ leads no CV, ao menos 1 SQL e criativo disponível.`,
      };
    });
  }, [dados]);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Cruzando anúncios da Meta com os leads do CV...</p>;
  if (!dados.disponivel) {
    return (
      <Vazio
        titulo="A base de anúncios da Meta ainda não foi baixada"
        texto="Baixe a base 'Meta Ads — Anúncios' para ver investimento, leads e custos de cada anúncio."
        acao={<Link href="/bases" className="botao-primario">Ir para Bases e integrações</Link>}
      />
    );
  }

  const r = dados.resumo;
  const abrir = (a: AnuncioAuditado) => setSelecionado({ chave: a.chave, titulo: a.anuncio, anuncio: a });

  // Filtro (empreendimento/praça) sem nenhum anúncio: explica o motivo e mostra onde há anúncios
  if (r.anuncios === 0) {
    return (
      <div className={`space-y-4 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
        <Vazio
          titulo={dados.filtro_ativo ? 'Nenhum anúncio da Meta para o filtro selecionado' : 'Nenhum anúncio da Meta no período'}
          texto={dados.motivo_vazio ?? undefined}
          acao={
            dados.filtro_ativo ? (
              <button onClick={limpar} className="botao-primario">
                Ver todos os empreendimentos
              </button>
            ) : undefined
          }
        />
        {r.leads_meta_cv > 0 && (
          <Aviso tipo="atencao">
            {numero(r.leads_meta_cv)} lead(s) de Meta chegaram ao CV no período sem anúncio identificado.{' '}
            <button
              onClick={() => setSelecionado({ chave: SEM_ANUNCIO, titulo: 'Leads de Meta sem anúncio identificado' })}
              className="underline text-amber-200"
            >
              Ver os leads e o motivo
            </button>
            {' · '}
            <Link href="/diagnosticos" className="underline text-amber-200">
              Ver em Diagnósticos
            </Link>
          </Aviso>
        )}
        {dados.empreendimentos_com_anuncios.length > 0 && (
          <Card titulo="Empreendimentos com anúncios da Meta no período" subtitulo="Clique para ver os anúncios e campeões de cada um">
            <div className="flex flex-wrap gap-2">
              {dados.empreendimentos_com_anuncios.map((e) => (
                <button key={e.empreendimento} onClick={() => setEmpreendimentos([e.empreendimento])} className="botao-secundario text-xs">
                  {empreendimentoCurto(e.empreendimento)} · {numero(e.anuncios)} anúncio(s) · {reaisCompacto(e.investimento)}
                </button>
              ))}
            </div>
          </Card>
        )}
        {selecionado && <DetalheAnuncio filtros={filtros} selecionado={selecionado} onFechar={() => setSelecionado(null)} />}
      </div>
    );
  }

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatTile destaque label="Investimento na Meta" valor={reaisCompacto(r.investimento)} sub={`${numero(r.anuncios)} anúncios no período`} />
        <StatTile label="Leads segundo a Meta" valor={numero(r.leads_plataforma)} sub={r.leads_plataforma ? `CPL da Meta ${reaisCentavos(r.investimento / r.leads_plataforma)}` : undefined} />
        <StatTile
          label="Leads de Meta no CV"
          valor={numero(r.leads_meta_cv)}
          sub={`${pct(r.cobertura)} com o anúncio identificado`}
          alerta={(r.cobertura ?? 100) < 70 ? 'atencao' : undefined}
          onClick={() => setSelecionado({ chave: SEM_ANUNCIO, titulo: 'Leads de Meta sem anúncio identificado' })}
        />
        <StatTile label="CPL real" valor={reaisCentavos(r.cpl_real)} sub="investimento ÷ leads que chegaram ao CV" subirEBom={false} />
        <StatTile label="Vendas dos leads" valor={numero(r.vendas)} sub={`${reaisCompacto(r.vgv)} de VGV`} />
        <StatTile label="ROAS" valor={roas(r.roas)} sub="VGV ÷ investimento" />
      </div>

      {dados.avisos.length > 0 && (
        <div className="grid md:grid-cols-2 gap-2">
          {dados.avisos.map((a) => (
            <Aviso key={a} tipo={a.startsWith('Só ') || a.includes('não aparecem') ? 'atencao' : 'info'}>
              {a}
            </Aviso>
          ))}
        </div>
      )}

      <Card titulo="Campeões de performance" subtitulo="Cada critério com amostra mínima, para um resultado de sorte não virar campeão. Clique para ver os leads.">
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {campeoes.map((c) => (
            <CartaoCampeao key={c.id} c={c} onAbrir={abrir} />
          ))}
        </div>
      </Card>

      <Card
        titulo="CPL real × leads no CV"
        subtitulo="Onde cada anúncio está: quanto mais à direita, mais leads; quanto mais embaixo, mais barato cada lead"
        acao={<AlternarVisao modo={modoGrafico} setModo={setModoGrafico} />}
      >
        <CplLeadsChart
          anuncios={dados.anuncios}
          medianas={dados.medianas}
          minLeads={dados.criterios.min_leads_cpl}
          minInvestimento={dados.criterios.min_investimento_cpl}
          modo={modoGrafico}
          onSelecionar={abrir}
        />
      </Card>

      <Card
        titulo={`Todos os anúncios (${numero(lista.length)})`}
        subtitulo="Clique no cabeçalho para ordenar e na linha para ver os leads por trás dos números"
        acao={
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar anúncio, conjunto, campanha..."
            className="controle text-xs w-64 bg-transparent outline-none text-slate-200 placeholder:text-slate-600"
          />
        }
      >
        <div className="overflow-x-auto max-h-[640px]">
          <table className="tabela">
            <thead className="sticky top-0 bg-slate-900 z-10">
              <tr>
                <th className="min-w-[280px]">Anúncio</th>
                {COLUNAS.map((c) => (
                  <th key={c.campo} className="text-right whitespace-nowrap">
                    <button
                      onClick={() => setOrdem((o) => ({ campo: c.campo, desc: o.campo === c.campo ? !o.desc : !c.menorEMelhor }))}
                      className="inline-flex items-center gap-1 hover:text-white"
                    >
                      {c.label}
                      {ordem.campo === c.campo && (ordem.desc ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />)}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {lista.map((a) => (
                <tr key={a.chave} className="cursor-pointer hover:bg-slate-800/40" onClick={() => abrir(a)}>
                  <td>
                    <div className="flex items-center gap-2">
                      <Miniatura url={a.miniatura} />
                      <div className="min-w-0">
                        <span className="block text-slate-100 font-medium truncate max-w-[260px]" title={a.anuncio}>
                          {a.anuncio}
                        </span>
                        <span className="block text-[10px] text-slate-500 truncate max-w-[260px]" title={`${a.conjunto ?? ''} · ${a.campanha ?? ''}`}>
                          {empreendimentoCurto(a.empreendimento)} · {a.conjunto ?? '—'}
                        </span>
                        <span className="block text-[10px] text-slate-600">
                          {a.sem_dados_da_plataforma ? 'sem dados da Meta' : STATUS_ANUNCIO[a.status ?? ''] ?? a.status ?? '—'}
                        </span>
                      </div>
                    </div>
                  </td>
                  {COLUNAS.map((c) => (
                    <td key={c.campo} className="num whitespace-nowrap">
                      {c.formato(a)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-slate-500 mt-3">
          Leads no CV: leads de Meta do período (pela última conversão, como no BI) ligados ao anúncio pelo formulário da Meta, pela UTM
          do anúncio ou pelo ID na UTM. SQL, visitas e vendas contam esses leads (coorte). CPL real = investimento ÷ leads no CV.
        </p>
      </Card>

      <Palavras filtros={filtros} chave={chave} versao={versao} />

      {selecionado && <DetalheAnuncio filtros={filtros} selecionado={selecionado} onFechar={() => setSelecionado(null)} />}
    </div>
  );
}

function CartaoCampeao({ c, onAbrir }: { c: CampeaoAnuncio; onAbrir: (a: AnuncioAuditado) => void }) {
  const a = c.anuncio;
  const valorDestaque =
    a && c.metrica === 'taxa_sql'
      ? `${numero(a.sql)} SQL de ${numero(a.leads_cv)} leads · ${pct(c.valor)}`
      : formatarMetrica(c.metrica, c.valor);

  return (
    <button
      disabled={!a}
      onClick={() => a && onAbrir(a)}
      className="text-left rounded-xl border border-slate-800 bg-slate-900/40 p-3 hover:border-slate-600 disabled:hover:border-slate-800 disabled:cursor-default"
    >
      <div className="flex items-center gap-1.5 text-[11px] text-amber-300 font-semibold mb-2">
        <Trophy className="w-3.5 h-3.5" /> {c.titulo}
      </div>
      {a ? (
        <>
          <CapaCampeao anuncio={a} />
          <div className="flex items-start gap-2">
            <div className="min-w-0">
              <p className="text-sm text-white font-semibold truncate" title={a.anuncio}>
                {a.anuncio}
              </p>
              <p className="text-[11px] text-slate-500 truncate">
                {empreendimentoCurto(a.empreendimento)} · {a.conjunto ?? '—'}
              </p>
              <p className="text-xl font-semibold text-white tabular-nums mt-1">{valorDestaque}</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 tabular-nums">
            {numero(a.leads_cv)} leads no CV · CPL real {reaisCentavos(a.cpl_real)} · {numero(a.vendas)} venda(s) · {reais(a.investimento)}
          </p>
        </>
      ) : (
        <p className="text-xs text-slate-500">{c.motivo_vazio}</p>
      )}
      {a && <p className="text-[11px] text-sky-300 mt-2">Ver o criativo (vídeo e formatos) e os leads →</p>}
      <p className="text-[10px] text-slate-600 mt-2 leading-snug">{c.criterio}</p>
    </button>
  );
}

function DetalheAnuncio({
  filtros,
  selecionado,
  onFechar,
}: {
  filtros: Filtros;
  selecionado: { chave: string; titulo: string; anuncio?: AnuncioAuditado };
  onFechar: () => void;
}) {
  const [dados, setDados] = useState<LeadsDoAnuncioResponse | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const a = selecionado.anuncio;

  useEffect(() => {
    let vivo = true;
    setDados(null);
    setErro(null);
    fetchLeadsDoAnuncio(filtros, selecionado.chave)
      .then((d) => vivo && setDados(d))
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, [filtros, selecionado.chave]);

  return (
    <div className="theme-modal-backdrop fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onFechar}>
      <div className="theme-modal-panel w-full max-w-5xl h-full overflow-y-auto bg-slate-950 border-l border-slate-800 p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-start gap-3 min-w-0">
            {a && <Miniatura url={a.miniatura} tamanho={64} />}
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-white break-words">{selecionado.titulo}</h2>
              {a && (
                <p className="text-xs text-slate-400 break-words">
                  {a.conjunto ?? '—'} · {a.campanha ?? '—'} · {a.conta ?? 'conta não lida'} · {empreendimentoCurto(a.empreendimento)}
                </p>
              )}
            </div>
          </div>
          <button onClick={onFechar} className="botao-secundario" aria-label="Fechar">
            <X className="w-4 h-4" />
          </button>
        </div>

        {a && !a.sem_dados_da_plataforma && (
          <div className="mb-4">
            <CriativoAnuncio anuncioIds={a.anuncio_ids} />
          </div>
        )}

        {a && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
            {[
              ['Investimento', reais(a.investimento)],
              ['Leads (Meta)', numero(a.leads_plataforma)],
              ['Leads no CV', `${numero(a.leads_cv)} · ${pct(a.pct_chegou)}`],
              ['CPL real', reaisCentavos(a.cpl_real)],
              ['SQL', `${numero(a.sql)} · ${pct(a.taxa_sql)}`],
              ['Visitas', numero(a.agendamentos)],
              ['Vendas', `${numero(a.vendas)} · ${pct(a.taxa_venda)}`],
              ['VGV · ROAS', `${reaisCompacto(a.vgv)} · ${roas(a.roas)}`],
            ].map(([rotulo, valor]) => (
              <div key={rotulo} className="rounded-lg bg-slate-800/50 px-3 py-2">
                <p className="text-[10px] text-slate-500">{rotulo}</p>
                <p className="text-sm text-slate-100 font-semibold tabular-nums">{valor}</p>
              </div>
            ))}
          </div>
        )}
        {a && Object.keys(a.fontes).length > 0 && (
          <p className="text-[11px] text-slate-400 mb-3">
            Como os leads foram ligados ao anúncio:{' '}
            {Object.entries(a.fontes)
              .map(([f, q]) => `${f} (${q})`)
              .join('; ')}
            .
          </p>
        )}

        {erro && <ErroCarga mensagem={erro} />}
        {!dados && !erro && <p className="text-xs text-slate-400">Carregando leads...</p>}
        {dados && (
          <div className="overflow-x-auto">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Conversão</th>
                  <th>Empreendimento</th>
                  <th>Etapa</th>
                  <th>Situação no CV</th>
                  <th>Venda</th>
                  <th>{selecionado.chave === SEM_ANUNCIO ? 'Por que ficou sem anúncio' : 'Ligado ao anúncio por'}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {dados.itens.map((l) => (
                  <tr key={String(l.id)}>
                    <td className="whitespace-nowrap">{data(l.data)}</td>
                    <td title={l.empreendimento}>{empreendimentoCurto(l.empreendimento)}</td>
                    <td className="whitespace-nowrap">{l.etapa_label}</td>
                    <td className="text-slate-400">{l.situacao ?? '—'}</td>
                    <td className="whitespace-nowrap">{l.vendido ? `${reais(l.valor_venda)} · ${data(l.data_venda)}` : '—'}</td>
                    <td className="text-[11px] text-slate-400 max-w-[220px]">{l.fonte}</td>
                    <td>
                      {l.link && (
                        <a href={l.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200 whitespace-nowrap">
                          Abrir no CV <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {dados.itens.length === 0 && <p className="text-xs text-slate-500 py-4">Nenhum lead no período.</p>}
          </div>
        )}
      </div>
    </div>
  );
}

/** Capa grande do anúncio no card: a peça inteira visível (qualquer formato), com play e duração nos vídeos. */
function CapaCampeao({ anuncio }: { anuncio: AnuncioAuditado }) {
  const anuncioId = anuncio.anuncio_ids[anuncio.anuncio_ids.length - 1];
  const [capa, setCapa] = useState<CapaAnuncio | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    if (!anuncioId || anuncio.sem_dados_da_plataforma) return;
    let vivo = true;
    setCapa(null);
    setFalhou(false);
    fetchCapa(anuncioId)
      .then((c) => vivo && setCapa(c))
      .catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, [anuncioId, anuncio.sem_dados_da_plataforma]);

  // Enquanto a capa grande carrega, mostra a miniatura da base
  const url = !falhou ? capa?.url || anuncio.miniatura : null;
  return (
    <div className="relative w-full h-44 rounded-lg overflow-hidden bg-slate-800 mb-2">
      {url ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt="" aria-hidden referrerPolicy="no-referrer" className="absolute inset-0 w-full h-full object-cover blur-lg scale-110 opacity-40" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt={`Criativo do anúncio ${anuncio.anuncio}`}
            referrerPolicy="no-referrer"
            onError={() => setFalhou(true)}
            className="relative w-full h-full object-contain"
          />
        </>
      ) : (
        <span className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-slate-500 text-[11px]">
          <ImageOff className="w-6 h-6" />
          {anuncio.sem_dados_da_plataforma ? 'Anúncio fora das contas lidas' : 'Sem imagem na Meta'}
        </span>
      )}
      {capa?.tipo === 'video' && (
        <>
          <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <span className="rounded-full bg-black/60 p-3">
              <Play className="w-6 h-6 text-white fill-white" />
            </span>
          </span>
          {capa.duracao_s ? (
            <span className="absolute bottom-1.5 right-1.5 text-[10px] font-semibold bg-black/70 text-white px-1.5 py-0.5 rounded">
              {capa.duracao_s}s
            </span>
          ) : null}
        </>
      )}
    </div>
  );
}
