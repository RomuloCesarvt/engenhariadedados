'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { AppShell, useShell } from '../components/bi/AppShell';
import { useDados, useFiltros } from '../components/bi/useFiltros';
import { Aviso, AlternarVisao, BadgeConfianca, Card, ErroCarga, Medidor, StatTile, Vazio } from '../components/bi/ui';
import { FunilChart, LeadsPorGrupoChart, ParticipacaoChart, VendasChart } from '../components/bi/charts';
import { Detalhe, PedidoDetalhe } from '../components/bi/Detalhe';
import { fetchBI, fetchDiagnosticos } from '../lib/biApi';
import { CONFIANCA_LABEL, GRUPO_COR, SERIES, STATUS } from '../lib/cores';
import { empreendimentoCurto, numero, pct, reais, reaisCompacto } from '../lib/format';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Visão geral" subtitulo="Leads online, vendas e qualidade dos dados no período">
        <VisaoGeral />
      </AppShell>
    </Suspense>
  );
}

function VisaoGeral() {
  const { filtros, chave, setEmpreendimentos } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchBI(filtros), [chave, versao]);
  const diagnosticos = useDados(() => fetchDiagnosticos(filtros), [chave, versao]);
  const [modoLeads, setModoLeads] = useState<'grafico' | 'tabela'>('grafico');
  const [modoVendas, setModoVendas] = useState<'grafico' | 'tabela'>('grafico');
  const [modoFunil, setModoFunil] = useState<'grafico' | 'tabela'>('grafico');
  const [detalhe, setDetalhe] = useState<PedidoDetalhe | null>(null);

  if (erro && !dados) {
    const semBase = erro.includes('ainda não foi baixada');
    return semBase ? (
      <Vazio
        titulo="A base de leads do CV ainda não foi baixada"
        texto="O BI é calculado sobre as bases salvas. Baixe as bases uma vez; depois elas se atualizam sozinhas a cada hora."
        acao={<Link href="/bases" className="botao-primario">Ir para Bases e integrações</Link>}
      />
    ) : (
      <ErroCarga mensagem={erro} onTentar={recarregar} />
    );
  }
  if (!dados) return <p className="text-xs text-slate-400">Calculando indicadores...</p>;

  const k = dados.kpis;
  const q = dados.qualidade;

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      {/* ---------------- indicadores ---------------- */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatTile
          label="Leads online"
          valor={numero(k.online)}
          delta={k.variacao.online}
          sub="pela data de cadastro, como no BI"
          onClick={() => setDetalhe({ titulo: 'Leads online', extra: {} })}
        />
        <StatTile
          label="Mídia paga"
          valor={numero(k.pago)}
          sub={`${pct(k.online ? (k.pago / k.online) * 100 : null)} dos leads online`}
          onClick={() => setDetalhe({ titulo: 'Leads de mídia paga', extra: { grupo: 'online_pago' } })}
        />
        <StatTile
          label="Orgânico + WhatsApp + indicação"
          valor={numero(k.organico + k.indicacao_digital)}
          sub={`${numero(k.indicacao_digital)} por Indique e Ganhe`}
          onClick={() => setDetalhe({ titulo: 'Leads orgânicos e WhatsApp', extra: { grupo: 'online_organico' } })}
        />
        <StatTile
          label="Vendas online"
          valor={numero(k.vendas_online)}
          delta={k.variacao.vendas_online}
          sub="pela data da venda"
          onClick={() => setDetalhe({ titulo: 'Vendas online no período', extra: { vendidos: true } })}
        />
        <StatTile
          label="VGV online"
          valor={reaisCompacto(k.vgv_online)}
          sub={`ticket médio ${k.vendas_online ? reaisCompacto(k.vgv_online / k.vendas_online) : '—'}`}
        />
        <StatTile label="Conversão (coorte)" valor={pct(k.conversao_coorte_online)} sub="leads online do período que já venderam" />
      </div>

      {diagnosticos.dados && diagnosticos.dados.resumo.pendentes_criticos + diagnosticos.dados.resumo.pendentes_atencao > 0 && (
        <Aviso tipo="atencao">
          <strong>
            {numero(diagnosticos.dados.resumo.pendentes_criticos + diagnosticos.dados.resumo.pendentes_atencao)} problema(s) pendente(s)
          </strong>{' '}
          podem afetar os números deste período
          {diagnosticos.dados.resumo.pendentes_criticos > 0 ? ` (${numero(diagnosticos.dados.resumo.pendentes_criticos)} crítico(s))` : ''}:{' '}
          {diagnosticos.dados.itens
            .filter((i) => i.situacao === 'pendente' && i.severidade !== 'info')
            .slice(0, 2)
            .map((i) => i.titulo)
            .join('; ')}
          .{' '}
          <Link href="/diagnosticos" className="underline text-amber-200">
            Ver o que é, por quê e como resolver
          </Link>
        </Aviso>
      )}

      {dados.regra_leads && <p className="text-[11px] text-slate-500 -mt-2">{dados.regra_leads}</p>}

      {dados.avisos.length > 0 && (
        <div className="grid md:grid-cols-2 gap-2">
          {dados.avisos.map((a) => (
            <Aviso key={a}>{a}</Aviso>
          ))}
        </div>
      )}

      {/* ---------------- tempo ---------------- */}
      <div className="grid xl:grid-cols-3 gap-5">
        <Card
          className="xl:col-span-2"
          titulo="Leads por origem"
          subtitulo={`Por ${dados.periodo.granularidade === 'mes' ? 'mês' : 'semana'}, pela data da última conversão no CV`}
          acao={<AlternarVisao modo={modoLeads} setModo={setModoLeads} />}
        >
          <LeadsPorGrupoChart serie={dados.serie} modo={modoLeads} />
        </Card>

        <Card titulo="Participação por origem" subtitulo="Passe o mouse para destacar · clique para ver os leads">
          <ParticipacaoChart grupos={dados.por_grupo} onSelecionar={(g) => setDetalhe({ titulo: g.label, extra: { grupo: g.chave } })} />
          <p className="text-[11px] text-slate-500 mt-4 leading-relaxed">
            Mídia paga = anúncios (Meta, Google). Orgânico = site, WhatsApp e redes sem anúncio. Indicação = Indique e Ganhe (BeeViral).
          </p>
        </Card>
      </div>

      {/* ---------------- canais ---------------- */}
      <Card titulo="Leads por canal" subtitulo="Classificação lead a lead pela evidência mais forte: UTM > mídia do CV > tag. Clique na linha para auditar.">
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Canal</th>
                <th>Grupo</th>
                <th className="text-right">Leads</th>
                <th className="text-right">% dos leads</th>
                <th>Confiança da classificação</th>
                <th className="text-right">Vendas no período</th>
                <th className="text-right">VGV</th>
                <th className="text-right" title="Dos leads cadastrados no período, quantos já viraram venda">
                  Conversão (coorte)
                </th>
              </tr>
            </thead>
            <tbody>
              {dados.por_canal.map((c) => (
                <tr key={c.chave} className="cursor-pointer hover:bg-slate-800/40" onClick={() => setDetalhe({ titulo: c.label, extra: { canal: c.chave } })}>
                  <td className="font-medium text-slate-100">
                    <span className="inline-block w-2 h-2 rounded-sm mr-2 align-middle" style={{ background: GRUPO_COR[c.grupo!] }} />
                    {c.label}
                  </td>
                  <td className="text-slate-400">{c.grupo_label}</td>
                  <td className="num">{numero(c.leads)}</td>
                  <td className="num">{pct(c.pct_leads)}</td>
                  <td>
                    <div className="flex gap-1 flex-wrap">
                      {Object.entries(c.confianca)
                        .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
                        .map(([nivel, qtd]) => (
                          <span key={nivel} title={CONFIANCA_LABEL[nivel]} className="inline-flex items-center gap-1">
                            <BadgeConfianca confianca={nivel} />
                            <span className="text-[10px] text-slate-500 tabular-nums">{numero(qtd ?? 0)}</span>
                          </span>
                        ))}
                    </div>
                  </td>
                  <td className="num">{numero(c.vendas)}</td>
                  <td className="num">{c.vgv ? reaisCompacto(c.vgv) : '—'}</td>
                  <td className="num">{pct(c.conversao_coorte)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---------------- empreendimentos ---------------- */}
      <Card
        titulo="Empreendimentos"
        subtitulo="Clique para filtrar todo o painel pelo empreendimento"
        acao={
          <Link href="/empreendimentos" className="text-xs text-sky-300 hover:text-sky-200 inline-flex items-center">
            Ver detalhes <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        }
      >
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Empreendimento</th>
                <th>Praça</th>
                <th className="text-right">Leads online</th>
                <th className="text-right">Mídia paga</th>
                <th className="text-right">Orgânico</th>
                <th className="text-right">Vendas online</th>
                <th className="text-right">VGV online</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_empreendimento.map((e) => (
                <tr key={e.empreendimento} className="cursor-pointer hover:bg-slate-800/40" onClick={() => setEmpreendimentos([e.empreendimento])}>
                  <td className="font-medium text-slate-100" title={e.empreendimento}>
                    {empreendimentoCurto(e.empreendimento)}
                  </td>
                  <td className="text-slate-400">{e.praca}</td>
                  <td className="num">{numero(e.leads)}</td>
                  <td className="num">{numero(e.pago)}</td>
                  <td className="num">{numero(e.organico)}</td>
                  <td className="num">{numero(e.vendas_online)}</td>
                  <td className="num">{e.vgv ? reaisCompacto(e.vgv) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ---------------- funil e vendas ---------------- */}
      <div className="grid xl:grid-cols-2 gap-5">
        <Card
          titulo="Funil dos leads online"
          subtitulo="Etapa mais avançada que cada lead alcançou (histórico de tags e tarefas, não só a situação atual)"
          acao={<AlternarVisao modo={modoFunil} setModo={setModoFunil} />}
        >
          <FunilChart
            etapas={dados.funil.online}
            modo={modoFunil}
            onClickEtapa={(nivel) => setDetalhe({ titulo: `Leads online que chegaram a: ${dados.funil.online[nivel].label}`, extra: { etapa_minima: nivel, grupo: undefined } })}
          />
        </Card>
        <Card titulo="Vendas online" subtitulo="Pela data da venda. VGV online no tooltip e na tabela." acao={<AlternarVisao modo={modoVendas} setModo={setModoVendas} />}>
          <VendasChart serie={dados.serie} modo={modoVendas} />
        </Card>
      </div>

      {/* ---------------- campanhas, perdas, qualidade ---------------- */}
      <div className="grid xl:grid-cols-3 gap-5">
        <Card titulo="Campanhas com mais leads" subtitulo="Pela utm_campaign registrada no CV" className="xl:col-span-1">
          {dados.campanhas.length === 0 ? (
            <p className="text-xs text-slate-500">Nenhum lead com campanha no período.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Campanha</th>
                    <th className="text-right">Leads</th>
                    <th className="text-right" title="Dos leads desta campanha cadastrados no período, quantos já viraram venda">
                      Já venderam
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {dados.campanhas.slice(0, 10).map((c) => (
                    <tr key={c.campanha}>
                      <td className="max-w-[220px]">
                        <span className="block truncate text-slate-200" title={c.campanha}>
                          {c.campanha}
                        </span>
                        <span className="block text-[10px] text-slate-500 truncate">
                          {c.canal} · {empreendimentoCurto(c.empreendimento)}
                        </span>
                      </td>
                      <td className="num">{numero(c.leads)}</td>
                      <td className="num">{numero(c.vendas_coorte)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card titulo="Por que os leads online se perdem" subtitulo="Motivo de cancelamento registrado no CV">
          <div className="space-y-3">
            {dados.motivos_perda_online.map((m) => (
              <div key={m.motivo}>
                <div className="flex justify-between text-xs mb-1 gap-2">
                  <span className="text-slate-300 truncate" title={m.motivo}>
                    {m.motivo}
                  </span>
                  <span className="tabular-nums text-slate-400 shrink-0">
                    {numero(m.leads)} · {pct(m.pct)}
                  </span>
                </div>
                <Medidor valor={m.pct} cor={SERIES.s1} />
              </div>
            ))}
            {dados.motivos_perda_online.length === 0 && <p className="text-xs text-slate-500">Nenhum cancelamento no período.</p>}
          </div>
        </Card>

        <Card titulo="Qualidade dos dados" subtitulo="O quanto dá para confiar na origem de cada número">
          <ul className="space-y-2.5 text-xs">
            <LinhaQualidade
              label="Leads com UTM (evidência mais forte)"
              valor={pct(q.pct_com_utm)}
              detalhe={`${numero(q.com_utm)} de ${numero(q.leads)}`}
              cor={(q.pct_com_utm ?? 0) >= 50 ? STATUS.bom : STATUS.atencao}
            />
            <LinhaQualidade
              label="WhatsApp sem rastreio"
              valor={numero(q.whatsapp_sem_rastreio)}
              detalhe="sem UTM nem tag de orgânico"
              cor={q.whatsapp_sem_rastreio ? STATUS.atencao : STATUS.bom}
              onClick={() => setDetalhe({ titulo: 'WhatsApp sem rastreio', extra: { canal: 'whatsapp_nao_rastreado' } })}
            />
            <LinhaQualidade
              label="Sem origem registrada"
              valor={numero(q.sem_origem)}
              detalhe="mídia e origem vazias no CV"
              cor={q.sem_origem ? STATUS.atencao : STATUS.bom}
              onClick={() => setDetalhe({ titulo: 'Leads sem origem registrada', extra: { canal: 'nao_rastreado' } })}
            />
            <LinhaQualidade
              label="Sem empreendimento"
              valor={numero(q.sem_empreendimento)}
              detalhe="não entram na conferência por produto"
              cor={q.sem_empreendimento ? STATUS.atencao : STATUS.bom}
              onClick={() => setDetalhe({ titulo: 'Leads sem empreendimento', extra: { empreendimento: 'Não identificado' } })}
            />
            <LinhaQualidade
              label="Vendas sem origem rastreável"
              valor={pct(q.pct_vendas_sem_origem)}
              detalhe={`${numero(q.vendas_sem_origem)} vendas`}
              cor={(q.pct_vendas_sem_origem ?? 0) >= 10 ? STATUS.serio : STATUS.bom}
            />
          </ul>
          <div className="mt-4 pt-3 border-t border-slate-800">
            <p className="text-[11px] text-slate-500 mb-2">Confiança da classificação dos leads do período</p>
            <div className="flex flex-wrap gap-2">
              {(['alta', 'media', 'baixa', 'nenhuma'] as const).map((n) => (
                <span key={n} className="inline-flex items-center gap-1">
                  <BadgeConfianca confianca={n} />
                  <span className="text-[11px] tabular-nums text-slate-400">{numero(q.confianca[n] ?? 0)}</span>
                </span>
              ))}
            </div>
          </div>
        </Card>
      </div>

      {dados.investimento.disponivel ? (
        <Card titulo="Investimento em mídia no período" subtitulo="Segundo as plataformas">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-xs text-slate-400">Meta Ads</p>
              <p className="text-xl font-semibold text-white">{reais(dados.investimento.meta)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Google Ads</p>
              <p className="text-xl font-semibold text-white">{reais(dados.investimento.google)}</p>
            </div>
          </div>
          {(dados.investimento.por_conta ?? []).length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <p className="text-xs text-slate-400 mb-1.5">
                Conta a conta. O BI da agência cobre só parte disto: nele entra a Meta das contas que ela gerencia, e o
                Google não entra.
              </p>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-400 border-b border-slate-700">
                    <th className="py-1.5 pr-2 text-left font-medium">Conta de anúncio</th>
                    <th className="py-1.5 px-2 text-left font-medium">Plataforma</th>
                    <th className="py-1.5 px-2 text-left font-medium">Praça</th>
                    <th className="py-1.5 pl-2 text-right font-medium">Investimento</th>
                  </tr>
                </thead>
                <tbody>
                  {(dados.investimento.por_conta ?? []).map((c) => (
                    <tr key={`${c.plataforma}|${c.conta}`} className="border-b border-slate-800/60">
                      <td className="py-1.5 pr-2 text-slate-200">{c.conta}</td>
                      <td className="py-1.5 px-2 text-slate-400">{c.plataforma === 'meta' ? 'Meta Ads' : 'Google Ads'}</td>
                      <td className="py-1.5 px-2 text-slate-400">{c.praca}</td>
                      <td className="py-1.5 pl-2 text-right tabular-nums text-slate-300">{reais(c.investimento)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      ) : (
        <Aviso tipo="atencao">
          Investimento e custo por lead aparecem aqui quando as bases de Meta Ads e Google Ads estiverem conectadas.{' '}
          <Link href="/bases" className="underline text-amber-200">
            Ver o que falta
          </Link>
          .
        </Aviso>
      )}

      <Detalhe pedido={detalhe} filtros={filtros} onFechar={() => setDetalhe(null)} />
    </div>
  );
}

function LinhaQualidade({
  label,
  valor,
  detalhe,
  cor,
  onClick,
}: {
  label: string;
  valor: string;
  detalhe: string;
  cor: string;
  onClick?: () => void;
}) {
  const conteudo = (
    <>
      <span className="inline-flex items-start gap-2 text-left">
        <span className="w-2 h-2 rounded-full mt-1 shrink-0" style={{ background: cor }} aria-hidden />
        <span>
          <span className="text-slate-300">{label}</span>
          <span className="block text-[10px] text-slate-500">{detalhe}</span>
        </span>
      </span>
      <span className="tabular-nums font-semibold text-slate-100">{valor}</span>
    </>
  );
  return (
    <li>
      {onClick ? (
        <button onClick={onClick} className="w-full flex items-start justify-between gap-2 hover:bg-slate-800/40 rounded-md -mx-1 px-1 py-0.5">
          {conteudo}
        </button>
      ) : (
        <div className="flex items-start justify-between gap-2">{conteudo}</div>
      )}
    </li>
  );
}
