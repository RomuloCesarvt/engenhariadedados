'use client';

import React, { Suspense, useMemo, useRef, useState } from 'react';
import { Download, Loader2, RefreshCw, Save } from 'lucide-react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados } from '../../components/bi/useFiltros';
import { Aviso, ErroCarga } from '../../components/bi/ui';
import { QuadroRef } from '../../components/apresentacao/Slide';
import { QuadroQamar } from '../../components/qamar/QuadroQamar';
import {
  AConectar,
  BlogPosts,
  Capa,
  Encerramento,
  FbVisao,
  IgConteudo,
  IgConteudos,
  IgDestaques,
  IgInteracoes,
  IgMaisComentados,
  IgPublico,
  IgStories,
  IgVisao,
  Imprensa,
  Indice,
  PagoAnuncios,
  PagoEntrega,
  SitePaginas,
  SiteVisao,
  YtVisao,
} from '../../components/qamar/slides';
import { fetchQamar, fetchQamarComparativo, salvarQamarManual } from '../../lib/biApi';
import { QamarComparativo, QamarRelatorio } from '../../types/qamar';
import { CmpInstagram, CmpLeitura, CmpPago, CmpSiteEConteudo, CmpTendencias } from '../../components/qamar/comparativo';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Qamar" subtitulo="O relatório mensal da agência de comunicação, montado com os dados das próprias fontes" semFiltros>
        <RelatorioQamar />
      </AppShell>
    </Suspense>
  );
}

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];

function opcoesDeMes(): { valor: string; rotulo: string }[] {
  const hoje = new Date();
  const lista = [];
  for (let i = 0; i < 12; i++) {
    const d = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1);
    lista.push({ valor: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`, rotulo: `${MESES[d.getMonth()]}/${d.getFullYear()}` });
  }
  return lista;
}

interface SlideDef {
  id: string;
  titulo: string;
  secao?: string;
  numeroSecao?: string;
  tituloSlide?: string;
  capa?: boolean;
  corpo: React.ReactNode;
}

function montarSlides(r: QamarRelatorio, cmp: QamarComparativo | null): SlideDef[] {
  const rot = r.rotulos;
  const s: SlideDef[] = [];
  const ig = r.instagram;
  const sec = (numeroSecao: string, secao: string) => ({ numeroSecao, secao });

  s.push({ id: 'qamar-capa', titulo: 'Capa', capa: true, corpo: <Capa rotulo={r.rotulo} /> });
  s.push({ id: 'qamar-indice', titulo: 'Índice', secao: 'Índice', tituloSlide: 'Índice', corpo: null }); // preenchido no fim

  if (ig.status === 'real') {
    const I = sec('01', 'Instagram');
    s.push({ id: 'qamar-ig-visao', titulo: 'Instagram · visão geral', ...I, tituloSlide: 'Visão geral', corpo: <IgVisao ig={ig} rotulos={rot} /> });
    s.push({ id: 'qamar-ig-interacoes', titulo: 'Instagram · interações e publicações', ...I, tituloSlide: 'Interações e publicações', corpo: <IgInteracoes ig={ig} rotulos={rot} /> });
    s.push({ id: 'qamar-ig-conteudo', titulo: 'Instagram · conteúdos publicados', ...I, tituloSlide: 'Conteúdos publicados no mês', corpo: <IgConteudo ig={ig} rotulos={rot} /> });
    const total = ig.conteudos?.length || 0;
    const partes = Math.ceil(total / 8);
    for (let i = 0; i < total; i += 8) {
      const n = i / 8 + 1;
      s.push({
        id: `qamar-ig-conteudos-${n}`,
        titulo: `Instagram · conteúdos do mês${partes > 1 ? ` (${n}/${partes})` : ''}`,
        ...I,
        tituloSlide: `Conteúdos de ${rot.atual.toLowerCase()}${partes > 1 ? ` (${n}/${partes})` : ''}`,
        corpo: <IgConteudos itens={ig.conteudos.slice(i, i + 8)} />,
      });
    }
    s.push({ id: 'qamar-ig-stories', titulo: 'Instagram · stories', ...I, tituloSlide: `Stories de ${rot.atual.toLowerCase()}`, corpo: <IgStories ig={ig} /> });
    if (ig.destaques.length) {
      s.push({ id: 'qamar-ig-destaques', titulo: 'Instagram · destaques', ...I, tituloSlide: `Destaques de ${rot.atual.toLowerCase()}`, corpo: <IgDestaques ig={ig} rotulos={rot} /> });
    }
    for (let i = 0; i < ig.mais_comentados.length; i += 2) {
      s.push({
        id: `qamar-ig-comentados-${i / 2 + 1}`,
        titulo: `Instagram · mais comentados (${i / 2 + 1})`,
        ...I,
        tituloSlide: `Mais comentados de ${rot.atual.toLowerCase()}`,
        corpo: <IgMaisComentados itens={ig.mais_comentados.slice(i, i + 2)} />,
      });
    }
    s.push({ id: 'qamar-ig-publico', titulo: 'Instagram · público', ...I, tituloSlide: 'Público', corpo: <IgPublico ig={ig} /> });
  } else {
    s.push({ id: 'qamar-ig-erro', titulo: 'Instagram', ...sec('01', 'Instagram'), tituloSlide: 'Instagram', corpo: <AConectar bloco={ig} rede="Instagram" /> });
  }

  const F = sec('02', 'Facebook');
  s.push(
    r.facebook.status === 'real' || r.facebook.status === 'parcial'
      ? { id: 'qamar-fb', titulo: 'Facebook · visão geral', ...F, tituloSlide: 'Visão geral', corpo: <FbVisao fb={r.facebook} rotulos={rot} /> }
      : { id: 'qamar-fb', titulo: 'Facebook · a conectar', ...F, tituloSlide: 'Facebook', corpo: <AConectar bloco={r.facebook} rede="Facebook" /> }
  );
  s.push({ id: 'qamar-linkedin', titulo: 'LinkedIn · a conectar', ...sec('03', 'LinkedIn'), tituloSlide: 'Desempenho', corpo: <AConectar bloco={r.linkedin} rede="LinkedIn" /> });
  s.push({ id: 'qamar-tiktok', titulo: 'TikTok · a conectar', ...sec('04', 'TikTok'), tituloSlide: 'TikTok', corpo: <AConectar bloco={r.tiktok} rede="TikTok" /> });
  s.push({ id: 'qamar-youtube', titulo: 'YouTube', ...sec('05', 'YouTube'), tituloSlide: `Vídeos de ${rot.atual.toLowerCase()}`, corpo: r.youtube?.status === 'real' ? <YtVisao yt={r.youtube} rotulos={rot} /> : <AConectar bloco={r.youtube ?? { status: 'nao_conectado', mensagem: 'Atualize o relatório para buscar o YouTube.' }} rede="YouTube" /> });
  s.push({ id: 'qamar-gmn', titulo: 'Google Meu Negócio · a conectar', ...sec('06', 'Google Meu Negócio'), tituloSlide: 'Contatos pelo perfil', corpo: <AConectar bloco={r.gmn} rede="Google Meu Negócio" /> });

  if (r.site.status === 'real') {
    const S = sec('07', 'Site');
    s.push({ id: 'qamar-site-visao', titulo: 'Site · visão geral', ...S, tituloSlide: 'Visão geral', corpo: <SiteVisao site={r.site} rotulos={rot} /> });
    s.push({ id: 'qamar-site-paginas', titulo: 'Site · páginas mais visitadas', ...S, tituloSlide: 'Páginas mais visitadas', corpo: <SitePaginas site={r.site} rotulos={rot} /> });
  }
  if (r.blog.status === 'real') {
    s.push({ id: 'qamar-blog', titulo: 'Blog · posts publicados', ...sec('08', 'Blog'), tituloSlide: 'Posts publicados', corpo: <BlogPosts blog={r.blog} rotulos={rot} /> });
  }
  s.push({ id: 'qamar-imprensa', titulo: 'Assessoria de imprensa', ...sec('09', 'Assessoria de Imprensa'), tituloSlide: 'Cobertura e ações', corpo: <Imprensa imprensa={r.imprensa} /> });
  if (r.trafego_pago.status === 'real') {
    const T = sec('10', 'Tráfego pago');
    s.push({ id: 'qamar-pago-anuncios', titulo: 'Tráfego pago · anúncios', ...T, tituloSlide: `Anúncios de ${rot.atual.toLowerCase()}`, corpo: <PagoAnuncios pago={r.trafego_pago} rotulos={rot} /> });
    s.push({ id: 'qamar-pago-entrega', titulo: 'Tráfego pago · entrega', ...T, tituloSlide: 'Entrega e público', corpo: <PagoEntrega pago={r.trafego_pago} /> });
  }
  if (cmp && cmp.resumos.length >= 2) {
    const C = sec('11', 'Comparativo');
    const periodo = `${cmp.resumos[0].rotulo} a ${cmp.resumos[cmp.resumos.length - 1].rotulo}`;
    s.push({ id: 'qamar-cmp-instagram', titulo: 'Comparativo · Instagram', ...C, tituloSlide: `Instagram · ${periodo}`, corpo: <CmpInstagram cmp={cmp} /> });
    s.push({ id: 'qamar-cmp-tendencias', titulo: 'Comparativo · tendências', ...C, tituloSlide: 'Tendências', corpo: <CmpTendencias cmp={cmp} /> });
    s.push({ id: 'qamar-cmp-site', titulo: 'Comparativo · site, blog e YouTube', ...C, tituloSlide: 'Site, blog e YouTube', corpo: <CmpSiteEConteudo cmp={cmp} /> });
    s.push({ id: 'qamar-cmp-pago', titulo: 'Comparativo · tráfego pago', ...C, tituloSlide: 'Tráfego pago e anúncios', corpo: <CmpPago cmp={cmp} /> });
    s.push({ id: 'qamar-cmp-leitura', titulo: 'Comparativo · leitura', ...C, tituloSlide: 'O que os números dizem', corpo: <CmpLeitura cmp={cmp} /> });
  }
  s.push({ id: 'qamar-fim', titulo: 'Encerramento', capa: true, corpo: <Encerramento /> });

  // Índice: a primeira página de cada seção
  const secoes: { numero: string; nome: string; pagina: number }[] = [];
  s.forEach((slide, i) => {
    if (slide.numeroSecao && slide.secao && !secoes.find((x) => x.numero === slide.numeroSecao)) {
      secoes.push({ numero: slide.numeroSecao, nome: slide.secao, pagina: i + 1 });
    }
  });
  s[1].corpo = <Indice itens={secoes} />;
  return s;
}

function RelatorioQamar() {
  const { versao } = useShell();
  const meses = useMemo(opcoesDeMes, []);
  // Abre no último mês fechado, que é o que a agência entrega
  const [mes, setMes] = useState(meses[1].valor);
  const [forcar, setForcar] = useState(0);
  const [comparar, setComparar] = useState(false);
  const { dados, erro, carregando, recarregar } = useDados(() => fetchQamar(mes, forcar > 0, comparar), [mes, forcar, comparar, versao]);
  const refs = useRef<(QuadroRef | null)[]>([]);
  const [baixando, setBaixando] = useState(false);

  // Comparativo entre meses: opcional, com os meses escolhidos pelo usuário
  const [cmpAtivo, setCmpAtivo] = useState(false);
  const [cmpMeses, setCmpMeses] = useState<string[]>([]);
  const chaveCmp = cmpMeses.slice().sort().join(',');
  const cmp = useDados<QamarComparativo | null>(
    () => (cmpAtivo && cmpMeses.length >= 2 ? fetchQamarComparativo(cmpMeses, forcar > 0) : Promise.resolve(null)),
    [cmpAtivo, chaveCmp, forcar, versao]
  );

  function alternarComparativo(ligar: boolean) {
    setCmpAtivo(ligar);
    if (ligar && cmpMeses.length === 0) {
      // Sugestão: os 6 meses terminando no mês do relatório
      const i = meses.findIndex((m) => m.valor === mes);
      setCmpMeses(meses.slice(i, i + 6).map((m) => m.valor));
    }
  }

  function alternarMes(valor: string) {
    setCmpMeses((atual) => (atual.includes(valor) ? atual.filter((m) => m !== valor) : [...atual, valor].slice(-12)));
  }

  const slides = useMemo(() => (dados ? montarSlides(dados, cmpAtivo ? cmp.dados : null) : null), [dados, cmpAtivo, cmp.dados]);

  async function baixarTodos() {
    setBaixando(true);
    try {
      for (const ref of refs.current) {
        if (ref) await ref.baixar();
        await new Promise((ok) => setTimeout(ok, 600));
      }
    } finally {
      setBaixando(false);
    }
  }

  const controles = (
    <div className="flex flex-wrap items-center gap-3">
      <label className="text-xs text-slate-300 flex items-center gap-2">
        Mês do relatório
        <select value={mes} onChange={(e) => setMes(e.target.value)} className="bg-slate-800 border border-slate-600 rounded-md px-2 py-1 text-xs text-slate-100">
          {meses.map((m) => (
            <option key={m.valor} value={m.valor}>
              {m.rotulo}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs text-slate-300 flex items-center gap-2">
        <input type="checkbox" checked={comparar} onChange={(e) => setComparar(e.target.checked)} />
        Comparar com o mês anterior
      </label>
      <label className="text-xs text-slate-300 flex items-center gap-2">
        <input type="checkbox" checked={cmpAtivo} onChange={(e) => alternarComparativo(e.target.checked)} />
        Comparar vários meses
      </label>
      <button onClick={() => setForcar((n) => n + 1)} disabled={carregando} className="botao-secundario">
        {carregando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
        Buscar de novo nas fontes
      </button>
      <button onClick={baixarTodos} disabled={!slides || baixando} className="botao-secundario">
        {baixando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
        Baixar todos os slides
      </button>
      {dados && (
        <span className="text-[11px] text-slate-400">
          {dados.rotulos.antes ? `Comparado com ${dados.rotulos.antes.toLowerCase()}` : `Dados só de ${dados.rotulos.atual.toLowerCase()}`} · gerado às {dados.gerado_em.slice(11, 16)}
        </span>
      )}
    </div>
  );

  if (erro && !dados) {
    return (
      <>
        <div className="mb-4">{controles}</div>
        <ErroCarga mensagem={erro} onTentar={recarregar} />
      </>
    );
  }
  if (!dados || !slides) {
    return (
      <>
        <div className="mb-4">{controles}</div>
        <p className="text-xs text-slate-400">Buscando Instagram, Facebook, site, blog e anúncios do mês. Na primeira vez leva cerca de um minuto...</p>
      </>
    );
  }

  const faltam = [dados.instagram, dados.facebook, dados.linkedin, dados.tiktok, dados.youtube ?? { status: 'real' as const }, dados.gmn, dados.site, dados.blog, dados.trafego_pago].filter((b) => b.status === 'nao_conectado').length;

  return (
    <div className="space-y-6">
      {controles}
      {cmpAtivo && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 space-y-2">
          <p className="text-xs text-slate-300">
            Meses do comparativo (de 2 a 12). Vira uma seção de insights no fim do relatório: tabelas mês a mês, tendências e uma leitura em frases.
          </p>
          <div className="flex flex-wrap gap-2">
            {meses
              .slice()
              .reverse()
              .map((m) => {
                const on = cmpMeses.includes(m.valor);
                return (
                  <button
                    key={m.valor}
                    onClick={() => alternarMes(m.valor)}
                    className={`text-xs rounded-full px-3 py-1 border ${on ? 'bg-emerald-700 border-emerald-500 text-white' : 'bg-slate-800 border-slate-600 text-slate-300'}`}
                  >
                    {m.rotulo}
                  </button>
                );
              })}
          </div>
          {cmpMeses.length < 2 && <p className="text-[11px] text-amber-300">Escolha pelo menos dois meses.</p>}
          {cmp.carregando && cmpMeses.length >= 2 && <p className="text-[11px] text-slate-400">Calculando o comparativo (leva até um minuto na primeira vez de cada mês)...</p>}
          {cmp.erro && <p className="text-[11px] text-rose-300">Não foi possível montar o comparativo: {cmp.erro}</p>}
        </div>
      )}
      {faltam > 0 && (
        <Aviso tipo="atencao">
          {faltam} fonte(s) ainda sem conexão (veja os slides marcados "a conectar"). O slide de cada uma traz o passo a passo para conectar; até lá, o número vem da agência.
        </Aviso>
      )}
      <EditorImprensa key={mes} mes={mes} imprensa={dados.imprensa} aoSalvar={recarregar} />
      {slides.map((sl, i) => (
        <QuadroQamar
          key={sl.id}
          ref={(el) => {
            refs.current[i] = el;
          }}
          id={sl.id}
          titulo={sl.titulo}
          secao={sl.secao}
          numeroSecao={sl.numeroSecao}
          tituloSlide={sl.tituloSlide}
          pagina={i + 1}
          capa={sl.capa}
        >
          {sl.corpo}
        </QuadroQamar>
      ))}
    </div>
  );
}

function EditorImprensa({ mes, imprensa, aoSalvar }: { mes: string; imprensa: QamarRelatorio['imprensa']; aoSalvar: () => void }) {
  const [itens, setItens] = useState(imprensa.itens.join('\n'));
  const [obs, setObs] = useState(imprensa.observacoes);
  const [estado, setEstado] = useState<'parado' | 'salvando' | 'salvo' | 'erro'>('parado');

  async function salvar() {
    setEstado('salvando');
    try {
      await salvarQamarManual(mes, {
        imprensa: itens
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean),
        observacoes: obs,
      });
      setEstado('salvo');
      aoSalvar();
    } catch {
      setEstado('erro');
    }
  }

  return (
    <details className="rounded-xl border border-slate-700 bg-slate-900/50 p-4">
      <summary className="cursor-pointer text-sm font-semibold text-slate-100">Assessoria de imprensa: texto do mês (não existe API, é digitado aqui)</summary>
      <div className="mt-3 grid md:grid-cols-2 gap-3">
        <label className="text-xs text-slate-300 space-y-1">
          Cobertura e ações (uma por linha)
          <textarea value={itens} onChange={(e) => setItens(e.target.value)} rows={5} className="w-full bg-slate-800 border border-slate-600 rounded-md p-2 text-xs text-slate-100" />
        </label>
        <label className="text-xs text-slate-300 space-y-1">
          Aproveitamento do conteúdo / observações
          <textarea value={obs} onChange={(e) => setObs(e.target.value)} rows={5} className="w-full bg-slate-800 border border-slate-600 rounded-md p-2 text-xs text-slate-100" />
        </label>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button onClick={salvar} disabled={estado === 'salvando'} className="botao-secundario">
          {estado === 'salvando' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          Salvar texto
        </button>
        {estado === 'salvo' && <span className="text-[11px] text-emerald-300">Salvo. O slide já mostra o texto.</span>}
        {estado === 'erro' && <span className="text-[11px] text-rose-300">Não foi possível salvar.</span>}
      </div>
    </details>
  );
}
