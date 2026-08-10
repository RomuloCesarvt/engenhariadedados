/**
 * Service Layer — Centraliza chamadas à API de Reconciliação.
 */

import { GlobalReconciliationReport, SalesAuditReport, SalesUploadInfo, SourceStatus } from '../types';

export interface ReportResponse {
  report: GlobalReconciliationReport;
  meta: {
    source: string;
    filePath?: string;
    historyCount?: number;
    readAt?: string;
    executedAt?: string;
    logs?: string;
  };
}

export interface ReportSummary {
  execution_id: string;
  timestamp: string;
  start_date: string;
  end_date: string;
  overall_adherence_rate: number;
  overall_health: string;
  total_source_leads: number;
  total_missing_in_cv: number;
  total_origin_mismatch: number;
  file_size: number;
  filename: string;
}

export interface ReportsListResponse {
  reports: ReportSummary[];
  total: number;
}

/**
 * Busca o relatório mais recente do disco (output/latest_report.json).
 */
export async function fetchLatestReport(): Promise<ReportResponse> {
  const res = await fetch('/api/reconcile', { cache: 'no-store' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Erro desconhecido' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Dispara uma nova análise de reconciliação via engine Python.
 */
export async function triggerAnalysis(
  startDate: string,
  endDate: string
): Promise<ReportResponse> {
  const res = await fetch('/api/reconcile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ startDate, endDate }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Erro desconhecido' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Lista o histórico de relatórios de reconciliação.
 */
export async function fetchReportHistory(): Promise<ReportsListResponse> {
  const res = await fetch('/api/reports', { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Busca um relatório específico pelo execution_id.
 */
export async function fetchReportById(id: string): Promise<{ report: GlobalReconciliationReport }> {
  const res = await fetch(`/api/reports?id=${encodeURIComponent(id)}`, { cache: 'no-store' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Erro desconhecido' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface SalesAuditResponse {
  sales_audit: SalesAuditReport;
  meta: {
    source: string;
    execution_id?: string;
    readAt?: string;
  };
}

/**
 * Busca apenas o bloco de auditoria de vendas do relatório mais recente.
 * O mesmo conteúdo já vem embutido em `report.sales_audit` de fetchLatestReport().
 */
export async function fetchLatestSalesAudit(): Promise<SalesAuditResponse> {
  const res = await fetch('/api/sales-audit', { cache: 'no-store' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Erro desconhecido' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface IntegrationsResponse {
  sources: SourceStatus[];
  checked: 'last_report' | 'live';
  execution_id?: string;
}

async function parseError(res: Response): Promise<never> {
  const err = await res.json().catch(() => ({ error: 'Erro desconhecido' }));
  throw new Error(err.error || err.detail || `HTTP ${res.status}`);
}

/**
 * Estado das integrações. `live=true` consulta cada API agora (leva alguns segundos);
 * sem ele, devolve o estado registrado na última análise.
 */
export async function fetchIntegrations(live = false): Promise<IntegrationsResponse> {
  const res = await fetch(`/api/integrations${live ? '?live=true' : ''}`, { cache: 'no-store' });
  if (!res.ok) return parseError(res);
  return res.json();
}

/** Envia a planilha de vendas (CSV/XLSX) usada quando as reservas do CV não estão acessíveis. */
export async function uploadSalesFile(file: File): Promise<SalesUploadInfo> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/sales/upload', { method: 'POST', body: form });
  if (!res.ok) return parseError(res);
  return res.json();
}

/** Planilha de vendas carregada mais recentemente, ou null se não houver. */
export async function fetchLatestSalesUpload(): Promise<SalesUploadInfo | null> {
  const res = await fetch('/api/sales/upload', { cache: 'no-store' });
  if (res.status === 404) return null;
  if (!res.ok) return parseError(res);
  return res.json();
}
