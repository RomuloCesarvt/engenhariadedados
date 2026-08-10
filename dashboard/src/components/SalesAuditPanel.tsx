'use client';

import React, { useMemo, useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowUpRight,
  ShoppingCart,
  Fingerprint,
  Search,
  Building2,
  Users,
  Shuffle,
} from 'lucide-react';
import {
  SalesAuditReport,
  SaleAuditRecord,
  SaleVerdict,
  MatchKey,
  EmpreendimentoAudit,
} from '../types';

const channelNames: Record<string, string> = {
  meta_ads: 'Meta Ads',
  google_ads: 'Google Ads',
  rd_station: 'RD Station',
  beeviral: 'BeeViral',
  sheets_bi: 'Planilhas / Eventos',
  cv_crm: 'CV CRM',
};

const matchKeyNames: Record<MatchKey, string> = {
  document: 'CPF/CNPJ',
  integration_id: 'ID de integração',
  email: 'e-mail',
  phone: 'telefone',
  name: 'nome (confiança baixa)',
  none: 'sem correspondência',
};

const verdictStyles: Record<
  SaleVerdict,
  { label: string; text: string; bg: string; border: string; icon: React.ReactNode }
> = {
  ONLINE_CONFIRMED: {
    label: 'Online comprovado',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  OFFLINE_CONFIRMED: {
    label: 'Offline coerente',
    text: 'text-slate-300',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/20',
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  ONLINE_UNPROVEN: {
    label: 'Online sem lead',
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/20',
    icon: <XCircle className="w-3.5 h-3.5" />,
  },
  ONLINE_NOT_DECLARED: {
    label: 'Online não declarado',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    icon: <ArrowUpRight className="w-3.5 h-3.5" />,
  },
  CHANNEL_MISMATCH: {
    label: 'Canal errado',
    text: 'text-violet-400',
    bg: 'bg-violet-500/10',
    border: 'border-violet-500/20',
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
  },
  LEAD_AFTER_SALE: {
    label: 'Lead após a venda',
    text: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/20',
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
  },
};

const problemVerdicts: SaleVerdict[] = [
  'ONLINE_UNPROVEN',
  'ONLINE_NOT_DECLARED',
  'CHANNEL_MISMATCH',
  'LEAD_AFTER_SALE',
];

type Filter = 'all' | 'problems';

function formatCurrency(value?: number) {
  if (value === undefined || value === null) return '—';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('pt-BR');
  } catch {
    return iso;
  }
}

/**
 * Painel de auditoria. A conferência é sempre por empreendimento: a aba "Consolidado"
 * existe só para dar o panorama, e os números que importam vivem em cada produto.
 */
export const SalesAuditPanel: React.FC<{ audit: SalesAuditReport }> = ({ audit }) => {
  const empreendimentos = audit.empreendimentos ?? [];
  // Abre já no primeiro empreendimento quando há só um — não faz sentido pedir
  // um clique para ver o único produto do período.
  const [selected, setSelected] = useState<string>(
    empreendimentos.length === 1 ? empreendimentos[0].empreendimento : '__all__'
  );

  const atual = empreendimentos.find((e) => e.empreendimento === selected);

  return (
    <div className="space-y-6">
      <EmpreendimentoSelector
        empreendimentos={empreendimentos}
        selected={selected}
        onSelect={setSelected}
        totalSales={audit.total_sales}
      />

      {atual ? (
        <EmpreendimentoView emp={atual} audit={audit} />
      ) : (
        <ConsolidadoView audit={audit} onSelect={setSelected} />
      )}
    </div>
  );
};

/* ─────────────────────────── Seletor de empreendimento ─────────────────────────── */

function EmpreendimentoSelector({
  empreendimentos,
  selected,
  onSelect,
  totalSales,
}: {
  empreendimentos: EmpreendimentoAudit[];
  selected: string;
  onSelect: (value: string) => void;
  totalSales: number;
}) {
  if (empreendimentos.length === 0) return null;

  return (
    <div className="card p-4">
      <div className="flex items-center space-x-2 mb-3">
        <Building2 className="w-4 h-4 text-sky-400" />
        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
          Empreendimento — a conferência é feita produto a produto
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onSelect('__all__')}
          className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-colors ${
            selected === '__all__'
              ? 'bg-sky-500 border-sky-500 text-white'
              : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
        >
          Consolidado ({totalSales} vendas)
        </button>

        {empreendimentos.map((emp) => {
          const ativo = selected === emp.empreendimento;
          return (
            <button
              key={emp.empreendimento}
              onClick={() => onSelect(emp.empreendimento)}
              className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-colors flex items-center space-x-2 ${
                ativo
                  ? 'bg-sky-500 border-sky-500 text-white'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  emp.is_consistent ? 'bg-emerald-400' : 'bg-rose-400'
                }`}
              />
              <span>{emp.empreendimento}</span>
              <span className={ativo ? 'text-sky-100' : 'text-slate-500'}>
                {emp.total_leads}L · {emp.total_sales}V
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ─────────────────────────── Visão de um empreendimento ─────────────────────────── */

function EmpreendimentoView({ emp, audit }: { emp: EmpreendimentoAudit; audit: SalesAuditReport }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return emp.sales.filter((sale) => {
      const matchesFilter = filter === 'all' || problemVerdicts.includes(sale.verdict);
      const matchesSearch =
        !term ||
        [sale.client_name, sale.email, sale.phone, sale.document, sale.sale_id]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(term));
      return matchesFilter && matchesSearch;
    });
  }, [emp.sales, filter, search]);

  const problemCount = emp.sales.filter((s) => problemVerdicts.includes(s.verdict)).length;
  const deltaSign = emp.online_delta > 0 ? '+' : '';

  return (
    <div className="space-y-6">
      {/* Veredito do empreendimento */}
      <div className={emp.is_consistent ? 'card p-6' : 'card-danger p-6'}>
        <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-sky-400" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">{emp.empreendimento}</h3>
              <p className="text-[11px] text-slate-500">
                {emp.total_leads} leads captados · {emp.total_sales} vendas · VGV{' '}
                {formatCurrency(emp.total_value)}
              </p>
            </div>
          </div>

          <span
            className={`px-3 py-1.5 rounded-full text-[11px] font-bold border ${
              emp.is_consistent
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
            }`}
          >
            {emp.is_consistent ? 'Conferência OK' : `${emp.inconsistencies.length} inconsistência(s)`}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-4">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              O relatório comercial diz
            </span>
            <p className="text-xl font-extrabold text-white mt-1">
              {emp.total_sales} vendas · <span className="text-sky-400">{emp.declared_online} online</span>
            </p>
          </div>
          <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-4">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              A base de leads deste empreendimento comprova
            </span>
            <p className="text-xl font-extrabold text-white mt-1">
              {emp.total_sales} vendas ·{' '}
              <span
                className={
                  emp.online_delta === 0
                    ? 'text-emerald-400'
                    : emp.online_delta < 0
                    ? 'text-rose-400'
                    : 'text-amber-400'
                }
              >
                {emp.verified_online} online
              </span>
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniStat
            label="Diferença no online"
            value={`${deltaSign}${emp.online_delta}`}
            tone={emp.online_delta === 0 ? 'neutral' : 'danger'}
          />
          <MiniStat
            label="Acurácia da atribuição"
            value={`${emp.attribution_accuracy}%`}
            tone={
              emp.health_status === 'HEALTHY'
                ? 'good'
                : emp.health_status === 'WARNING'
                ? 'warn'
                : 'danger'
            }
          />
          <MiniStat label="Leads → vendas" value={`${emp.conversion_rate}%`} tone="neutral" />
          <MiniStat
            label="Vendas mal atribuídas"
            value={problemCount}
            tone={problemCount ? 'danger' : 'good'}
          />
        </div>

        {emp.inconsistencies.length > 0 && (
          <div className="mt-4 space-y-2">
            {emp.inconsistencies.map((problema, i) => (
              <p
                key={i}
                className="text-xs text-amber-300 bg-amber-500/5 border border-amber-500/20 rounded-xl p-3 leading-relaxed"
              >
                {problema}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* Leads do empreendimento por canal */}
      {emp.total_leads > 0 && (
        <div className="card p-5">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center space-x-2">
            <Users className="w-4 h-4 text-sky-400" />
            <span>Leads captados para {emp.empreendimento}</span>
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {Object.entries(emp.leads_by_channel).map(([canal, qtd]) => (
              <div key={canal} className="rounded-xl bg-slate-900/60 border border-slate-800 px-4 py-3">
                <p className="text-[10px] text-slate-500 font-semibold">{channelNames[canal] ?? canal}</p>
                <p className="text-lg font-bold text-slate-200 mt-0.5">{qtd}</p>
              </div>
            ))}
          </div>
          {emp.total_cv_leads > 0 && (
            <p className="text-[11px] text-slate-500 mt-3">
              {emp.total_cv_leads} lead(s) também registrados no CV CRM para este empreendimento.
            </p>
          )}
        </div>
      )}

      {/* Composição dos vereditos */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <VerdictCard
          label="Online comprovado"
          count={emp.online_confirmed}
          verdict="ONLINE_CONFIRMED"
          description="Venda com lead digital anterior"
        />
        <VerdictCard
          label="Online sem lead"
          count={emp.online_unproven}
          verdict="ONLINE_UNPROVEN"
          description="Infla o online deste produto"
        />
        <VerdictCard
          label="Online não declarado"
          count={emp.online_not_declared}
          verdict="ONLINE_NOT_DECLARED"
          description="Online creditado ao offline"
        />
        <VerdictCard
          label="Canal errado"
          count={emp.channel_mismatch}
          verdict="CHANNEL_MISMATCH"
          description="Online certo, mídia errada"
        />
      </div>

      {emp.cross_empreendimento_sales > 0 && (
        <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-4 flex items-start space-x-3">
          <Shuffle className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
          <p className="text-xs text-violet-200 leading-relaxed">
            <strong>{emp.cross_empreendimento_sales} venda(s)</strong> deste empreendimento têm comprador
            que entrou por campanha de <strong>outro produto</strong>. A venda continua sendo online, mas a
            verba que gerou o lead foi investida em outra obra — vale conferir como o crédito está sendo
            lançado.
          </p>
        </div>
      )}

      {/* Venda a venda */}
      <div className="card p-5">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <ShoppingCart className="w-4 h-4 text-sky-400" />
            <span>
              Venda a venda em {emp.empreendimento} ({filtered.length})
            </span>
          </h3>

          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Cliente, e-mail, CPF..."
                className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-sky-500/50 w-48"
              />
            </div>
            <FilterButton active={filter === 'all'} onClick={() => setFilter('all')}>
              Todas
            </FilterButton>
            <FilterButton active={filter === 'problems'} onClick={() => setFilter('problems')}>
              Só divergências ({problemCount})
            </FilterButton>
          </div>
        </div>

        <div className="space-y-2">
          {filtered.map((sale) => (
            <SaleRow key={sale.sale_id} sale={sale} />
          ))}
          {filtered.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-8">
              {emp.total_sales === 0
                ? 'Nenhuma venda registrada para este empreendimento no período.'
                : 'Nenhuma venda para este filtro.'}
            </p>
          )}
        </div>
      </div>

      {audit.low_confidence_matches > 0 && (
        <p className="text-xs text-slate-400">
          ⚠ {audit.low_confidence_matches} correspondência(s) em toda a execução foram obtidas apenas pelo
          nome do cliente — confirme com CPF antes de considerar conclusivo.
        </p>
      )}
    </div>
  );
}

/* ─────────────────────────── Visão consolidada ─────────────────────────── */

function ConsolidadoView({
  audit,
  onSelect,
}: {
  audit: SalesAuditReport;
  onSelect: (value: string) => void;
}) {
  const empreendimentos = audit.empreendimentos ?? [];
  const inconsistentes = empreendimentos.filter((e) => !e.is_consistent);

  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              O relatório comercial diz
            </span>
            <p className="text-2xl font-extrabold text-white mt-1">
              {audit.total_sales} vendas ·{' '}
              <span className="text-sky-400">{audit.declared_online} online</span>
            </p>
          </div>
          <div className="text-right">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              A base de leads comprova
            </span>
            <p className="text-2xl font-extrabold text-white mt-1">
              {audit.total_sales} vendas ·{' '}
              <span
                className={
                  audit.online_delta === 0
                    ? 'text-emerald-400'
                    : audit.online_delta < 0
                    ? 'text-rose-400'
                    : 'text-amber-400'
                }
              >
                {audit.verified_online} online
              </span>
            </p>
          </div>
        </div>

        <p className="mt-4 text-xs text-slate-400 leading-relaxed">
          Este é o total somado de todos os empreendimentos — útil como panorama, mas é no produto que o
          erro aparece. {inconsistentes.length > 0
            ? `${inconsistentes.length} de ${empreendimentos.length} empreendimento(s) estão com inconsistência.`
            : 'Nenhum empreendimento apresenta inconsistência.'}
        </p>

        {(audit.leads_sem_empreendimento > 0 || audit.vendas_sem_empreendimento > 0) && (
          <div className="mt-4 space-y-2">
            {audit.leads_sem_empreendimento > 0 && (
              <p className="text-xs text-amber-300 bg-amber-500/5 border border-amber-500/20 rounded-xl p-3 leading-relaxed">
                {audit.leads_sem_empreendimento} lead(s) não puderam ser atribuídos a nenhum empreendimento —
                a campanha não nomeia o produto. Esses leads seguem valendo para provar a origem de uma
                venda, mas ficam de fora da contagem por produto.
              </p>
            )}
            {audit.vendas_sem_empreendimento > 0 && (
              <p className="text-xs text-rose-300 bg-rose-500/5 border border-rose-500/20 rounded-xl p-3 leading-relaxed">
                {audit.vendas_sem_empreendimento} venda(s) sem empreendimento informado na base de origem.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Quadro comparativo */}
      <div className="card p-5">
        <h3 className="text-sm font-bold text-white mb-4">Conferência por empreendimento</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[640px]">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-800">
                <th className="pb-2 font-semibold">Empreendimento</th>
                <th className="pb-2 font-semibold text-right">Leads</th>
                <th className="pb-2 font-semibold text-right">Vendas</th>
                <th className="pb-2 font-semibold text-right">Online decl.</th>
                <th className="pb-2 font-semibold text-right">Online compr.</th>
                <th className="pb-2 font-semibold text-right">Conversão</th>
                <th className="pb-2 font-semibold text-right">Situação</th>
              </tr>
            </thead>
            <tbody>
              {empreendimentos.map((emp) => (
                <tr
                  key={emp.empreendimento}
                  onClick={() => onSelect(emp.empreendimento)}
                  className="border-b border-slate-800/60 hover:bg-slate-800/30 cursor-pointer transition-colors"
                >
                  <td className="py-3 font-semibold text-slate-200">{emp.empreendimento}</td>
                  <td className="py-3 text-right text-slate-300 tabular-nums">{emp.total_leads}</td>
                  <td className="py-3 text-right text-slate-300 tabular-nums">{emp.total_sales}</td>
                  <td className="py-3 text-right text-sky-400 tabular-nums font-semibold">
                    {emp.declared_online}
                  </td>
                  <td
                    className={`py-3 text-right tabular-nums font-semibold ${
                      emp.online_delta === 0
                        ? 'text-emerald-400'
                        : emp.online_delta < 0
                        ? 'text-rose-400'
                        : 'text-amber-400'
                    }`}
                  >
                    {emp.verified_online}
                  </td>
                  <td className="py-3 text-right text-slate-400 tabular-nums">{emp.conversion_rate}%</td>
                  <td className="py-3 text-right">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                        emp.is_consistent
                          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                          : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                      }`}
                    >
                      {emp.is_consistent ? 'OK' : `${emp.inconsistencies.length} problema(s)`}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-slate-500 mt-3">Clique em uma linha para abrir a conferência do produto.</p>
      </div>
    </div>
  );
}

/* ─────────────────────────── Blocos reutilizados ─────────────────────────── */

function SaleRow({ sale }: { sale: SaleAuditRecord }) {
  const style = verdictStyles[sale.verdict];

  return (
    <div className={`rounded-xl border ${style.border} ${style.bg} p-4`}>
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="min-w-0">
          <div className="flex items-center space-x-2 flex-wrap">
            <span className="text-sm font-bold text-white">{sale.client_name ?? sale.sale_id}</span>
            <span
              className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${style.text} ${style.bg} border ${style.border}`}
            >
              {style.icon}
              <span>{style.label}</span>
            </span>
            {sale.empreendimento_match === false && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold text-violet-400 bg-violet-500/10 border border-violet-500/20">
                <Shuffle className="w-3 h-3" />
                <span>Outro empreendimento</span>
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 truncate">
            {sale.email ?? sale.phone ?? sale.document ?? 'sem contato informado'} ·{' '}
            {formatDate(sale.sale_date)} · {formatCurrency(sale.value)}
          </p>
        </div>

        <div className="text-right text-[11px] shrink-0">
          <p className="text-slate-400">
            declarado: <span className="text-slate-200 font-semibold">{sale.declared_channel_raw}</span>
          </p>
          <p className="text-slate-400">
            comprovado:{' '}
            <span className="text-slate-200 font-semibold">
              {sale.matched_channel ? channelNames[sale.matched_channel] ?? sale.matched_channel : 'nenhum lead'}
            </span>
          </p>
        </div>
      </div>

      <p className="text-[11px] text-slate-300 mt-3 leading-relaxed">{sale.details}</p>

      <div className="flex items-center space-x-3 mt-2 text-[10px] text-slate-500 flex-wrap">
        <span className="inline-flex items-center space-x-1">
          <Fingerprint className="w-3 h-3" />
          <span>
            {sale.matched_by === 'none'
              ? 'sem correspondência na base de leads'
              : `match por ${matchKeyNames[sale.matched_by]}`}
          </span>
        </span>
        {sale.matched_lead_id && <span>lead {sale.matched_lead_id}</span>}
        {sale.lead_empreendimento && <span>campanha de {sale.lead_empreendimento}</span>}
        {sale.days_lead_to_sale !== undefined && sale.days_lead_to_sale !== null && (
          <span>{sale.days_lead_to_sale}d entre lead e venda</span>
        )}
      </div>
    </div>
  );
}

function VerdictCard({
  label,
  count,
  verdict,
  description,
}: {
  label: string;
  count: number;
  verdict: SaleVerdict;
  description: string;
}) {
  const style = verdictStyles[verdict];
  return (
    <div className={`rounded-2xl border ${style.border} ${style.bg} p-4`}>
      <div className={`flex items-center space-x-1.5 ${style.text}`}>
        {style.icon}
        <span className="text-[11px] font-semibold">{label}</span>
      </div>
      <p className={`text-2xl font-extrabold mt-1.5 ${style.text}`}>{count}</p>
      <p className="text-[10px] text-slate-500 mt-0.5 leading-snug">{description}</p>
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: 'good' | 'warn' | 'danger' | 'neutral';
}) {
  const toneMap = {
    good: 'text-emerald-400',
    warn: 'text-amber-400',
    danger: 'text-rose-400',
    neutral: 'text-slate-200',
  };
  return (
    <div className="rounded-xl bg-slate-900/60 border border-slate-800 px-4 py-3">
      <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wide">{label}</p>
      <p className={`text-lg font-bold mt-0.5 ${toneMap[tone]}`}>{value}</p>
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-colors border ${
        active
          ? 'bg-sky-500 border-sky-500 text-white'
          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  );
}
