'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  AlertTriangle,
  BarChart3,
  Building2,
  Megaphone,
  Database,
  FileSpreadsheet,
  Filter,
  GitCompare,
  Globe,
  History,
  Lightbulb,
  Presentation,
  Newspaper,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { FilterBar } from './FilterBar';
import { useFiltros } from './useFiltros';
import { atualizarBases, fetchBases, fetchOpcoes } from '../../lib/biApi';
import { dataHora, idade } from '../../lib/format';
import { BaseInfo, EstadoAtualizacao, OpcoesResponse } from '../../types/bi';
import { ThemeToggle } from '../ThemeToggle';

// O Analista fecha a sequência: ele lê o que as telas anteriores mostram. Bases e integrações
// vem depois dele, porque é manutenção, não leitura do período.
const NAV = [
  { href: '/', label: 'Visão geral', icone: BarChart3 },
  { href: '/empreendimentos', label: 'Empreendimentos', icone: Building2 },
  { href: '/anuncios', label: 'Anúncios', icone: Megaphone },
  { href: '/site', label: 'Site (Analytics)', icone: Globe },
  { href: '/funil', label: 'Funil e vendas', icone: Filter },
  { href: '/conferencias', label: 'Conferências', icone: GitCompare },
  { href: '/diagnosticos', label: 'Diagnósticos', icone: AlertTriangle },
  { href: '/vendas', label: 'Vendas × leads', icone: FileSpreadsheet },
  { href: '/analista', label: 'Analista', icone: Lightbulb },
  { href: '/apresentacao', label: 'Apresentação', icone: Presentation },
  { href: '/qamar', label: 'Qamar', icone: Newspaper },
  { href: '/bases', label: 'Bases e integrações', icone: Database },
  { href: '/reconciliacao', label: 'Reconciliação (anterior)', icone: History },
];

interface ShellCtx {
  /** muda quando as bases terminam de atualizar: telas incluem nas dependências */
  versao: number;
  opcoes: OpcoesResponse | null;
  erroOpcoes: string | null;
}

const Contexto = createContext<ShellCtx>({ versao: 0, opcoes: null, erroOpcoes: null });
export const useShell = () => useContext(Contexto);

function FrescorDosDados({ bases, onAtualizado }: { bases: BaseInfo[]; onAtualizado: () => void }) {
  const [estado, setEstado] = useState<EstadoAtualizacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const cv = bases.find((b) => b.base === 'cv_leads');

  const acompanhar = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(async () => {
      try {
        const r = await fetchBases();
        setEstado(r.atualizacao);
        if (!r.atualizacao.em_andamento) {
          if (timer.current) clearInterval(timer.current);
          onAtualizado();
        }
      } catch {
        /* mantém o acompanhamento na próxima volta */
      }
    }, 4000);
  }, [onAtualizado]);

  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
  }, []);

  async function atualizar() {
    setErro(null);
    try {
      const r = await atualizarBases();
      setEstado({ ...r, em_andamento: true });
      acompanhar();
    } catch (e: any) {
      setErro(e.message);
    }
  }

  const rodando = estado?.em_andamento;
  return (
    <div className="flex items-center gap-3 text-[11px]">
      {cv && (
        <span className="text-slate-400" title={cv.dados_de ?? undefined}>
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle ${
              cv.status.mode === 'real' ? 'bg-emerald-400' : 'bg-rose-400'
            }`}
          />
          CV atualizado {idade(cv.idade_horas)}
          {cv.dados_de && <span className="text-slate-600"> · {dataHora(cv.dados_de)}</span>}
        </span>
      )}
      <button onClick={atualizar} disabled={rodando} className="botao-secundario">
        {rodando ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
        {rodando ? `Atualizando ${estado?.base_atual ?? ''}...` : 'Atualizar dados'}
      </button>
      {erro && <span className="text-rose-300">{erro}</span>}
    </div>
  );
}

export function AppShell({
  titulo,
  subtitulo,
  children,
  semFiltros = false,
  acoes,
}: {
  titulo: string;
  subtitulo?: string;
  children: React.ReactNode;
  semFiltros?: boolean;
  acoes?: React.ReactNode;
}) {
  const pathname = usePathname();
  const { query } = useFiltros();
  const [versao, setVersao] = useState(0);
  const [opcoes, setOpcoes] = useState<OpcoesResponse | null>(null);
  const [erroOpcoes, setErroOpcoes] = useState<string | null>(null);

  useEffect(() => {
    fetchOpcoes()
      .then((o) => {
        setOpcoes(o);
        setErroOpcoes(null);
      })
      .catch((e: Error) => setErroOpcoes(e.message));
  }, [versao]);

  const aoAtualizar = useCallback(() => setVersao((v) => v + 1), []);

  return (
    <Contexto.Provider value={{ versao, opcoes, erroOpcoes }}>
      <div className="min-h-screen flex">
        <aside className="hidden lg:flex w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-950 sticky top-0 h-screen">
          <div className="ml-brand-lockup px-5 py-5 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <Image
                src="/moura-leite-logo-transparent.png"
                alt="Moura Leite Loteamentos"
                width={48}
                height={48}
                className="ml-brand-logo h-12 w-12 shrink-0 object-contain"
              />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-white">Moura Leite BI</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Leads, vendas e loteamentos</p>
              </div>
            </div>
            <p className="text-[11px] text-slate-500 mt-3">Mídia online × CRM Construtor de Vendas</p>
          </div>
          <nav className="flex-1 p-3 space-y-0.5" aria-label="Seções">
            {NAV.map(({ href, label, icone: Icone }) => {
              const ativo = href === '/' ? pathname === '/' : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={`${href}${query && href !== '/reconciliacao' ? `?${query}` : ''}`}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] transition-colors ${
                    ativo ? 'bg-sky-500/10 text-sky-300' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`}
                  aria-current={ativo ? 'page' : undefined}
                >
                  <Icone className="w-4 h-4" />
                  {label}
                </Link>
              );
            })}
          </nav>
          <p className="px-5 py-4 text-[10px] text-slate-600 leading-relaxed border-t border-slate-800">
            Números calculados das bases salvas. Cada indicador leva à lista de leads com a evidência da classificação.
          </p>
        </aside>

        <div className="flex-1 min-w-0">
          <header className="sticky top-0 z-30 bg-slate-900/95 backdrop-blur border-b border-slate-800">
            <div className="px-6 py-4 flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0 flex items-center gap-3">
                <Image
                  src="/moura-leite-logo-transparent.png"
                  alt="Moura Leite Loteamentos"
                  width={40}
                  height={40}
                  className="ml-brand-logo lg:hidden h-10 w-10 shrink-0 object-contain"
                />
                <div className="min-w-0">
                  <h1 className="text-lg font-semibold text-white">{titulo}</h1>
                  {subtitulo && <p className="text-xs text-slate-400 mt-0.5">{subtitulo}</p>}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {acoes}
                {opcoes && <FrescorDosDados bases={opcoes.bases} onAtualizado={aoAtualizar} />}
                <ThemeToggle />
              </div>
            </div>
            {!semFiltros && (
              <div className="px-6 pb-3">
                <FilterBar empreendimentos={opcoes?.empreendimentos ?? []} pracas={opcoes?.pracas ?? []} />
              </div>
            )}
            <nav className="lg:hidden flex gap-1 overflow-x-auto px-4 pb-2" aria-label="Seções">
              {NAV.map(({ href, label }) => (
                <Link
                  key={href}
                  href={`${href}${query ? `?${query}` : ''}`}
                  className={`px-3 py-1.5 rounded-lg text-xs whitespace-nowrap ${
                    (href === '/' ? pathname === '/' : pathname.startsWith(href)) ? 'bg-sky-500/10 text-sky-300' : 'text-slate-400'
                  }`}
                >
                  {label}
                </Link>
              ))}
            </nav>
          </header>
          <main className="px-6 py-6 max-w-[1400px]">{children}</main>
        </div>
      </div>
    </Contexto.Provider>
  );
}
