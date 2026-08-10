'use client';

/**
 * Lista de leads por trás de um número: a prova de cada indicador.
 * Sem nome, e-mail ou telefone — cada linha abre o lead no CV.
 */

import React, { useEffect, useState } from 'react';
import { ExternalLink, Loader2, X } from 'lucide-react';
import { fetchLeadsDetalhe } from '../../lib/biApi';
import { data, empreendimentoCurto, reais } from '../../lib/format';
import { Filtros, LeadsDetalheResponse } from '../../types/bi';
import { BadgeConfianca } from './ui';

export interface PedidoDetalhe {
  titulo: string;
  extra: {
    empreendimento?: string;
    canal?: string;
    grupo?: string;
    etapa_minima?: number;
    vendidos?: boolean;
    criterio?: 'interesse' | 'comprado';
    so_outro_empreendimento?: boolean;
  };
}

const LIGACAO: Record<string, string> = {
  lead_associado: 'Lead associado à reserva',
  email: 'E-mail do titular',
  telefone: 'Telefone do titular',
  sem_lead: 'Sem lead no CV',
};

export function Detalhe({ pedido, filtros, onFechar }: { pedido: PedidoDetalhe | null; filtros: Filtros; onFechar: () => void }) {
  const [resp, setResp] = useState<LeadsDetalheResponse | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!pedido) return;
    setResp(null);
    setErro(null);
    fetchLeadsDetalhe(filtros, { ...pedido.extra, limite: 1000 })
      .then(setResp)
      .catch((e: Error) => setErro(e.message));
  }, [pedido, filtros]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onFechar();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onFechar]);

  if (!pedido) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={pedido.titulo}>
      <div className="theme-modal-backdrop absolute inset-0 bg-black/60" onClick={onFechar} />
      <div className="theme-modal-panel relative w-full max-w-5xl h-full bg-[#0b1020] border-l border-slate-800 flex flex-col">
        <header className="theme-modal-header px-5 py-4 border-b border-slate-800 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-white">{pedido.titulo}</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {pedido.extra.vendidos ? 'Vendas' : 'Leads cadastrados'} de {data(filtros.inicio)} a {data(filtros.fim)}
              {resp && ` · ${resp.total.toLocaleString('pt-BR')} registro(s)`}
              {resp?.truncado && ' · mostrando os 1.000 mais recentes'}
            </p>
          </div>
          <button onClick={onFechar} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400" aria-label="Fechar">
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="flex-1 overflow-auto">
          {!resp && !erro && (
            <div className="p-10 text-center text-slate-400 text-xs">
              <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
              Carregando leads...
            </div>
          )}
          {erro && <p className="p-5 text-xs text-rose-300">{erro}</p>}
          {resp && pedido.extra.vendidos && (
            <table className="tabela">
              <thead className="theme-modal-table-head sticky top-0 bg-[#0b1020]">
                <tr>
                  <th>Venda</th>
                  <th>Unidade comprada</th>
                  <th>Interesse do lead</th>
                  <th>Origem do lead</th>
                  <th>Como a venda foi ligada ao lead</th>
                  <th className="text-right">Valor</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {resp.itens.map((l) => (
                  <tr key={l.idreserva ?? `lead-${l.id}`}>
                    <td className="whitespace-nowrap">{data(l.data_venda)}</td>
                    <td className="max-w-[200px]">
                      <span className="block truncate" title={l.empreendimento_comprado ?? l.empreendimento}>
                        {empreendimentoCurto(l.empreendimento_comprado ?? l.empreendimento)}
                      </span>
                      {l.unidade && <span className="block text-slate-500">{l.unidade}</span>}
                    </td>
                    <td className="max-w-[200px]">
                      <span className="block truncate" title={l.empreendimento}>
                        {l.ligacao === 'sem_lead' ? '—' : empreendimentoCurto(l.empreendimento)}
                      </span>
                      {l.outro_empreendimento && (
                        <span className="inline-block mt-0.5 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px]">
                          comprou em outro empreendimento
                        </span>
                      )}
                    </td>
                    <td className="max-w-[240px]">
                      <span className="block whitespace-nowrap">{l.canal_label}</span>
                      <span className="block text-slate-500">{l.evidencia}</span>
                    </td>
                    <td className="text-slate-400">
                      {l.ligacao ? LIGACAO[l.ligacao] : 'Data de venda do lead'}
                      {l.midia_reserva && <span className="block text-slate-500">Mídia na reserva: {l.midia_reserva}</span>}
                    </td>
                    <td className="num">{reais(l.valor_venda)}</td>
                    <td>
                      {l.link && (
                        <a href={l.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200 whitespace-nowrap">
                          Abrir lead no CV <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {resp && !pedido.extra.vendidos && (
            <table className="tabela">
              <thead className="theme-modal-table-head sticky top-0 bg-[#0b1020]">
                <tr>
                  <th>Cadastro</th>
                  <th>Empreendimento</th>
                  <th>Canal</th>
                  <th>Confiança</th>
                  <th>Por que foi classificado assim</th>
                  <th>Etapa alcançada</th>
                  <th>Situação no CV</th>
                  <th className="text-right">Valor</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {resp.itens.map((l) => (
                  <tr key={l.id ?? undefined}>
                    <td className="whitespace-nowrap">{data(l.data)}</td>
                    <td className="max-w-[180px] truncate" title={l.empreendimento}>
                      {empreendimentoCurto(l.empreendimento)}
                    </td>
                    <td className="whitespace-nowrap">{l.canal_label}</td>
                    <td>
                      <BadgeConfianca confianca={l.confianca} />
                    </td>
                    <td className="text-slate-400 max-w-[260px]">
                      {l.evidencia}
                      {l.campanha && <span className="block text-slate-500 truncate" title={l.campanha}>Campanha: {l.campanha}</span>}
                    </td>
                    <td className="whitespace-nowrap">{l.etapa_label}</td>
                    <td className="text-slate-400 whitespace-nowrap">
                      {l.situacao}
                      {l.motivo_perda && <span className="block text-slate-500">{l.motivo_perda}</span>}
                    </td>
                    <td className="num">{l.vendido ? reais(l.valor_venda) : '—'}</td>
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
          )}
          {resp && resp.total === 0 && <p className="p-10 text-center text-xs text-slate-400">Nenhum lead neste recorte.</p>}
        </div>
      </div>
    </div>
  );
}
