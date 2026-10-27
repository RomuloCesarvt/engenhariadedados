/**
 * Cliente do dashboard para a API do motor (Python). As chamadas passam pelo proxy
 * /api/engine, que adiciona a chave da API no servidor — ela nunca chega ao navegador.
 */

import { EngineHealth, EngineReport, GlobalReconciliationReport } from '../types';

export class EngineError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export async function engineFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/engine/${path}`, { cache: 'no-store', ...init });
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {}
    throw new EngineError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const fetchLatestReport = () => engineFetch<EngineReport>('report/latest');

export const fetchHealth = () => engineFetch<EngineHealth>('health');

export const runReconciliation = (startDate: string, endDate: string) =>
  engineFetch<EngineReport>('reconcile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_date: startDate, end_date: endDate }),
  });

/** Relatório vazio, usado antes da primeira análise. */
export const EMPTY_REPORT: GlobalReconciliationReport = {
  execution_id: '',
  timestamp: '',
  start_date: '',
  end_date: '',
  total_source_leads: 0,
  total_cv_leads: 0,
  total_reconciled_ok: 0,
  total_missing_in_cv: 0,
  total_origin_mismatch: 0,
  overall_adherence_rate: 0,
  overall_health: 'HEALTHY',
  channels: [],
  divergences: [],
};
