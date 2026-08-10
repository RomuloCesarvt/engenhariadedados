'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { AlternarVisao, Aviso, Card, ErroCarga, StatTile } from '../../components/bi/ui';
import { FunilChart, LeadsPorGrupoChart } from '../../components/bi/charts';
import { Detalhe, PedidoDetalhe } from '../../components/bi/Detalhe';
import { fetchBI } from '../../lib/biApi';
import { empreendimentoCurto, numero, pct, reais, reaisCompacto, reaisCentavos } from '../../lib/format';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Empreendimentos" subtitulo="Cada produto com seus leads, canais, funil, vendas e custo">
        <Empreendimentos />
      </AppShell>
    </Suspense>
  );
}

function Empreendimentos() {
  const { filtros, chave, setEmpreendimentos } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchBI(filtros), [chave, versao]);
  const [modo, setModo] = useState<'grafico' | 'tabela'>('grafico');
  const [modoFunil, setModoFunil] = useState<'grafico' | 'tabela'>('grafico');
  const [detalhe, setDetalhe] = useState<PedidoDetalhe | null>(null);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Calculando...</p>;

  const umSo = filtros.empreendimentos.length === 1 ? dados.por_empreendimento.find((e) => e.empreendimento === filtros.empreendimentos[0]) : null;
  const k = dados.kpis;

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      {!umSo && (
        <Aviso>Selecione um empreendimento na tabela (ou no filtro acima) para abrir a análise completa do produto.</Aviso>
      )}

      {umSo && (
        <>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="text-xs text-slate-400">{umSo.praca}</p>
              <h2 className="text-xl font-semibold text-white">{empreendimentoCurto(umSo.empreendimento)}</h2>
            </div>
            <button onClick={() => setEmpreendimentos([])} className="botao-secundario">
              Voltar para todos
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
            <StatTile destaque label="Interesses online cadastrados" valor={numero(k.online)} delta={k.variacao.online} sub="data de cadastro no CV" onClick={() => setDetalhe({ titulo: 'Leads', extra: {} })} />
            <StatTile label="Pessoas únicas" valor={numero(k.pessoas_unicas)} sub={`${numero(k.interesses_adicionais)} interesse(s) adicional(is)`} />
            <StatTile label="Última conversão no período" valor={numero(k.ultima_conversao_pessoas)} sub="sinal de conferência, não histórico completo" />
            <StatTile label="Vendas online" valor={numero(k.vendas)} delta={k.variacao.vendas} sub={`leads deste produto (regra do BI) · ${reaisCompacto(k.vgv)}`} onClick={() => setDetalhe({ titulo: 'Vendas dos leads deste empreendimento', extra: { vendidos: true } })} />
            <StatTile
              label="Unidades vendidas online"
              valor={numero(k.unidades_vendidas)}
              sub={`vendidas neste produto · ${reaisCompacto(k.vgv_unidades)}`}
              onClick={() => setDetalhe({ titulo: 'Unidades vendidas online neste empreendimento', extra: { vendidos: true, criterio: 'comprado' } })}
            />
            <StatTile label="Conversão (coorte online)" valor={pct(k.conversao_coorte_online)} sub="leads online do período que já venderam" />
            <StatTile
              label="Custo por lead Meta (CRM)"
              valor={umSo.cpl_meta_crm ? reaisCentavos(umSo.cpl_meta_crm) : '—'}
              sub={umSo.investimento_meta ? `${reais(umSo.investimento_meta)} investidos` : 'investimento não conectado'}
              subirEBom={false}
            />
          </div>

          <Aviso>
            Compare a mesma definição: este painel usa <strong>data de cadastro</strong> e o interesse oficial atual do CV.
            Relatórios baseados em conversões ou mudanças de etapa terão outro total.{' '}
            <Link href="/diagnosticos" className="underline text-amber-200">Ver divergências conhecidas dos Power BIs</Link>.
          </Aviso>

          {umSo.empreendimento.endsWith('16103') && (
            <Aviso>
              O Power BI FM&amp;D está com a chave do Novo Horizonte inconsistente: a tabela associa os dados ao código
              <strong> 16101</strong>, mas o filtro oferece o código oficial <strong>16103</strong> e retorna zero ao selecioná-lo.
            </Aviso>
          )}

          <div className="grid xl:grid-cols-2 gap-5">
            <Card titulo="Leads por origem" acao={<AlternarVisao modo={modo} setModo={setModo} />}>
              <LeadsPorGrupoChart serie={dados.serie} modo={modo} />
            </Card>
            <Card titulo="Funil dos leads online" acao={<AlternarVisao modo={modoFunil} setModo={setModoFunil} />}>
              <FunilChart etapas={dados.funil.online} modo={modoFunil} onClickEtapa={(n) => setDetalhe({ titulo: dados.funil.online[n].label, extra: { etapa_minima: n } })} />
            </Card>
          </div>

          <Card titulo="Canais deste empreendimento">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Canal</th>
                  <th className="text-right">Leads</th>
                  <th className="text-right">%</th>
                  <th className="text-right">Vendas</th>
                  <th className="text-right">Conversão (coorte)</th>
                </tr>
              </thead>
              <tbody>
                {dados.por_canal.map((c) => (
                  <tr key={c.chave} className="cursor-pointer hover:bg-slate-800/40" onClick={() => setDetalhe({ titulo: c.label, extra: { canal: c.chave } })}>
                    <td>{c.label}</td>
                    <td className="num">{numero(c.leads)}</td>
                    <td className="num">{pct(c.pct_leads)}</td>
                    <td className="num">{numero(c.vendas)}</td>
                    <td className="num">{pct(c.conversao_coorte)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}

      <Card titulo={umSo ? 'Comparar com os demais' : 'Todos os empreendimentos'} subtitulo="Clique em uma linha para abrir o empreendimento">
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Empreendimento</th>
                <th>Praça</th>
                <th className="text-right">Leads online</th>
                <th className="text-right">Meta</th>
                <th className="text-right">Google</th>
                <th className="text-right">Vendas online</th>
                <th className="text-right">VGV online</th>
                <th className="text-right" title="Vendidas neste empreendimento com origem online comprovada">Unidades online</th>
                <th className="text-right">Conversão</th>
                <th className="text-right">Invest. Meta</th>
                <th className="text-right">CPL Meta (CRM)</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_empreendimento.map((e) => (
                <tr
                  key={e.empreendimento}
                  className={`cursor-pointer hover:bg-slate-800/40 ${umSo?.empreendimento === e.empreendimento ? 'bg-sky-500/5' : ''}`}
                  onClick={() => setEmpreendimentos([e.empreendimento])}
                >
                  <td className="font-medium text-slate-100" title={e.empreendimento}>
                    {empreendimentoCurto(e.empreendimento)}
                  </td>
                  <td className="text-slate-400">{e.praca}</td>
                  <td className="num">{numero(e.leads)}</td>
                  <td className="num">{numero(e.meta)}</td>
                  <td className="num">{numero(e.google)}</td>
                  <td className="num">{numero(e.vendas)}</td>
                  <td className="num">{e.vgv ? reaisCompacto(e.vgv) : '—'}</td>
                  <td className="num">{numero(e.unidades_vendidas)}</td>
                  <td className="num">{pct(e.conversao_coorte)}</td>
                  <td className="num">{e.investimento_meta ? reaisCompacto(e.investimento_meta) : '—'}</td>
                  <td className="num">{e.cpl_meta_crm ? reaisCentavos(e.cpl_meta_crm) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Detalhe pedido={detalhe} filtros={filtros} onFechar={() => setDetalhe(null)} />
    </div>
  );
}
