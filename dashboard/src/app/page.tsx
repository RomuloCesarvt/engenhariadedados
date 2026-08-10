'use client';

import React, { useState } from 'react';
import { INITIAL_REPORT } from '../lib/mockData';
import { GlobalReconciliationReport } from '../types';
import {
  Activity,
  Search,
  BarChart3,
  AlertTriangle,
  ArrowLeft,
  Download,
  Users,
  CheckCircle2,
  XCircle,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Eye,
  Play,
  Sparkles,
  RefreshCw,
  Radio,
} from 'lucide-react';
import { TriggerAnalysisModal } from '../components/TriggerAnalysisModal';
import { LiveMonitor } from '../components/LiveMonitor';

type Screen = 'home' | 'diagnostico' | 'canais' | 'investigar' | 'monitor';

const channelNames: Record<string, string> = {
  meta_ads: 'Meta Ads (Facebook / Instagram)',
  google_ads: 'Google Ads',
  rd_station: 'RD Station',
  beeviral: 'BeeViral (Indicação)',
  sheets_bi: 'Planilhas / Eventos',
};

const channelColors: Record<string, string> = {
  meta_ads: '#3b82f6',
  google_ads: '#10b981',
  rd_station: '#8b5cf6',
  beeviral: '#f59e0b',
  sheets_bi: '#64748b',
};

export default function Home() {
  const [report, setReport] = useState<GlobalReconciliationReport>(INITIAL_REPORT);
  const [screen, setScreen] = useState<Screen>('home');
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  // ━━━ TELA HOME ━━━
  if (screen === 'home') {
    return (
      <div className="min-h-screen flex flex-col bg-[#0a0e1a]">
        <header className="px-6 pt-6 pb-4 flex items-center justify-between max-w-5xl mx-auto w-full">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">Auditor de Leads</h1>
              <p className="text-[11px] text-slate-500">Origens de Mídia vs CRM Construtor de Vendas</p>
            </div>
          </div>
        </header>

        <main className="flex-1 flex flex-col items-center justify-center px-6 -mt-4">
          <div className="w-full max-w-4xl bg-gradient-to-r from-sky-950/40 via-slate-900 to-indigo-950/40 border border-sky-500/20 rounded-3xl p-8 mb-8 text-center relative overflow-hidden shadow-2xl">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs font-semibold mb-4">
              <Sparkles className="w-3.5 h-3.5" />
              <span>APIs Conectadas: Meta Ads, BeeViral, RD Station, Google Ads</span>
            </div>

            <h2 className="text-2xl md:text-3xl font-extrabold text-white mb-3">
              Análise de Integridade de Leads
            </h2>
            <p className="text-xs md:text-sm text-slate-300 max-w-xl mx-auto mb-6 leading-relaxed">
              Clique no botão abaixo para buscar os leads das mídias ativas e cruzar com o CRM Construtor de Vendas.
            </p>

            <div className="flex items-center justify-center space-x-4">
              <button
                onClick={() => setIsModalOpen(true)}
                className="px-8 py-3.5 rounded-2xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-bold text-sm shadow-xl shadow-sky-500/25 transition-all transform hover:-translate-y-0.5 active:translate-y-0 flex items-center space-x-2"
              >
                <Play className="w-5 h-5 fill-current" />
                <span>EXECUTAR ANÁLISE AGORA</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-4xl w-full">
            <button onClick={() => setScreen('diagnostico')} className="menu-card text-left group">
              <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <BarChart3 className="w-6 h-6 text-sky-400" />
              </div>
              <h3 className="text-base font-bold text-white mb-1.5">Diagnóstico Geral</h3>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Ver percentual de leads integrados com sucesso no CRM CV.
              </p>
              <div className="flex items-center text-xs font-semibold text-sky-400 group-hover:text-sky-300 transition-colors">
                <span>Ver resumo</span>
                <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
              </div>
            </button>

            <button onClick={() => setScreen('canais')} className="menu-card text-left group">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <TrendingUp className="w-6 h-6 text-emerald-400" />
              </div>
              <h3 className="text-base font-bold text-white mb-1.5">Comparar Canais</h3>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Ver qual mídia está perdendo mais leads (Meta, Google, BeeViral, RD).
              </p>
              <div className="flex items-center text-xs font-semibold text-emerald-400 group-hover:text-emerald-300 transition-colors">
                <span>Ver comparativo</span>
                <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
              </div>
            </button>

            <button onClick={() => setScreen('investigar')} className="menu-card text-left group">
              <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <AlertTriangle className="w-6 h-6 text-rose-400" />
              </div>
              <h3 className="text-base font-bold text-white mb-1.5">Investigar Problemas</h3>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Ver lista completa de e-mails e telefones dos leads perdidos.
              </p>
              <div className="flex items-center text-xs font-semibold text-rose-400 group-hover:text-rose-300 transition-colors">
                <span>Ver leads perdidos</span>
                <ChevronRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
              </div>
            </button>
          </div>

          {/* Monitor ao Vivo — Card destacado */}
          <button onClick={() => setScreen('monitor')} className="w-full max-w-4xl mt-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-r from-rose-500/5 via-amber-500/5 to-emerald-500/5 rounded-2xl group-hover:from-rose-500/10 group-hover:via-amber-500/10 group-hover:to-emerald-500/10 transition-all duration-500" />
            <div className="relative flex items-center justify-between p-5 rounded-2xl border border-slate-800 group-hover:border-amber-500/30 transition-all">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-rose-500/20 to-amber-500/20 border border-amber-500/30 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Radio className="w-6 h-6 text-amber-400 monitor-pulse" />
                </div>
                <div className="text-left">
                  <h3 className="text-base font-bold text-white mb-0.5">Monitor ao Vivo</h3>
                  <p className="text-xs text-slate-400">Verificação automática em tempo real — cada lead novo é monitorado no CV</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span className="hidden sm:inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[11px] font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 connection-dot" />
                  <span>LIVE</span>
                </span>
                <ChevronRight className="w-5 h-5 text-slate-500 group-hover:text-amber-400 group-hover:translate-x-1 transition-all" />
              </div>
            </div>
          </button>
        </main>

        <footer className="text-center py-6">
          <p className="text-[11px] text-slate-600">
            Período analisado: {report.start_date} até {report.end_date}
          </p>
        </footer>

        <TriggerAnalysisModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onRunSuccess={(newReport) => setReport(newReport)}
        />
      </div>
    );
  }

  // ━━━ TELA: DIAGNÓSTICO GERAL ━━━
  if (screen === 'diagnostico') {
    const successRate = report.overall_adherence_rate;

    return (
      <div className="min-h-screen">
        <PageHeader
          title="Diagnóstico Geral"
          subtitle="Resumo da saúde da integração dos seus leads"
          onBack={() => setScreen('home')}
          onRun={() => setIsModalOpen(true)}
        />

        <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
          <div className="card p-8 text-center">
            <p className="text-sm text-slate-400 mb-2">De cada 100 leads captados nas suas mídias...</p>
            <div className="flex items-center justify-center space-x-1 mb-2">
              <span className="text-6xl font-extrabold text-emerald-400">{successRate}</span>
              <span className="text-3xl font-bold text-emerald-400/60">%</span>
            </div>
            <p className="text-sm text-slate-300">chegaram corretamente ao <strong>CRM Construtor de Vendas (CV)</strong></p>

            <div className="max-w-md mx-auto mt-6">
              <div className="w-full bg-slate-800 rounded-full h-3 overflow-hidden">
                <div
                  className="h-3 rounded-full progress-animated"
                  style={{
                    '--progress': `${successRate}%`,
                    background: successRate >= 90 ? '#10b981' : successRate >= 75 ? '#f59e0b' : '#f43f5e',
                  } as React.CSSProperties}
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Leads captados" value={report.total_source_leads} sublabel="Total de todas as mídias" icon={<Users className="w-4 h-4" />} color="sky" />
            <StatCard label="Chegaram no CRM" value={report.total_reconciled_ok} sublabel="Integrados com sucesso" icon={<CheckCircle2 className="w-4 h-4" />} color="emerald" />
            <StatCard label="Leads perdidos" value={report.total_missing_in_cv} sublabel="Não entraram no CV" icon={<XCircle className="w-4 h-4" />} color="rose" highlight={report.total_missing_in_cv > 0} />
            <StatCard label="Origem errada" value={report.total_origin_mismatch} sublabel="Mídia trocada no CV" icon={<AlertTriangle className="w-4 h-4" />} color="amber" />
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <button onClick={() => setScreen('canais')} className="btn-primary text-sm flex items-center justify-center space-x-2 flex-1">
              <TrendingUp className="w-4 h-4" />
              <span>Ver qual mídia está pior</span>
            </button>
            {report.total_missing_in_cv > 0 && (
              <button onClick={() => setScreen('investigar')} className="flex-1 bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 font-semibold text-sm px-6 py-3 rounded-xl transition-colors flex items-center justify-center space-x-2">
                <Eye className="w-4 h-4" />
                <span>Investigar leads perdidos</span>
              </button>
            )}
          </div>
        </main>

        <TriggerAnalysisModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onRunSuccess={(newReport) => setReport(newReport)}
        />
      </div>
    );
  }

  // ━━━ TELA: COMPARAR CANAIS ━━━
  if (screen === 'canais') {
    const sortedChannels = [...report.channels].sort((a, b) => a.adherence_rate - b.adherence_rate);

    return (
      <div className="min-h-screen">
        <PageHeader
          title="Comparar Canais"
          subtitle="Qual mídia está perdendo mais leads?"
          onBack={() => setScreen('home')}
          onRun={() => setIsModalOpen(true)}
        />

        <main className="max-w-5xl mx-auto px-6 py-8 space-y-4">
          {sortedChannels.map((ch) => {
            const barColor = channelColors[ch.channel] || '#64748b';
            const hasMissing = ch.missing_in_cv_count > 0;

            return (
              <div key={ch.channel} className="card p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: barColor }} />
                    <div>
                      <h4 className="text-sm font-bold text-white">{channelNames[ch.channel] || ch.channel}</h4>
                      <p className="text-[11px] text-slate-500">
                        {ch.total_source_leads} leads captados · {ch.match_ok_count} no CRM
                        {hasMissing && <span className="text-rose-400 ml-1"> · {ch.missing_in_cv_count} perdido(s)</span>}
                        {ch.origin_mismatch_count > 0 && <span className="text-amber-400 ml-1"> · {ch.origin_mismatch_count} origem errada</span>}
                        {ch.pending_sync_count > 0 && <span className="text-sky-400 ml-1"> · {ch.pending_sync_count} aguardando sincronização</span>}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className={`text-lg font-bold ${ch.adherence_rate >= 95 ? 'text-emerald-400' : ch.adherence_rate >= 80 ? 'text-amber-400' : 'text-rose-400'}`}>
                      {ch.adherence_rate}%
                    </span>
                    <p className="text-[10px] text-slate-500">aderência</p>
                  </div>
                </div>

                <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                  <div
                    className="h-2 rounded-full progress-animated"
                    style={{
                      '--progress': `${ch.adherence_rate}%`,
                      backgroundColor: ch.adherence_rate >= 95 ? '#10b981' : ch.adherence_rate >= 80 ? '#f59e0b' : '#f43f5e',
                    } as React.CSSProperties}
                  />
                </div>
              </div>
            );
          })}
        </main>

        <TriggerAnalysisModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onRunSuccess={(newReport) => setReport(newReport)}
        />
      </div>
    );
  }

  // ━━━ TELA: INVESTIGAR PROBLEMAS ━━━
  if (screen === 'investigar') {
    const filteredDivergences = report.divergences.filter((item) => {
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        (item.email && item.email.toLowerCase().includes(term)) ||
        (item.phone && item.phone.includes(term))
      );
    });

    const exportToCSV = () => {
      if (filteredDivergences.length === 0) return;
      const headers = ['E-mail', 'Telefone', 'Canal de Origem', 'Problema', 'Detalhes', 'Data da Captura'];
      const rows = filteredDivergences.map((d) => [
        d.email || '', d.phone || '', channelNames[d.origin_channel] || d.origin_channel,
        d.divergence_type === 'MISSING_IN_CV' ? 'Lead faltando no CRM' : d.divergence_type === 'ORIGIN_MISMATCH' ? 'Origem errada' : d.divergence_type === 'LATENCY_DELAY' ? 'Atraso na integração' : d.divergence_type,
        `"${d.details.replace(/"/g, '""')}"`, d.source_created_at,
      ]);
      const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
      const link = document.createElement('a');
      link.setAttribute('href', encodeURI(csvContent));
      link.setAttribute('download', `leads_com_problema_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };

    return (
      <div className="min-h-screen">
        <PageHeader
          title="Investigar Problemas"
          subtitle={`${report.divergences.length} leads com inconsistência detectada`}
          onBack={() => setScreen('home')}
          onRun={() => setIsModalOpen(true)}
          action={
            <button onClick={exportToCSV} className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors">
              <Download className="w-3.5 h-3.5" />
              <span>Baixar lista (CSV)</span>
            </button>
          }
        />

        <main className="max-w-5xl mx-auto px-6 py-8 space-y-4">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-4 top-3.5" />
            <input
              type="text"
              placeholder="Buscar por e-mail ou telefone..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-2xl pl-11 pr-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500/50 transition-colors"
            />
          </div>

          {filteredDivergences.map((item) => (
            <div key={item.id} className="card p-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2 mb-1">
                    <span className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/15 flex items-center space-x-1">
                      <XCircle className="w-3 h-3 inline" />
                      <span>{item.divergence_type === 'MISSING_IN_CV' ? 'Não chegou no CRM' : item.divergence_type === 'ORIGIN_MISMATCH' ? 'Origem trocada' : 'Chegou com atraso'}</span>
                    </span>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">
                      via {channelNames[item.origin_channel] || item.origin_channel}
                    </span>
                  </div>
                  <div className="mt-2">
                    <p className="text-sm font-semibold text-white">{item.email || 'E-mail não informado'}</p>
                    <p className="text-xs text-slate-400">{item.phone || 'Telefone não informado'}</p>
                  </div>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">{item.details}</p>
                </div>

                <div className="text-right shrink-0">
                  <p className="text-[10px] text-slate-500 uppercase font-semibold">Captado em</p>
                  <p className="text-xs text-slate-300 font-medium">
                    {new Date(item.source_created_at).toLocaleDateString('pt-BR')}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </main>

        <TriggerAnalysisModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onRunSuccess={(newReport) => setReport(newReport)}
        />
      </div>
    );
  }

  // ━━━ TELA: MONITOR AO VIVO ━━━
  if (screen === 'monitor') {
    return (
      <div className="min-h-screen">
        <PageHeader
          title="Monitor ao Vivo"
          subtitle="Verificação automática de leads em tempo real"
          onBack={() => setScreen('home')}
          action={
            <span className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[11px] font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 connection-dot" />
              <span>LIVE</span>
            </span>
          }
        />

        <main className="max-w-5xl mx-auto px-6 py-8">
          <LiveMonitor />
        </main>
      </div>
    );
  }

  return null;
}

function PageHeader({
  title,
  subtitle,
  onBack,
  onRun,
  action,
}: {
  title: string;
  subtitle: string;
  onBack: () => void;
  onRun?: () => void;
  action?: React.ReactNode;
}) {
  return (
    <header className="sticky top-0 z-30 bg-[#0a0e1a]/95 backdrop-blur-md border-b border-slate-800/60">
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBack}
            className="w-9 h-9 rounded-xl bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h2 className="text-base font-bold text-white">{title}</h2>
            <p className="text-[11px] text-slate-500">{subtitle}</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {action}
          {onRun && (
            <button
              onClick={onRun}
              className="btn-primary text-xs flex items-center space-x-2 shadow-md"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Executar Análise</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

function StatCard({
  label,
  value,
  sublabel,
  icon,
  color,
  highlight = false,
}: {
  label: string;
  value: number;
  sublabel: string;
  icon: React.ReactNode;
  color: 'sky' | 'emerald' | 'rose' | 'amber';
  highlight?: boolean;
}) {
  const colorMap = {
    sky: { bg: 'bg-sky-500/10', border: 'border-sky-500/20', text: 'text-sky-400' },
    emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400' },
    rose: { bg: 'bg-rose-500/10', border: 'border-rose-500/20', text: 'text-rose-400' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400' },
  };

  const c = colorMap[color];

  return (
    <div className={`${highlight ? 'card-danger' : 'card'} p-5`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-slate-400">{label}</span>
        <div className={`w-7 h-7 rounded-lg ${c.bg} border ${c.border} flex items-center justify-center ${c.text}`}>
          {icon}
        </div>
      </div>
      <div className={`text-2xl font-bold ${c.text}`}>{value}</div>
      <p className="text-[11px] text-slate-500 mt-1">{sublabel}</p>
    </div>
  );
}
