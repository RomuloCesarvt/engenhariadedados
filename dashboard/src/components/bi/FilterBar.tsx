'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar, Check, ChevronDown, MapPin, Building2, Search, X } from 'lucide-react';
import { PRESETS, useFiltros } from './useFiltros';
import { data, empreendimentoCurto } from '../../lib/format';

function MultiSelect({
  icone,
  rotuloTodos,
  opcoes,
  selecionados,
  onChange,
  formatar = (s: string) => s,
}: {
  icone: React.ReactNode;
  rotuloTodos: string;
  opcoes: string[];
  selecionados: string[];
  onChange: (lista: string[]) => void;
  formatar?: (s: string) => string;
}) {
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fechar = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setAberto(false);
    };
    document.addEventListener('mousedown', fechar);
    return () => document.removeEventListener('mousedown', fechar);
  }, []);

  const filtradas = useMemo(
    () => opcoes.filter((o) => o.toLowerCase().includes(busca.trim().toLowerCase())),
    [opcoes, busca]
  );

  const rotulo =
    selecionados.length === 0
      ? rotuloTodos
      : selecionados.length === 1
      ? formatar(selecionados[0])
      : `${selecionados.length} selecionados`;

  const alternar = (o: string) =>
    onChange(selecionados.includes(o) ? selecionados.filter((s) => s !== o) : [...selecionados, o]);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setAberto((a) => !a)} className="controle max-w-[260px]" aria-expanded={aberto}>
        {icone}
        <span className="truncate">{rotulo}</span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
      </button>
      {aberto && (
        <div className="absolute z-40 mt-1 w-80 painel p-2 shadow-2xl">
          <div className="flex items-center gap-2 px-2 py-1.5 border-b border-slate-700 mb-1">
            <Search className="w-3.5 h-3.5 text-slate-500" />
            <input
              autoFocus
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar..."
              className="bg-transparent text-xs text-slate-200 outline-none w-full placeholder:text-slate-600"
            />
          </div>
          <div className="max-h-72 overflow-y-auto">
            {filtradas.map((o) => {
              const ativo = selecionados.includes(o);
              return (
                <button
                  key={o}
                  onClick={() => alternar(o)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left text-xs text-slate-200 hover:bg-slate-700/50"
                >
                  <span className="w-4 shrink-0">{ativo && <Check className="w-4 h-4 text-sky-400" strokeWidth={3} />}</span>
                  <span className="truncate" title={o}>
                    {formatar(o)}
                  </span>
                </button>
              );
            })}
            {filtradas.length === 0 && <p className="text-xs text-slate-500 px-2 py-3">Nada encontrado.</p>}
          </div>
          {selecionados.length > 0 && (
            <button onClick={() => onChange([])} className="w-full text-[11px] text-slate-400 hover:text-slate-200 border-t border-slate-700 mt-1 pt-2 pb-1">
              Limpar seleção
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function FilterBar({ empreendimentos, pracas }: { empreendimentos: string[]; pracas: string[] }) {
  const { filtros, preset, setPreset, setPersonalizado, setEmpreendimentos, setPracas, limpar } = useFiltros();

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="controle">
        <Calendar className="w-3.5 h-3.5 text-slate-400" />
        <select
          value={preset}
          onChange={(e) => setPreset(e.target.value as typeof preset)}
          className="bg-transparent outline-none text-xs text-slate-200 cursor-pointer"
          aria-label="Período"
        >
          {PRESETS.map((p) => (
            <option key={p.id} value={p.id} className="bg-slate-900">
              {p.label}
            </option>
          ))}
        </select>
      </label>

      {preset === 'personalizado' ? (
        <div className="controle">
          <input
            type="date"
            value={filtros.inicio}
            max={filtros.fim}
            onChange={(e) => e.target.value && setPersonalizado(e.target.value, filtros.fim)}
            className="bg-transparent outline-none text-xs text-slate-200 [color-scheme:dark]"
            aria-label="Data inicial"
          />
          <span className="text-slate-500">até</span>
          <input
            type="date"
            value={filtros.fim}
            min={filtros.inicio}
            onChange={(e) => e.target.value && setPersonalizado(filtros.inicio, e.target.value)}
            className="bg-transparent outline-none text-xs text-slate-200 [color-scheme:dark]"
            aria-label="Data final"
          />
        </div>
      ) : (
        <span className="text-[11px] text-slate-500">
          {data(filtros.inicio)} a {data(filtros.fim)}
        </span>
      )}

      <MultiSelect
        icone={<Building2 className="w-3.5 h-3.5 text-slate-400" />}
        rotuloTodos="Todos os empreendimentos"
        opcoes={empreendimentos}
        selecionados={filtros.empreendimentos}
        onChange={setEmpreendimentos}
        formatar={empreendimentoCurto}
      />
      <MultiSelect
        icone={<MapPin className="w-3.5 h-3.5 text-slate-400" />}
        rotuloTodos="Todas as praças"
        opcoes={pracas}
        selecionados={filtros.pracas}
        onChange={setPracas}
      />

      {(filtros.empreendimentos.length > 0 || filtros.pracas.length > 0) && (
        <button onClick={limpar} className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 px-2">
          <X className="w-3 h-3" /> Limpar filtros
        </button>
      )}
    </div>
  );
}
