export type OriginChannel = 'meta_ads' | 'google_ads' | 'rd_station' | 'beeviral' | 'sheets_bi' | 'cv_crm';

export type DivergenceType = 
  | 'MATCH_OK'
  | 'MISSING_IN_CV'
  | 'ORIGIN_MISMATCH'
  | 'VOLUME_GAP'
  | 'LATENCY_DELAY'
  | 'DUPLICATE_SOURCE'
  | 'PENDING_SYNC';

export type HealthStatus = 'HEALTHY' | 'WARNING' | 'CRITICAL';

export interface ChannelSummary {
  channel: OriginChannel;
  total_source_leads: number;
  total_cv_leads: number;
  match_ok_count: number;
  missing_in_cv_count: number;
  origin_mismatch_count: number;
  latency_delay_count: number;
  pending_sync_count: number;
  adherence_rate: number;
  health_status: HealthStatus;
}

export interface DivergenceRecord {
  id: string;
  source_lead_id: string;
  email?: string;
  phone?: string;
  origin_channel: OriginChannel;
  divergence_type: DivergenceType;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  details: string;
  source_created_at: string;
  cv_created_at?: string;
  origem_no_cv?: string;
  integration_id?: string;
}

export type SourceMode = 'real' | 'simulado' | 'erro' | 'nao_configurado';

export interface HelpLink {
  label: string;
  url: string;
}

/** Como uma fonte entregou os dados na análise — nunca apresentar simulação como real. */
export interface SourceStatus {
  source: string;
  label: string;
  mode: SourceMode;
  records: number;
  message: string;
  action?: string | null;
  help_links: HelpLink[];
  checked_at: string;
}

export interface SalesUploadInfo {
  filename: string;
  original_filename?: string;
  uploaded_at: string;
  rows: number;
  empreendimentos: string[];
  first_sale: string | null;
  last_sale: string | null;
  declared_online: number;
  without_empreendimento: number;
  empreendimentos_mapeados?: { planilha: string; oficial: string | null }[];
  empreendimentos_nao_reconhecidos?: string[];
  catalogo_disponivel?: boolean;
}

export interface GlobalReconciliationReport {
  execution_id: string;
  timestamp: string;
  start_date: string;
  end_date: string;
  total_source_leads: number;
  total_cv_leads: number;
  total_reconciled_ok: number;
  total_missing_in_cv: number;
  total_origin_mismatch: number;
  overall_adherence_rate: number;
  overall_health: HealthStatus;
  channels: ChannelSummary[];
  divergences: DivergenceRecord[];
  sales_audit?: SalesAuditReport | null;
  sources?: SourceStatus[];
  simulated_data?: boolean;
  /** false quando os leads do CV não puderam ser lidos */
  cv_available?: boolean;
}

// ============================================================================
// AUDITORIA DE VENDAS — cruzamento da base de Vendas x base de Leads
// ============================================================================

export type SaleVerdict =
  | 'ONLINE_CONFIRMED'
  | 'ONLINE_UNPROVEN'
  | 'ONLINE_NOT_DECLARED'
  | 'OFFLINE_CONFIRMED'
  | 'CHANNEL_MISMATCH'
  | 'LEAD_AFTER_SALE';

export type MatchKey = 'document' | 'integration_id' | 'email' | 'phone' | 'name' | 'none';

export interface SaleAuditRecord {
  sale_id: string;
  client_name?: string;
  document?: string;
  email?: string;
  phone?: string;
  sale_date: string;
  value?: number;
  empreendimento?: string;
  declared_channel_raw: string;
  declared_is_online: boolean;
  verified_is_online: boolean;
  verdict: SaleVerdict;
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'NONE';
  matched_by: MatchKey;
  matched_lead_id?: string;
  matched_channel?: OriginChannel;
  lead_created_at?: string;
  days_lead_to_sale?: number;
  lead_empreendimento?: string;
  /** true = lead do mesmo empreendimento; false = cliente migrou de produto; null = indeterminado */
  empreendimento_match?: boolean | null;
  details: string;
}

export interface EmpreendimentoAudit {
  empreendimento: string;

  total_leads: number;
  leads_by_channel: Record<string, number>;
  total_cv_leads: number;

  total_sales: number;
  total_value: number;

  declared_online: number;
  verified_online: number;
  online_delta: number;

  online_confirmed: number;
  online_unproven: number;
  online_not_declared: number;
  offline_confirmed: number;
  channel_mismatch: number;

  cross_empreendimento_sales: number;
  sales_without_lead: number;

  conversion_rate: number;
  attribution_accuracy: number;
  health_status: HealthStatus;
  is_consistent: boolean;
  inconsistencies: string[];

  sales: SaleAuditRecord[];
}

export interface SalesChannelAudit {
  channel: OriginChannel;
  declared_sales: number;
  verified_sales: number;
  delta: number;
}

export interface SalesAuditReport {
  start_date: string;
  end_date: string;
  attribution_window_days: number;

  total_sales: number;
  declared_online: number;
  declared_offline: number;
  verified_online: number;
  verified_offline: number;

  online_confirmed: number;
  online_unproven: number;
  online_not_declared: number;
  offline_confirmed: number;
  channel_mismatch: number;
  lead_after_sale: number;
  duplicate_buyers: number;

  online_delta: number;
  attribution_accuracy: number;
  health_status: HealthStatus;

  matched_by_document: number;
  matched_by_integration_id: number;
  matched_by_email: number;
  matched_by_phone: number;
  matched_by_name: number;
  unmatched: number;
  low_confidence_matches: number;

  empreendimentos: EmpreendimentoAudit[];
  leads_sem_empreendimento: number;
  vendas_sem_empreendimento: number;
  empreendimento_filtro?: string | null;
  sales_base_available?: boolean;

  channels: SalesChannelAudit[];
  sales: SaleAuditRecord[];
}
