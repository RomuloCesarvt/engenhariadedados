'use client';

/**
 * Filtros globais guardados na URL: toda tela abre com o mesmo recorte, o link pode ser
 * compartilhado e o botão voltar do navegador funciona.
 */

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Filtros } from '../../types/bi';

export type Preset = 'mes_atual' | 'mes_anterior' | 'ult_30' | 'ult_90' | 'ano_atual' | 'ult_12m' | 'personalizado';

export const PRESETS: { id: Preset; label: string }[] = [
  { id: 'ult_30', label: 'Últimos 30 dias' },
  { id: 'mes_atual', label: 'Este mês' },
  { id: 'mes_anterior', label: 'Mês passado' },
  { id: 'ult_90', label: 'Últimos 90 dias' },
  { id: 'ano_atual', label: 'Este ano' },
  { id: 'ult_12m', label: 'Últimos 12 meses' },
  { id: 'personalizado', label: 'Personalizado' },
];

const PRESET_PADRAO: Preset = 'ult_30';

function iso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dia = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${dia}`;
}

export function periodoDoPreset(preset: Preset, hoje = new Date()): { inicio: string; fim: string } {
  const h = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const menosDias = (n: number) => new Date(h.getFullYear(), h.getMonth(), h.getDate() - n);
  switch (preset) {
    case 'mes_atual':
      return { inicio: iso(new Date(h.getFullYear(), h.getMonth(), 1)), fim: iso(h) };
    case 'mes_anterior':
      return {
        inicio: iso(new Date(h.getFullYear(), h.getMonth() - 1, 1)),
        fim: iso(new Date(h.getFullYear(), h.getMonth(), 0)),
      };
    case 'ult_90':
      return { inicio: iso(menosDias(89)), fim: iso(h) };
    case 'ano_atual':
      return { inicio: iso(new Date(h.getFullYear(), 0, 1)), fim: iso(h) };
    case 'ult_12m':
      return { inicio: iso(new Date(h.getFullYear() - 1, h.getMonth(), h.getDate() + 1)), fim: iso(h) };
    case 'ult_30':
    default:
      return { inicio: iso(menosDias(29)), fim: iso(h) };
  }
}

export function useFiltros() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const query = params.toString();

  const preset = ((params.get('periodo') as Preset) || PRESET_PADRAO) as Preset;

  const filtros: Filtros = useMemo(() => {
    const padrao = periodoDoPreset(preset === 'personalizado' ? PRESET_PADRAO : preset);
    return {
      inicio: preset === 'personalizado' ? params.get('inicio') || padrao.inicio : padrao.inicio,
      fim: preset === 'personalizado' ? params.get('fim') || padrao.fim : padrao.fim,
      empreendimentos: params.getAll('emp'),
      pracas: params.getAll('praca'),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const mudar = useCallback(
    (fn: (q: URLSearchParams) => void) => {
      const q = new URLSearchParams(params.toString());
      fn(q);
      router.replace(`${pathname}${q.toString() ? `?${q.toString()}` : ''}`, { scroll: false });
    },
    [params, pathname, router]
  );

  return {
    filtros,
    preset,
    query,
    /** chave estável para dependências de efeitos */
    chave: `${filtros.inicio}|${filtros.fim}|${filtros.empreendimentos.join(',')}|${filtros.pracas.join(',')}`,
    setPreset: (p: Preset) =>
      mudar((q) => {
        q.set('periodo', p);
        if (p === 'personalizado') {
          q.set('inicio', filtros.inicio);
          q.set('fim', filtros.fim);
        } else {
          q.delete('inicio');
          q.delete('fim');
        }
      }),
    setPersonalizado: (inicio: string, fim: string) =>
      mudar((q) => {
        q.set('periodo', 'personalizado');
        q.set('inicio', inicio);
        q.set('fim', fim);
      }),
    setEmpreendimentos: (lista: string[]) =>
      mudar((q) => {
        q.delete('emp');
        lista.forEach((e) => q.append('emp', e));
      }),
    setPracas: (lista: string[]) =>
      mudar((q) => {
        q.delete('praca');
        lista.forEach((p) => q.append('praca', p));
      }),
    limpar: () =>
      mudar((q) => {
        q.delete('emp');
        q.delete('praca');
      }),
  };
}

/** Busca assíncrona que mantém o resultado anterior visível enquanto recarrega. */
export function useDados<T>(carregar: () => Promise<T>, deps: unknown[]) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    let vivo = true;
    setCarregando(true);
    setErro(null);
    carregar()
      .then((d) => vivo && setDados(d))
      .catch((e: Error) => vivo && setErro(e.message))
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tentativa]);

  return { dados, erro, carregando, recarregar: () => setTentativa((t) => t + 1) };
}
