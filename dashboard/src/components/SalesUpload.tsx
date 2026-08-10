'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Play,
} from 'lucide-react';
import { SalesUploadInfo, SourceStatus } from '../types';
import { fetchLatestSalesUpload, uploadSalesFile } from '../lib/dataService';

function formatDate(iso?: string | null) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('pt-BR');
  } catch {
    return iso;
  }
}

/**
 * Origem da base de vendas: mostra de onde as vendas vieram na última análise e
 * permite carregar a planilha comercial quando as reservas do CV não estão acessíveis.
 */
export const SalesUpload: React.FC<{
  salesStatus?: SourceStatus;
  onRequestRun: () => void;
}> = ({ salesStatus, onRequestRun }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [current, setCurrent] = useState<SalesUploadInfo | null>(null);
  const [justUploaded, setJustUploaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLatestSalesUpload()
      .then(setCurrent)
      .catch(() => setCurrent(null));
  }, []);

  async function handleFile(file?: File) {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const info = await uploadSalesFile(file);
      setCurrent(info);
      setJustUploaded(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  const baseOk = salesStatus?.mode === 'real';

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start space-x-3 min-w-0">
          <div
            className={`w-10 h-10 rounded-2xl border flex items-center justify-center shrink-0 ${
              baseOk ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'
            }`}
          >
            {baseOk ? <CheckCircle2 className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-white">Base de vendas</p>
            <p className="text-xs text-slate-400 mt-0.5 leading-relaxed break-words">
              {salesStatus?.message ?? 'Rode uma análise para ver de onde as vendas foram lidas.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <button
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors disabled:opacity-60"
          >
            {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UploadCloud className="w-3.5 h-3.5" />}
            <span>{uploading ? 'Lendo planilha...' : 'Carregar planilha de vendas'}</span>
          </button>
        </div>
      </div>

      {!baseOk && salesStatus?.action && (
        <p className="text-xs text-amber-200 bg-amber-500/5 border border-amber-500/20 rounded-xl p-3 leading-relaxed">
          {salesStatus.action}
        </p>
      )}

      {!baseOk && salesStatus && salesStatus.help_links.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {salesStatus.help_links.map((link) => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-300 hover:bg-sky-500/20 text-[11px] font-semibold transition-colors"
            >
              <span>{link.label}</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          ))}
        </div>
      )}

      {error && (
        <p className="text-xs text-rose-300 bg-rose-500/5 border border-rose-500/20 rounded-xl p-3 leading-relaxed">{error}</p>
      )}

      {current && (
        <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center space-x-2 min-w-0">
              <FileSpreadsheet className="w-4 h-4 text-sky-400 shrink-0" />
              <span className="text-xs font-semibold text-slate-200 truncate">
                {current.original_filename ?? current.filename}
              </span>
              <span className="text-[10px] text-slate-500 shrink-0">
                carregada em {new Date(current.uploaded_at).toLocaleString('pt-BR')}
              </span>
            </div>
            {justUploaded && (
              <button
                onClick={onRequestRun}
                className="btn-primary text-xs inline-flex items-center space-x-2"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Rodar análise com esta planilha</span>
              </button>
            )}
          </div>

          <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <Info label="Vendas" value={current.rows} />
            <Info label="Declaradas online" value={current.declared_online} />
            <Info label="Período da planilha" value={`${formatDate(current.first_sale)} – ${formatDate(current.last_sale)}`} />
            <Info label="Empreendimentos" value={current.empreendimentos.length} />
          </div>

          {current.empreendimentos_mapeados && current.empreendimentos_mapeados.length > 0 && (
            <div className="mt-4 space-y-1">
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wide">
                Empreendimento na planilha → nome oficial no CV
              </p>
              {current.empreendimentos_mapeados.map((m) => (
                <p key={m.planilha} className="text-[11px] text-slate-400">
                  {m.planilha} <span className="text-slate-600">→</span>{' '}
                  {m.oficial ? (
                    <span className="text-emerald-300">{m.oficial}</span>
                  ) : (
                    <span className="text-amber-300">
                      {current.catalogo_disponivel ? 'não reconhecido no CV — confira o nome' : 'catálogo do CV indisponível'}
                    </span>
                  )}
                </p>
              ))}
            </div>
          )}

          {current.without_empreendimento > 0 && (
            <p className="mt-3 text-[11px] text-amber-300">
              {current.without_empreendimento} venda(s) sem empreendimento — elas ficarão em "Não identificado".
            </p>
          )}
          {justUploaded && (
            <p className="mt-3 text-[11px] text-slate-400">
              Escolha na análise um período que cubra as datas da planilha; vendas fora do período não entram na conferência.
            </p>
          )}
        </div>
      )}

      {!current && (
        <p className="text-[11px] text-slate-500 leading-relaxed">
          Colunas reconhecidas: <strong>cliente</strong>, <strong>cpf</strong>, <strong>email</strong>,{' '}
          <strong>telefone</strong>, <strong>origem</strong>, <strong>data_venda</strong>, <strong>valor</strong>,{' '}
          <strong>empreendimento</strong>. CSV (vírgula ou ponto e vírgula) ou Excel.
        </p>
      )}
    </div>
  );
};

function Info({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wide">{label}</p>
      <p className="text-slate-200 font-semibold mt-0.5">{value}</p>
    </div>
  );
}
