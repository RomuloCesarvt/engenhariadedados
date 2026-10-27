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
}

export type SourceState = 'live' | 'simulated' | 'not_configured' | 'error';

export interface SourceStatus {
  source: string;
  status: SourceState;
  detail?: string | null;
  count: number;
}

export interface EngineReport {
  saved_at: string | null;
  report: GlobalReconciliationReport | null;
  sources: SourceStatus[];
}

export interface EngineHealth {
  ok: boolean;
  persistence: { kind: string; persistent: boolean };
  simulation_allowed: boolean;
  monitor_mode: 'demo' | 'production';
  sources_configured: Record<string, boolean>;
}
