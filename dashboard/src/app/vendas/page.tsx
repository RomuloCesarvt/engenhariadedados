'use client';

/**
 * Vendas × leads: toda venda do CV cruzada com os sinais de origem online (outro lead da pessoa, mídia da reserva,
 * formulário da Meta, BeeViral, RD Station). Mostra o que está fora do online e deveria estar, com a análise do período.
 */

import React, { Suspense, useState } from 'react';
import { ExternalLink, Search } from 'lucide-react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { OQueResponde } from '../../components/bi/OQueResponde';
import { Aviso, Card, ErroCarga, StatTile, Vazio } from '../../components/bi/ui';
import { SalesUpload } from '../../components/SalesUpload';
import { fetchAuditoriaVendas } from '../../lib/biApi';
import { data, empreendimentoCurto, numero, pct, reais, reaisCompacto } from '../../lib/format';
import { ForcaSinal, StatusVendaAuditada, VendaAuditada } from '../../types/bi';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Vendas × leads" subtitulo="Cada venda cruzada com todos os sinais de origem online: o que conta, o que falta contar e por quê">
        <VendasXLeads />
      </AppShell>
    </Suspense>
  );
}

const ABAS: { status: StatusVendaAuditada; label: string }[] = [
  { status: 'online_nao_contabilizada', label: 'Online não contabilizadas' },
  { status: 'online_sem_vinculo', label: 'Online sem o lead vinculado' },
  { status: 'provavel_online', label: 'Provável online (mídia da reserva)' },
  { status: 'possivel_online', label: 'Possível online (só RD)' },
  { status: 'sem_sinal_online', label: 'Sem sinal online' },
];

function OQueEstaTelaResponde() {
  return (
    <OQueResponde
      pergunta={
        <>
          venda a venda, <strong>existe algum sinal de que essa pessoa veio do digital?</strong> É a varredura ampla: passa
          por todas as bases e mostra até as pistas fracas, para você conferir uma a uma no dia a dia.
        </>
      }
      regua={[
        <>
          Olha <strong>todas as vendas do CV</strong> no período (as que ainda estão vendidas) e cruza com outro lead da
          pessoa, formulário da Meta, indicação BeeViral, mídia escolhida na reserva e contato na RD Station.
        </>,
        <>
          Separa por <strong>força da evidência</strong>: forte (lead online, Meta, BeeViral), indício (só a mídia da
          reserva) e sinal fraco (só contato na RD) — pistas, não veredito.
        </>,
        <>
          "Contam como online" segue a régua do BI gerencial: o <strong>lead vinculado à reserva</strong> tem origem
          online. WhatsApp entra como canal digital, como no resto do BI.
        </>,
      ]}
      naoResponde={
        <>
          se a venda <strong>é venda online</strong> — isso depende de quem vendeu (o time Moura Leite) e da janela de
          atribuição, e é o que fecha o relatório do mês em
        </>
      }
      outra={{ href: '/analista', label: 'Analista → Vendas online × leads' }}
    />
  );
}

const FORCA: Record<ForcaSinal, { classe: string; label: string }> = {
  forte: { classe: 'bg-emerald-500/10 text-emerald-300', label: 'evidência forte' },
  media: { classe: 'bg-amber-500/10 text-amber-300', label: 'indício' },
  fraco: { classe: 'bg-slate-700/40 text-slate-300', label: 'sinal fraco' },
};

const LIGACAO: Record<VendaAuditada['ligacao'], string> = {
  lead_associado: 'Lead associado à reserva',
  email: 'Lead achado pelo e-mail do titular',
  telefone: 'Lead achado pelo telefone do titular',
  sem_lead: 'Sem lead no CV',
};

function VendasXLeads() {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchAuditoriaVendas(filtros), [chave, versao]);
  const [aba, setAba] = useState<StatusVendaAuditada>('online_nao_contabilizada');

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Cruzando vendas e leads...</p>;
  if (!dados.disponivel) {
    return <Vazio titulo="A base de reservas do CV ainda não foi baixada" texto="Atualize a base 'CV — Reservas e vendas' em Bases e integrações." />;
  }

  const r = dados.resumo;
  const lista = dados.itens.filter((i) => i.status === aba);
  const contagem: Record<StatusVendaAuditada, number> = {
    online: r.online,
    online_nao_contabilizada: r.online_nao_contabilizada,
    online_sem_vinculo: r.online_sem_vinculo,
    provavel_online: r.provavel_online,
    possivel_online: r.possivel_online,
    sem_sinal_online: r.sem_sinal_online,
  };

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <OQueEstaTelaResponde />

      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <StatTile label="Vendas no período" valor={numero(r.vendas)} sub={`VGV ${reaisCompacto(r.vgv)} · pela data da venda`} />
        <StatTile label="Contam como online" valor={numero(r.online)} sub={`${pct(r.pct_online_contada)} das vendas · ${reaisCompacto(r.vgv_online)}`} />
        <StatTile
          destaque
          label="Online não contabilizadas"
          valor={numero(r.online_nao_contabilizada)}
          sub={`evidência forte · ${reaisCompacto(r.vgv_online_nao_contabilizada)} · online iria a ${pct(r.pct_online_potencial)}`}
          onClick={() => setAba('online_nao_contabilizada')}
        />
        <StatTile
          label="Online sem o lead vinculado"
          valor={numero(r.online_sem_vinculo)}
          sub={`a pessoa tem lead online, a reserva não · ${reaisCompacto(r.vgv_online_sem_vinculo)}`}
          onClick={() => setAba('online_sem_vinculo')}
        />
        <StatTile
          label="Provável online"
          valor={numero(r.provavel_online)}
          sub={`só a mídia da reserva · ${reaisCompacto(r.vgv_provavel_online)} · essa mídia acerta ${pct(r.confiabilidade_midia_reserva)}`}
          onClick={() => setAba('provavel_online')}
        />
        <StatTile
          label="Possível online"
          valor={numero(r.possivel_online)}
          sub={`só contato na RD antes da compra · ${numero(r.sem_sinal_online)} sem sinal online`}
          onClick={() => setAba('possivel_online')}
        />
      </div>

      <Card titulo="Análise do período" subtitulo="O que os números mostram e onde agir primeiro">
        <ul className="space-y-1.5 text-xs text-slate-300 leading-relaxed list-disc pl-4">
          {dados.leituras.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </Card>

      <div className="grid xl:grid-cols-3 gap-5">
        <Card titulo="Evidências encontradas" subtitulo="Vendas fora do online com cada sinal (uma venda pode ter vários)">
          <table className="tabela">
            <thead>
              <tr>
                <th>Sinal</th>
                <th className="text-right">Vendas</th>
                <th className="text-right">VGV</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_sinal.map((s) => (
                <tr key={s.tipo}>
                  <td>
                    {s.label}
                    <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] ${FORCA[s.forca].classe}`}>{FORCA[s.forca].label}</span>
                  </td>
                  <td className="num">{numero(s.vendas)}</td>
                  <td className="num">{s.vgv ? reaisCompacto(s.vgv) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card titulo="Onde acontece" subtitulo="Vendas a conferir (fortes + prováveis) por empreendimento comprado">
          <table className="tabela">
            <thead>
              <tr>
                <th>Empreendimento</th>
                <th className="text-right">A conferir</th>
                <th className="text-right">Fortes</th>
                <th className="text-right">VGV</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_empreendimento.slice(0, 8).map((e) => (
                <tr key={e.empreendimento}>
                  <td title={e.empreendimento}>{empreendimentoCurto(e.empreendimento)}</td>
                  <td className="num">{numero(e.vendas)}</td>
                  <td className="num">{numero(e.fortes)}</td>
                  <td className="num">{reaisCompacto(e.vgv)}</td>
                </tr>
              ))}
              {!dados.por_empreendimento.length && (
                <tr>
                  <td className="text-slate-500">Nenhuma no período.</td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
        <Card titulo="Quem registrou" subtitulo="Imobiliária ou corretor das vendas a conferir">
          <table className="tabela">
            <tbody>
              {dados.por_imobiliaria.map((m) => (
                <tr key={m.nome}>
                  <td>{m.nome}</td>
                  <td className="num">{numero(m.vendas)}</td>
                </tr>
              ))}
              {!dados.por_imobiliaria.length && (
                <tr>
                  <td className="text-slate-500">Nenhuma no período.</td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      </div>

      <Card
        titulo="Vendas para conferir"
        subtitulo="Cada venda com as evidências, como está ligada ao lead hoje e o que fazer"
        acao={
          dados.cv_busca_url ? (
            <a href={dados.cv_busca_url} target="_blank" rel="noopener noreferrer" className="botao-secundario inline-flex items-center gap-1">
              <Search className="w-3 h-3" /> Buscar lead no CV
            </a>
          ) : undefined
        }
      >
        <div className="flex flex-wrap gap-2 mb-3" role="tablist">
          {ABAS.map((a) => (
            <button
              key={a.status}
              role="tab"
              aria-selected={aba === a.status}
              onClick={() => setAba(a.status)}
              className={`px-3 py-1.5 rounded-lg border text-[11px] ${
                aba === a.status ? 'border-sky-500/60 bg-sky-500/10 text-sky-200' : 'border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              {a.label} · {numero(contagem[a.status])}
            </button>
          ))}
        </div>
        {aba === 'sem_sinal_online' && (
          <Aviso>Nenhuma base mostra origem online para estas vendas. A lista serve para conferência: normalmente são vendas do comercial.</Aviso>
        )}
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Venda</th>
                <th>Unidade</th>
                <th>Origem hoje</th>
                <th>Evidências de origem online</th>
                <th>O que fazer</th>
                <th className="text-right">Valor</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((v) => (
                <tr key={v.idreserva} className="align-top">
                  <td className="whitespace-nowrap">
                    {data(v.data_venda)}
                    <span className="block text-slate-500">Reserva {v.idreserva}</span>
                  </td>
                  <td className="max-w-[190px]">
                    <span className="block truncate" title={v.empreendimento_comprado}>
                      {empreendimentoCurto(v.empreendimento_comprado)}
                    </span>
                    {v.unidade && <span className="block text-slate-500">{v.unidade}</span>}
                    {(v.imobiliaria || v.corretor) && <span className="block text-slate-500 truncate">{v.imobiliaria || v.corretor}</span>}
                  </td>
                  <td className="max-w-[200px]">
                    <span className="block">{v.canal_atual}</span>
                    <span className="block text-slate-500">{LIGACAO[v.ligacao]}</span>
                    {v.lead_link && (
                      <a href={v.lead_link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200">
                        Lead {v.lead_id} no CV <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </td>
                  <td className="max-w-[320px]">
                    {v.sinais.length === 0 && <span className="text-slate-500">—</span>}
                    <ul className="space-y-1.5">
                      {v.sinais.map((s) => (
                        <li key={s.tipo}>
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] mr-1 ${FORCA[s.forca].classe}`} title={FORCA[s.forca].label}>
                            {s.label}
                          </span>
                          <span className="text-slate-400">{s.detalhe}</span>
                          {s.link && (
                            <a href={s.link} target="_blank" rel="noopener noreferrer" className="ml-1 inline-flex items-center gap-1 text-sky-300 hover:text-sky-200 whitespace-nowrap">
                              {s.link_label ?? 'Abrir'} <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="max-w-[260px] text-slate-300">{v.sugestao}</td>
                  <td className="num whitespace-nowrap">{reais(v.valor_venda)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!lista.length && <p className="p-8 text-center text-xs text-slate-400">Nenhuma venda nesta situação no período.</p>}
          {dados.truncado && <p className="pt-3 text-xs text-slate-500">Mostrando as primeiras 2.000 vendas; reduza o período para ver todas.</p>}
        </div>
      </Card>

      <Card titulo="Planilha do comercial (opcional)" subtitulo="Não é necessária: as vendas já vêm das reservas do CV">
        <SalesUpload onRequestRun={() => (window.location.href = '/reconciliacao')} />
      </Card>
    </div>
  );
}
