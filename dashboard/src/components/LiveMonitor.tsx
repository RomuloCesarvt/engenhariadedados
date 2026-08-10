import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Radio,
  Wifi,
  WifiOff,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Loader2,
  RefreshCw,
  Zap,
  Eye,
  Mail,
  Phone,
  Tag,
  Signal,
  Pause,
  Play,
} from 'lucide-react';

// ━━━ Types ━━━
interface TrackedLead {
  lead_id: string;
  email?: string;
  phone?: string;
  email_clean?: string;
  phone_clean?: string;
  origin_channel: string;
  campaign_name?: string;
  source_created_at: string;
  detected_at: string;
  status: 'WAITING' | 'FOUND' | 'LOST' | 'MISMATCH';
  cv_data?: {
    cv_id: string;
    origem_cv: string;
    midia_cv?: string;
    created_at: string;
  };
  cv_origin?: string;
  attempts: number;
  last_check_at?: string;
  resolved_at?: string;
}

interface MonitorStats {
  total: number;
  waiting: number;
  found: number;
  lost: number;
  mismatch: number;
}

interface LiveMonitorProps {
  backendUrl?: string;
}

// ━━━ Helpers ━━━
const channelNames: Record<string, string> = {
  meta_ads: 'Meta Ads',
  google_ads: 'Google Ads',
  rd_station: 'RD Station',
  beeviral: 'BeeViral',
  sheets_bi: 'Planilhas',
};

const channelColors: Record<string, string> = {
  meta_ads: '#3b82f6',
  google_ads: '#10b981',
  rd_station: '#8b5cf6',
  beeviral: '#f59e0b',
  sheets_bi: '#64748b',
};

const channelBgColors: Record<string, string> = {
  meta_ads: 'rgba(59, 130, 246, 0.1)',
  google_ads: 'rgba(16, 185, 129, 0.1)',
  rd_station: 'rgba(139, 92, 246, 0.1)',
  beeviral: 'rgba(245, 158, 11, 0.1)',
  sheets_bi: 'rgba(100, 116, 139, 0.1)',
};

function formatElapsedTime(isoDate: string): string {
  const diff = (Date.now() - new Date(isoDate).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s atrás`;
  if (diff < 3600) return `${Math.floor(diff / 60)}min ${Math.floor(diff % 60)}s atrás`;
  return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}min atrás`;
}

function formatCountdown(isoDate: string, maxSeconds: number = 600): string {
  const elapsed = (Date.now() - new Date(isoDate).getTime()) / 1000;
  const remaining = Math.max(0, maxSeconds - elapsed);
  const min = Math.floor(remaining / 60);
  const sec = Math.floor(remaining % 60);
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

function getProgressPercent(isoDate: string, maxSeconds: number = 600): number {
  const elapsed = (Date.now() - new Date(isoDate).getTime()) / 1000;
  return Math.min(100, (elapsed / maxSeconds) * 100);
}

// ━━━ Component ━━━
export const LiveMonitor: React.FC<LiveMonitorProps> = ({ backendUrl = 'http://localhost:8765' }) => {
  const [leads, setLeads] = useState<TrackedLead[]>([]);
  const [stats, setStats] = useState<MonitorStats>({ total: 0, waiting: 0, found: 0, lost: 0, mismatch: 0 });
  const [connected, setConnected] = useState(false);
  const [mode, setMode] = useState<'demo' | 'production'>('demo');
  const [isPaused, setIsPaused] = useState(false);
  const [, setTick] = useState(0); // Force re-render for timers
  const eventSourceRef = useRef<EventSource | null>(null);
  const pausedRef = useRef(false);

  // Keep ref in sync for use inside callbacks
  useEffect(() => {
    pausedRef.current = isPaused;
  }, [isPaused]);

  // Timer tick every second for countdown updates
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  // SSE Connection
  const connectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`${backendUrl}/api/monitor/stream`);
    eventSourceRef.current = es;

    es.addEventListener('initial', (e) => {
      try {
        const data = JSON.parse(e.data);
        setLeads(data.leads || []);
        setStats(data.stats || { total: 0, waiting: 0, found: 0, lost: 0, mismatch: 0 });
        setMode(data.mode || 'demo');
        setConnected(true);
      } catch {}
    });

    es.addEventListener('lead_new', (e) => {
      if (pausedRef.current) return;
      try {
        const lead: TrackedLead = JSON.parse(e.data);
        setLeads((prev) => [lead, ...prev.filter((l) => l.lead_id !== lead.lead_id)]);
      } catch {}
    });

    es.addEventListener('lead_update', (e) => {
      if (pausedRef.current) return;
      try {
        const lead: TrackedLead = JSON.parse(e.data);
        setLeads((prev) =>
          prev.map((l) => (l.lead_id === lead.lead_id ? lead : l))
        );
      } catch {}
    });

    es.addEventListener('stats', (e) => {
      try {
        setStats(JSON.parse(e.data));
      } catch {}
    });

    es.addEventListener('reset', () => {
      setLeads([]);
      setStats({ total: 0, waiting: 0, found: 0, lost: 0, mismatch: 0 });
    });

    es.addEventListener('heartbeat', () => {
      // Keep-alive
    });

    es.onerror = () => {
      setConnected(false);
    };

    es.onopen = () => {
      setConnected(true);
    };
  }, [backendUrl]);

  useEffect(() => {
    connectSSE();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [connectSSE]);

  const handleReset = async () => {
    try {
      await fetch(`${backendUrl}/api/monitor/reset`);
    } catch {}
  };

  // ━━━ Render ━━━
  return (
    <div className="space-y-6">
      {/* Connection Banner */}
      <div className={`flex items-center justify-between p-4 rounded-2xl border ${
        connected
          ? 'bg-emerald-500/5 border-emerald-500/20'
          : 'bg-rose-500/5 border-rose-500/20'
      }`}>
        <div className="flex items-center space-x-3">
          <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${
            connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
          }`}>
            {connected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
          </div>
          <div>
            <span className={`text-xs font-bold ${connected ? 'text-emerald-400' : 'text-rose-400'}`}>
              {connected ? 'CONECTADO' : 'DESCONECTADO'}
            </span>
            <p className="text-[10px] text-slate-500">
              {connected
                ? `Modo ${mode === 'demo' ? 'DEMO (dados simulados)' : 'PRODUÇÃO (APIs reais)'} · Polling a cada 60s`
                : 'Inicie o backend: uvicorn engine.lead_monitor:app --port 8765'}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`p-2 rounded-xl text-xs font-medium transition-colors ${
              isPaused
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-white'
            }`}
            title={isPaused ? 'Retomar atualizações' : 'Pausar atualizações'}
          >
            {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={handleReset}
            className="p-2 rounded-xl bg-slate-800 text-slate-400 border border-slate-700 hover:text-white transition-colors"
            title="Limpar monitor"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatsCard label="Total" value={stats.total} icon={<Eye className="w-4 h-4" />} color="slate" />
        <StatsCard label="Aguardando CV" value={stats.waiting} icon={<Clock className="w-4 h-4" />} color="amber" pulse={stats.waiting > 0} />
        <StatsCard label="Confirmados" value={stats.found} icon={<CheckCircle2 className="w-4 h-4" />} color="emerald" />
        <StatsCard label="Perdidos" value={stats.lost} icon={<XCircle className="w-4 h-4" />} color="rose" highlight={stats.lost > 0} />
        <StatsCard label="Origem errada" value={stats.mismatch} icon={<AlertTriangle className="w-4 h-4" />} color="amber" />
      </div>

      {/* Live Feed */}
      <div className="space-y-3">
        <div className="flex items-center space-x-2 mb-1">
          <Radio className="w-4 h-4 text-rose-500 monitor-pulse" />
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Feed ao Vivo</span>
          {isPaused && (
            <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-[10px] font-bold border border-amber-500/20">
              PAUSADO
            </span>
          )}
        </div>

        {leads.length === 0 && (
          <div className="card p-12 text-center">
            <Loader2 className="w-8 h-8 text-sky-400 animate-spin mx-auto mb-4" />
            <p className="text-sm text-slate-300 font-medium">Aguardando leads das fontes de mídia...</p>
            <p className="text-xs text-slate-500 mt-1">Os leads aparecerão aqui automaticamente conforme forem detectados.</p>
          </div>
        )}

        {leads.map((lead, index) => (
          <LeadCard key={lead.lead_id} lead={lead} isNew={index === 0 && lead.status === 'WAITING'} />
        ))}
      </div>
    </div>
  );
};

// ━━━ Sub-Components ━━━

function StatsCard({
  label,
  value,
  icon,
  color,
  pulse = false,
  highlight = false,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: 'slate' | 'amber' | 'emerald' | 'rose';
  pulse?: boolean;
  highlight?: boolean;
}) {
  const colorMap = {
    slate: { bg: 'bg-slate-500/10', border: 'border-slate-500/20', text: 'text-slate-400' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400' },
    emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400' },
    rose: { bg: 'bg-rose-500/10', border: 'border-rose-500/20', text: 'text-rose-400' },
  };
  const c = colorMap[color];

  return (
    <div className={`${highlight ? 'card-danger' : 'card'} p-4 ${pulse ? 'monitor-pulse-border' : ''}`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-semibold text-slate-500 uppercase">{label}</span>
        <div className={`w-6 h-6 rounded-lg ${c.bg} border ${c.border} flex items-center justify-center ${c.text}`}>
          {icon}
        </div>
      </div>
      <div className={`text-2xl font-bold ${c.text}`}>{value}</div>
    </div>
  );
}

function LeadCard({ lead, isNew }: { lead: TrackedLead; isNew: boolean }) {
  const chColor = channelColors[lead.origin_channel] || '#64748b';
  const chBg = channelBgColors[lead.origin_channel] || 'rgba(100,116,139,0.1)';
  const chName = channelNames[lead.origin_channel] || lead.origin_channel;

  const statusConfig = {
    WAITING: {
      icon: <Loader2 className="w-4 h-4 animate-spin" />,
      label: 'Aguardando CV...',
      bg: 'bg-amber-500/5',
      border: 'border-amber-500/20',
      text: 'text-amber-400',
      badgeBg: 'bg-amber-500/10',
    },
    FOUND: {
      icon: <CheckCircle2 className="w-4 h-4" />,
      label: 'Caiu no CV!',
      bg: 'bg-emerald-500/5',
      border: 'border-emerald-500/30',
      text: 'text-emerald-400',
      badgeBg: 'bg-emerald-500/10',
    },
    LOST: {
      icon: <XCircle className="w-4 h-4" />,
      label: 'Não caiu no CV',
      bg: 'bg-rose-500/5',
      border: 'border-rose-500/30',
      text: 'text-rose-400',
      badgeBg: 'bg-rose-500/10',
    },
    MISMATCH: {
      icon: <AlertTriangle className="w-4 h-4" />,
      label: 'Origem errada',
      bg: 'bg-amber-500/5',
      border: 'border-amber-500/30',
      text: 'text-amber-400',
      badgeBg: 'bg-amber-500/10',
    },
  };

  const sc = statusConfig[lead.status];

  return (
    <div
      className={`rounded-2xl border p-4 transition-all duration-500 ${sc.bg} ${sc.border} ${
        isNew ? 'animate-slide-in' : ''
      } ${lead.status === 'FOUND' ? 'lead-found-flash' : ''} ${
        lead.status === 'LOST' ? 'lead-lost-flash' : ''
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Left: Lead Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center flex-wrap gap-2 mb-2">
            {/* Status Badge */}
            <span className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold ${sc.badgeBg} ${sc.text} border ${sc.border}`}>
              {sc.icon}
              <span>{sc.label}</span>
            </span>

            {/* Channel Badge */}
            <span
              className="px-2.5 py-1 rounded-lg text-[11px] font-bold border"
              style={{
                backgroundColor: chBg,
                color: chColor,
                borderColor: `${chColor}33`,
              }}
            >
              {chName}
            </span>

            {/* Attempts */}
            {lead.status === 'WAITING' && lead.attempts > 0 && (
              <span className="text-[10px] text-slate-500 font-medium">
                {lead.attempts}x verificado
              </span>
            )}
          </div>

          {/* Contact Info */}
          <div className="space-y-1">
            {lead.email && (
              <div className="flex items-center space-x-2">
                <Mail className="w-3 h-3 text-slate-500 shrink-0" />
                <span className="text-sm font-medium text-slate-200 truncate">{lead.email}</span>
              </div>
            )}
            {lead.phone && (
              <div className="flex items-center space-x-2">
                <Phone className="w-3 h-3 text-slate-500 shrink-0" />
                <span className="text-xs text-slate-400">{lead.phone}</span>
              </div>
            )}
            {lead.campaign_name && (
              <div className="flex items-center space-x-2">
                <Tag className="w-3 h-3 text-slate-600 shrink-0" />
                <span className="text-[11px] text-slate-500">{lead.campaign_name}</span>
              </div>
            )}
          </div>

          {/* CV Details (when found or mismatch) */}
          {(lead.status === 'FOUND' || lead.status === 'MISMATCH') && lead.cv_data && (
            <div className={`mt-2 p-2.5 rounded-xl border text-[11px] ${
              lead.status === 'FOUND'
                ? 'bg-emerald-500/5 border-emerald-500/15 text-emerald-300'
                : 'bg-amber-500/5 border-amber-500/15 text-amber-300'
            }`}>
              {lead.status === 'FOUND' ? (
                <span>✅ Registrado no CV como <strong>{lead.cv_origin}</strong> (ID: {lead.cv_data.cv_id})</span>
              ) : (
                <span>⚠️ Lead veio do <strong>{chName}</strong>, mas está registrado no CV como <strong>&quot;{lead.cv_origin}&quot;</strong></span>
              )}
            </div>
          )}

          {lead.status === 'LOST' && (
            <div className="mt-2 p-2.5 rounded-xl border bg-rose-500/5 border-rose-500/15 text-rose-300 text-[11px]">
              ❌ Após 10 minutos de monitoramento, este lead não foi encontrado no CRM Construtor de Vendas.
            </div>
          )}
        </div>

        {/* Right: Time Info */}
        <div className="shrink-0 text-right sm:min-w-[130px]">
          {lead.status === 'WAITING' && (
            <div className="space-y-1.5">
              <div className="text-[10px] text-slate-500 uppercase font-semibold">Tempo restante</div>
              <div className="text-lg font-bold text-amber-400 font-mono monitor-pulse">
                {formatCountdown(lead.detected_at)}
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="h-1.5 rounded-full bg-gradient-to-r from-amber-500 to-rose-500 transition-all duration-1000"
                  style={{ width: `${getProgressPercent(lead.detected_at)}%` }}
                />
              </div>
            </div>
          )}

          <div className={`${lead.status === 'WAITING' ? 'mt-2' : ''}`}>
            <p className="text-[10px] text-slate-500 uppercase font-semibold">Detectado</p>
            <p className="text-xs text-slate-400 font-medium">{formatElapsedTime(lead.detected_at)}</p>
          </div>

          {lead.resolved_at && (
            <div className="mt-1">
              <p className="text-[10px] text-slate-500 uppercase font-semibold">
                {lead.status === 'FOUND' ? 'Confirmado em' : lead.status === 'LOST' ? 'Expirado em' : 'Detectado em'}
              </p>
              <p className="text-xs text-slate-400 font-medium">{formatElapsedTime(lead.resolved_at)}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
