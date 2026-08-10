'use client';

import React, { Suspense, useState } from 'react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { AlternarVisao, Aviso, Card, ErroCarga, StatTile } from '../../components/bi/ui';
import { FunilChart, FunilComparacaoChart, VendasChart } from '../../components/bi/charts';
import { Detalhe, PedidoDetalhe } from '../../components/bi/Detalhe';
import { fetchBI } from '../../lib/biApi';
import { GRUPO_COR } from '../../lib/cores';
import { data, dataHora, numero, pct, reais, reaisCompacto } from '../../lib/format';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Funil e vendas" subtitulo="Do lead online à venda: onde avança, onde para e de qual canal digital vem">
        <Funil />
      </AppShell>
    </Suspense>
  );
}

function Funil() {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchBI(filtros), [chave, versao]);
  const [modoTodos, setModoTodos] = useState<'grafico' | 'tabela'>('grafico');
  const [modoOnline, setModoOnline] = useState<'grafico' | 'tabela'>('grafico');
  const [modoMovimentacao, setModoMovimentacao] = useState<'grafico' | 'tabela'>('grafico');
  const [modoVendas, setModoVendas] = useState<'grafico' | 'tabela'>('grafico');
  const [detalhe, setDetalhe] = useState<PedidoDetalhe | null>(null);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Calculando...</p>;
  const k = dados.kpis;
  const eq = dados.equivalencias_bi;
  const vendasOnlineEtapa = dados.funil.online[dados.funil.online.length - 1];

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
        <StatTile destaque label="Vendas online" valor={numero(k.vendas)} delta={k.variacao.vendas} sub="pela data da venda e pelo lead vinculado" onClick={() => setDetalhe({ titulo: 'Vendas online', extra: { vendidos: true } })} />
        <StatTile
          label="VGV online"
          valor={reaisCompacto(k.vgv)}
          sub="somente vendas com origem online comprovada"
        />
        <StatTile label="Conversão coorte (online)" valor={pct(k.conversao_coorte_online)} sub={`${numero(vendasOnlineEtapa?.leads ?? 0)} vendas dos ${numero(k.online)} leads online`} />
        <StatTile label="Ticket médio online" valor={k.vendas ? reais(k.vgv / k.vendas) : '—'} sub="VGV online ÷ vendas online" />
      </div>

      {k.fonte_vendas === 'reservas' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <StatTile
            label="Unidades vendidas online"
            valor={numero(k.unidades_vendidas)}
            sub={`no empreendimento comprado · ${reaisCompacto(k.vgv_unidades)}`}
            onClick={() => setDetalhe({ titulo: 'Unidades vendidas online (empreendimento comprado)', extra: { vendidos: true, criterio: 'comprado' } })}
          />
          <StatTile
            label="Compraram em outro empreendimento"
            valor={numero(k.vendas_outro_empreendimento)}
            sub="vendas online contadas no interesse do lead, com a unidade comprada em outro produto"
            onClick={() => setDetalhe({ titulo: 'Compraram em outro empreendimento', extra: { vendidos: true, so_outro_empreendimento: true } })}
          />
        </div>
      )}

      <Aviso>
        Todo este painel considera <strong>somente leads e vendas com origem online</strong>. O funil conta a etapa mais avançada que cada lead cadastrado no período alcançou, usando o histórico de tags
        (SAL, SQL, atendimento) e tarefas (visita agendada). A situação atual sozinha apagaria o caminho: a maioria dos leads está hoje
        como &quot;Cancelado&quot;. Vendas por data de venda ficam no gráfico ao lado.
      </Aviso>

      <Card
        titulo="Régua de comparação dos Power BIs"
        subtitulo={`CV Leads: ${dataHora(eq.cv_leads_atualizado_em)} · CV Reservas: ${dataHora(eq.cv_reservas_atualizado_em)}. Nomes diferentes indicam populações e datas de referência diferentes.`}
      >
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Nome sem ambiguidade</th>
                <th className="text-right">Agora</th>
                <th>Regra</th>
                <th>Equivale a</th>
              </tr>
            </thead>
            <tbody>
              <tr className="text-amber-200">
                <td>Novo Lead MQL por transição</td>
                <td className="num font-semibold">—</td>
                <td>{eq.regra_novo_lead_mql}</td>
                <td>funil Gerencial do Power BI FM&amp;D</td>
              </tr>
              <tr>
                <td>MQL por última conversão</td>
                <td className="num font-semibold">{numero(eq.mql_ultima_conversao)}</td>
                <td>pessoa online cuja última conversão no CV caiu no período</td>
                <td>cartão MQL do Power BI Moura Leite</td>
              </tr>
              <tr>
                <td>SQL detectado no histórico</td>
                <td className="num font-semibold">{numero(eq.sql_historico)}</td>
                <td>situação, tags e tarefas; estimativa auditável, não a fato de qualificações</td>
                <td>comparação indicativa com SQL, não substitui o SQL certificado</td>
              </tr>
              <tr>
                <td>Unidades vendidas online</td>
                <td className="num font-semibold">{numero(eq.unidades_vendidas)}</td>
                <td>reserva vendida com lead online, pela data da venda e pelo produto comprado</td>
                <td>fonte direta do CV; os cartões gerais dos Power BIs não entram nesta comparação</td>
              </tr>
              <tr>
                <td>Vendas SDR online</td>
                <td className="num font-semibold">{numero(eq.vendas_tipo_sdr_online)}</td>
                <td>tipo “Vendas SDR” com lead vinculado classificado como online · {reaisCompacto(eq.vgv_tipo_sdr_online)}</td>
                <td>funil Gerencial do Power BI FM&amp;D com filtro Online</td>
              </tr>
              <tr className={eq.vendas_sem_tipo ? 'text-amber-200' : undefined}>
                <td>Vendas online sem tipo preenchido</td>
                <td className="num font-semibold">{numero(eq.vendas_sem_tipo)}</td>
                <td>{reaisCompacto(eq.vgv_sem_tipo)} mantidos no total online e sinalizados para correção</td>
                <td>não podem ser apagadas silenciosamente por um filtro</td>
              </tr>
            </tbody>
          </table>
        </div>
        {!eq.sql_certificado && <p className="mt-3 text-[11px] text-amber-300">{eq.regra_sql}</p>}
      </Card>

      <Card
        titulo="Movimentação no período"
        subtitulo="A mesma população do MQL do Power BI Moura Leite: uma pessoa por última conversão registrada no período. As etapas seguintes são reconstruídas dos sinais disponíveis no CV."
        acao={<AlternarVisao modo={modoMovimentacao} setModo={setModoMovimentacao} />}
      >
        <FunilChart etapas={dados.funil_movimentacao} modo={modoMovimentacao} />
      </Card>

      <div className="grid xl:grid-cols-2 gap-5">
        <Card titulo="Funil — leads online" acao={<AlternarVisao modo={modoOnline} setModo={setModoOnline} />}>
          <FunilChart etapas={dados.funil.online} modo={modoOnline} onClickEtapa={(n) => setDetalhe({ titulo: `Online: ${dados.funil.online[n].label}`, extra: { etapa_minima: n } })} />
        </Card>
        <Card
          titulo="Funil online × período anterior"
          subtitulo="Etapa a etapa: quantos chegaram agora, quantos no período anterior de mesmo tamanho e como mudou a passagem entre etapas"
          acao={<AlternarVisao modo={modoTodos} setModo={setModoTodos} />}
        >
          <FunilComparacaoChart
            atual={dados.funil.online}
            anterior={dados.funil_anterior}
            rotuloAtual={`${data(dados.periodo.inicio)} a ${data(dados.periodo.fim)}`}
            rotuloAnterior={`${data(dados.periodo.anterior_inicio)} a ${data(dados.periodo.anterior_fim)}`}
            modo={modoTodos}
          />
        </Card>
      </div>

      <div className="grid xl:grid-cols-2 gap-5">
        <Card titulo="Vendas online no tempo" acao={<AlternarVisao modo={modoVendas} setModo={setModoVendas} />}>
          <VendasChart serie={dados.serie} modo={modoVendas} />
        </Card>
        <Card titulo="De onde vieram as vendas online" subtitulo="Vendas do período pelo canal digital do lead que comprou">
          <table className="tabela">
            <thead>
              <tr>
                <th>Canal</th>
                <th className="text-right">Vendas</th>
                <th className="text-right">% das vendas</th>
                <th className="text-right">VGV</th>
              </tr>
            </thead>
            <tbody>
              {[...dados.por_canal]
                .filter((c) => c.vendas > 0)
                .sort((a, b) => b.vendas - a.vendas)
                .map((c) => (
                  <tr key={c.chave} className="cursor-pointer hover:bg-slate-800/40" onClick={() => setDetalhe({ titulo: `Vendas: ${c.label}`, extra: { canal: c.chave, vendidos: true } })}>
                    <td>
                      <span className="inline-block w-2 h-2 rounded-sm mr-2 align-middle" style={{ background: GRUPO_COR[c.grupo!] }} />
                      {c.label}
                    </td>
                    <td className="num">{numero(c.vendas)}</td>
                    <td className="num">{pct(k.vendas ? (c.vendas / k.vendas) * 100 : null)}</td>
                    <td className="num">{reaisCompacto(c.vgv)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Detalhe pedido={detalhe} filtros={filtros} onFechar={() => setDetalhe(null)} />
    </div>
  );
}
