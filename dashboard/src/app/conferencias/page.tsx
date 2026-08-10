'use client';

import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ExternalLink } from 'lucide-react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { AlternarVisao, Aviso, Card, ErroCarga, Medidor, StatTile, Vazio } from '../../components/bi/ui';
import { PlataformaCrmChart } from '../../components/bi/charts';
import { fetchConferenciaBeeviral, fetchConferenciaPlataforma, fetchConferenciaRD, verificarLead } from '../../lib/biApi';
import { SERIES, STATUS } from '../../lib/cores';
import { data, empreendimentoCurto, numero, pct, reais, reaisCentavos } from '../../lib/format';
import { ConferenciaFormulariosMeta, IndicacaoConferida, LeadFormularioConferir, StatusIndicacao, StatusRD, VerificacaoLead } from '../../types/bi';

type Aba = 'beeviral' | 'rd' | 'meta' | 'google';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Conferências" subtitulo="Cruzamento entre as bases: o que cada fonte diz × o que chegou no CV">
        <Conferencias />
      </AppShell>
    </Suspense>
  );
}

function Conferencias() {
  const [aba, setAba] = useState<Aba>('beeviral');
  const abas: { id: Aba; label: string; pergunta: string }[] = [
    { id: 'beeviral', label: 'BeeViral × CV', pergunta: 'Cada indicação chegou no CRM, e chegou creditada à BeeViral?' },
    { id: 'rd', label: 'RD Station × CV', pergunta: 'Quem converteu em formulário da RD chegou no CRM? Listas importadas ficam de fora.' },
    { id: 'meta', label: 'Meta Ads × CV', pergunta: 'A Meta diz que gerou X leads — quantos chegaram no CRM?' },
    { id: 'google', label: 'Google Ads × CV', pergunta: 'O Google diz que gerou X conversões — quantas chegaram no CRM?' },
  ];
  const atual = abas.find((a) => a.id === aba)!;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2" role="tablist">
        {abas.map((a) => (
          <button
            key={a.id}
            role="tab"
            aria-selected={aba === a.id}
            onClick={() => setAba(a.id)}
            className={`px-4 py-2 rounded-xl text-xs font-medium border transition-colors ${
              aba === a.id ? 'bg-sky-500/10 border-sky-500/40 text-sky-200' : 'border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
      <p className="text-sm text-slate-300">{atual.pergunta}</p>
      {aba === 'beeviral' ? <ConfBeeviral /> : aba === 'rd' ? <ConfRD /> : <ConfPlataforma plataforma={aba} />}
    </div>
  );
}

const STATUS_COR: Record<StatusIndicacao, string> = {
  creditada: STATUS.bom,
  sem_credito: STATUS.serio,
  ja_era_lead: '#64748b',
  nao_chegou: STATUS.critico,
};

function ConfBeeviral() {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchConferenciaBeeviral(filtros), [chave, versao]);
  const [statusFiltro, setStatusFiltro] = useState<StatusIndicacao | 'todos'>('todos');
  const listaRef = useRef<HTMLDivElement>(null);
  const vendasRef = useRef<HTMLDivElement>(null);
  const confirmando = !!dados && (dados.confirmacao.pendentes > 0 || dados.confirmacao.em_andamento);

  // Leva direto à lista já filtrada (ex.: clicar em "Não chegaram no CV")
  const irParaLista = (s: StatusIndicacao | 'todos') => {
    setStatusFiltro(s);
    setTimeout(() => listaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
  };

  useEffect(() => {
    if (!confirmando) return;
    const t = setTimeout(recarregar, 6000);
    return () => clearTimeout(t);
  }, [dados, confirmando, recarregar]);

  const itens = useMemo(
    () => (dados?.itens ?? []).filter((i) => statusFiltro === 'todos' || i.status === statusFiltro),
    [dados, statusFiltro]
  );

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Cruzando indicações com o CV...</p>;
  const r = dados.resumo;
  const ordem: StatusIndicacao[] = ['creditada', 'sem_credito', 'ja_era_lead', 'nao_chegou'];

  if (r.indicacoes === 0) {
    return <Vazio titulo="Nenhuma indicação da BeeViral no período" texto="Amplie o período no filtro acima." />;
  }

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatTile
          destaque
          label="Indicações no período"
          valor={numero(r.indicacoes)}
          sub={`${numero(r.vendidas)} já viraram venda no CV`}
          onClick={() => irParaLista('todos')}
        />
        <StatTile label="Chegaram no CV" valor={pct(r.pct_no_cv)} sub={`${numero(r.indicacoes - r.nao_chegou)} indicações`} />
        <StatTile
          label="Creditadas à BeeViral"
          valor={pct(r.pct_creditada)}
          sub="das que entraram pela indicação"
          alerta={(r.pct_creditada ?? 100) < 70 ? 'critico' : undefined}
        />
        <StatTile
          label="Não chegaram no CV"
          valor={numero(r.nao_chegou)}
          sub={r.nao_chegou ? 'clique para ver as indicações' : undefined}
          alerta={r.nao_chegou ? 'atencao' : undefined}
          onClick={() => irParaLista('nao_chegou')}
        />
        <StatTile
          label="Viraram venda"
          valor={numero(r.vendidas)}
          sub={`${reais(r.vgv_vendidas)} · ver a origem`}
          onClick={() => vendasRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
        />
      </div>

      {confirmando && (
        <Aviso tipo="atencao">
          Confirmando {numero(dados.confirmacao.pendentes)} indicação(ões) direto na API do CV: nenhuma é dada como &quot;não chegou&quot; sem essa
          confirmação — a tela se atualiza sozinha.
        </Aviso>
      )}

      <div className="grid xl:grid-cols-3 gap-5">
        <Card titulo="Situação das indicações" subtitulo="Clique para filtrar a lista">
          <div className="space-y-3">
            {ordem.map((s) => (
              <button key={s} onClick={() => irParaLista(statusFiltro === s ? 'todos' : s)} className="w-full text-left">
                <div className="flex justify-between text-xs mb-1">
                  <span className={`inline-flex items-center gap-2 ${statusFiltro === s ? 'text-white font-semibold' : 'text-slate-300'}`}>
                    <span className="w-2 h-2 rounded-full" style={{ background: STATUS_COR[s] }} />
                    {dados.status_labels[s]}
                  </span>
                  <span className="tabular-nums text-slate-200">
                    {numero(r[s])} <span className="text-slate-500">· {pct(r.indicacoes ? (r[s] / r.indicacoes) * 100 : null)}</span>
                  </span>
                </div>
                <Medidor valor={r.indicacoes ? (r[s] / r.indicacoes) * 100 : 0} cor={STATUS_COR[s]} />
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500 mt-4 leading-relaxed">
            &quot;Já era lead&quot; não é erro: a pessoa estava no CV antes de ser indicada, então a origem no CRM é a do primeiro contato.
          </p>
        </Card>

        <Card titulo="Como as indicações sem crédito foram registradas" subtitulo="Canal que o CV atribuiu a elas">
          {dados.credito_no_cv.length === 0 ? (
            <p className="text-xs text-slate-500">Todas as indicações que chegaram foram creditadas.</p>
          ) : (
            <table className="tabela">
              <tbody>
                {dados.credito_no_cv.map((c) => (
                  <tr key={c.canal}>
                    <td>{c.canal}</td>
                    <td className="num font-semibold">{numero(c.indicacoes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card titulo="Por empreendimento">
          <table className="tabela">
            <thead>
              <tr>
                <th>Empreendimento</th>
                <th className="text-right">Indic.</th>
                <th className="text-right">No CV</th>
                <th className="text-right">Creditadas</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_empreendimento.map((e) => (
                <tr key={e.empreendimento}>
                  <td title={e.empreendimento}>{empreendimentoCurto(e.empreendimento)}</td>
                  <td className="num">{numero(e.indicacoes)}</td>
                  <td className="num">{pct(e.pct_no_cv)}</td>
                  <td className="num">{pct(e.pct_creditada)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <div ref={vendasRef} className="scroll-mt-4">
        <Card
          titulo={`Vendas das indicações (${numero(r.vendidas)})`}
          subtitulo={`Uma linha por venda, mesmo que a pessoa tenha sido indicada mais de uma vez: a origem que o CV registrou e se a BeeViral ficou com o crédito.${
            r.vendas_antes_da_indicacao ? ` ${r.vendas_antes_da_indicacao} venda(s) aconteceram antes da indicação e ficam fora da contagem e do VGV.` : ''
          }`}
        >
          {dados.vendas.length === 0 ? (
            <p className="text-xs text-slate-500">Nenhuma indicação do período virou venda ainda.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Venda em</th>
                    <th className="text-right">Valor</th>
                    <th>Empreendimento</th>
                    <th>Campanha / corretor da BeeViral</th>
                    <th>Origem registrada no CV</th>
                    <th>Crédito da BeeViral</th>
                    <th>Abrir</th>
                  </tr>
                </thead>
                <tbody>
                  {dados.vendas.map((v) => (
                    <tr key={v.indicacao_id}>
                      <td className="whitespace-nowrap">
                        {v.cv_data_venda ? data(v.cv_data_venda) : '—'}
                        {v.venda_antes_da_indicacao && (
                          <span className="block text-[10px] text-amber-300">antes da indicação ({data(v.data)}) · fora da soma</span>
                        )}
                      </td>
                      <td className="num">{v.cv_valor_venda ? reais(v.cv_valor_venda) : '—'}</td>
                      <td title={v.empreendimento}>{empreendimentoCurto(v.empreendimento)}</td>
                      <td className="max-w-[260px]">
                        <span className="block truncate" title={(v.campanhas_do_lead?.length ? v.campanhas_do_lead : [v.campanha ?? '']).join(' · ')}>
                          {(v.campanhas_do_lead?.length ? v.campanhas_do_lead : [v.campanha ?? '—']).join(' · ')}
                        </span>
                        {(v.indicacoes_do_lead ?? 1) > 1 && (
                          <span className="block text-[10px] text-amber-300">Indicado {v.indicacoes_do_lead} vezes · venda contada uma vez</span>
                        )}
                      </td>
                      <td>
                        <span className="block text-slate-200">{v.cv_canal ?? '—'}</span>
                        {v.cv_evidencia && <span className="block text-[10px] text-slate-500">{v.cv_evidencia}</span>}
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ background: STATUS_COR[v.status] }} />
                          {v.status_label}
                        </span>
                      </td>
                      <td>
                        <AcoesIndicacao i={v} cvBuscaUrl={dados.cv_busca_url} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Card titulo="Por campanha / corretor da BeeViral">
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Campanha</th>
                <th className="text-right">Indicações</th>
                <th className="text-right">Creditadas</th>
                <th className="text-right">Sem crédito</th>
                <th className="text-right">Já eram leads</th>
                <th className="text-right">Não chegaram</th>
                <th className="text-right">% no CV</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_campanha.map((c) => (
                <tr key={c.campanha}>
                  <td>{c.campanha}</td>
                  <td className="num">{numero(c.indicacoes)}</td>
                  <td className="num">{numero(c.creditada)}</td>
                  <td className="num">{numero(c.sem_credito)}</td>
                  <td className="num">{numero(c.ja_era_lead)}</td>
                  <td className="num">{numero(c.nao_chegou)}</td>
                  <td className="num">{pct(c.pct_no_cv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div ref={listaRef} className="scroll-mt-4">
      <Card
        titulo={`Indicação a indicação (${numero(itens.length)})${statusFiltro !== 'todos' ? ` · ${dados.status_labels[statusFiltro]}` : ''}`}
        subtitulo="Cada botão abre exatamente esta indicação na BeeViral e este lead no CV e no RD. Contato só de quem não chegou ao CV."
        acao={
          statusFiltro !== 'todos' && (
            <button onClick={() => setStatusFiltro('todos')} className="botao-secundario">
              Mostrar todas
            </button>
          )
        }
      >
        <div className="overflow-x-auto max-h-[520px]">
          <table className="tabela">
            <thead className="sticky top-0 bg-slate-900">
              <tr>
                <th>Indicada em</th>
                <th>Indicado</th>
                <th>Campanha</th>
                <th>Empreendimento</th>
                <th>Situação</th>
                <th>Encontrada por</th>
                <th>Canal registrado no CV</th>
                <th>Situação no CV</th>
                <th>Abrir / conferir</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((i) => (
                <tr key={i.indicacao_id}>
                  <td className="whitespace-nowrap">{data(i.data)}</td>
                  <td className="min-w-[170px]">
                    {i.nome || i.email || i.telefone ? (
                      <>
                        <span className="block text-slate-100">{i.nome || '—'}</span>
                        {i.email && (
                          <BotaoCopiar texto={i.email} rotulo={i.email} className="block text-left text-[11px] text-sky-300 hover:text-sky-200 break-all" />
                        )}
                        {i.telefone && (
                          <BotaoCopiar texto={i.telefone} rotulo={i.telefone} className="block text-left text-[11px] text-sky-300 hover:text-sky-200 tabular-nums" />
                        )}
                      </>
                    ) : (
                      <span className="text-slate-600">no CV</span>
                    )}
                  </td>
                  <td className="max-w-[200px] truncate" title={i.campanha ?? ''}>
                    {i.campanha}
                  </td>
                  <td title={i.empreendimento}>{empreendimentoCurto(i.empreendimento)}</td>
                  <td className="whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: STATUS_COR[i.status] }} />
                      {i.status_label}
                    </span>
                  </td>
                  <td className="text-slate-400">{i.chave_encontrada ?? '—'}</td>
                  <td className="text-slate-400">{i.cv_canal ?? '—'}</td>
                  <td className="text-slate-400">
                    {i.cv_situacao ?? '—'}
                    {i.cv_vendido && <span className="ml-1 text-emerald-300">· vendido</span>}
                  </td>
                  <td>
                    <AcoesIndicacao i={i} cvBuscaUrl={dados.cv_busca_url} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      </div>
    </div>
  );
}

function LinkDireto({ href, titulo, onClick, children }: { href: string; titulo: string; onClick?: () => void; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      title={titulo}
      className="botao-secundario !py-1 !px-2 text-[11px] inline-flex items-center gap-1 whitespace-nowrap"
    >
      {children} <ExternalLink className="w-3 h-3" />
    </a>
  );
}

function AcoesIndicacao({ i, cvBuscaUrl }: { i: IndicacaoConferida; cvBuscaUrl: string | null }) {
  const [estado, setEstado] = useState<EstadoVerificacao | undefined>();
  const r = estado?.resultado;
  const chave = i.email || i.telefone || '';

  const verificar = async () => {
    setEstado({ carregando: true });
    try {
      setEstado({ resultado: await verificarLead(i.email, i.telefone) });
    } catch (e) {
      setEstado({ erro: (e as Error).message });
    }
  };

  return (
    <div className="space-y-1.5 text-[11px] min-w-[210px]">
      {i.confirmacao?.estado === 'confirmado' && (
        <p className="text-emerald-300">
          ✓ Confirmado ao vivo às{' '}
          {new Date(i.confirmacao.verificado_em ?? '').toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}: não está no CV
        </p>
      )}
      {i.confirmacao?.estado === 'pendente' && <p className="text-slate-400">Confirmando no CV…</p>}
      <div className="flex flex-wrap gap-1.5">
        {i.bee_link && (
          <LinkDireto href={i.bee_link} titulo="Abre exatamente esta indicação no painel da BeeViral">
            BeeViral
          </LinkDireto>
        )}
        {i.cv_link ? (
          <LinkDireto href={i.cv_link} titulo="Abre exatamente este lead no CV">
            CV
          </LinkDireto>
        ) : (
          cvBuscaUrl &&
          chave && (
            <LinkDireto
              href={cvBuscaUrl}
              onClick={() => copiarTexto(chave)}
              titulo="O lead não existe no CV: abre a tela de leads e copia o e-mail (ou telefone) para colar na busca"
            >
              Buscar no CV
            </LinkDireto>
          )
        )}
        {i.rd_link ? (
          <LinkDireto href={i.rd_link} titulo="Abre exatamente este contato no RD Station">
            RD
          </LinkDireto>
        ) : (
          i.email && (
            <LinkDireto
              href={RD_BASE_CONTATOS_URL}
              onClick={() => copiarTexto(i.email as string)}
              titulo="Sem o identificador do RD: abre a base de contatos e copia o e-mail para colar na busca"
            >
              Buscar no RD
            </LinkDireto>
          )
        )}
        {!i.cv_link && chave && (
          <button onClick={verificar} disabled={estado?.carregando} className="botao-primario !py-1 !px-2 text-[11px]">
            {estado?.carregando ? 'Verificando...' : r ? 'Verificar de novo' : 'Verificar agora'}
          </button>
        )}
      </div>

      {estado?.erro && <p className="text-rose-300">Falha na verificação: {estado.erro}</p>}
      {r && (
        <div className="rounded-md border border-slate-700 bg-slate-900/60 p-2 space-y-1">
          {!r.cv.consultado ? (
            <p className="text-amber-300">CV: não foi possível consultar ({r.cv.erros.join('; ') || 'sem e-mail e telefone'})</p>
          ) : r.cv.encontrado ? (
            r.cv.leads.map((c) => (
              <a key={String(c.idlead)} href={c.link ?? '#'} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-emerald-300 hover:text-emerald-200">
                CV: lead #{c.idlead} · {c.situacao ?? '—'} <ExternalLink className="w-3 h-3" />
              </a>
            ))
          ) : (
            <p className="text-rose-300">CV: não existe (buscado por {r.cv.consultas.map((c) => c.por).join(', ')})</p>
          )}
          {r.rd.consultado &&
            (r.rd.encontrado ? (
              <a href={r.rd.link ?? '#'} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-amber-300 hover:text-amber-200">
                RD: contato existe — abrir <ExternalLink className="w-3 h-3" />
              </a>
            ) : (
              <p className="text-slate-400">RD: contato não existe</p>
            ))}
        </div>
      )}
    </div>
  );
}

function ConfPlataforma({ plataforma }: { plataforma: 'meta' | 'google' }) {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchConferenciaPlataforma(plataforma, filtros), [chave, versao, plataforma]);
  const [modo, setModo] = useState<'grafico' | 'tabela'>('grafico');

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Cruzando...</p>;

  if (!dados.disponivel) {
    const st = dados.base.status;
    return (
      <div className="space-y-4">
        <Vazio
          titulo={`A base de ${dados.label} ainda não está conectada`}
          texto={
            <>
              <p>{st.message}</p>
              {st.action && <p className="mt-2 text-amber-200">{st.action}</p>}
              <p className="mt-3">
                Enquanto isso: <strong>{numero(dados.resumo.leads_crm)}</strong> leads do período estão classificados como {dados.label} no CV.
              </p>
            </>
          }
          acao={
            <div className="flex flex-wrap justify-center gap-2">
              {st.help_links.map((l) => (
                <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="botao-secundario">
                  {l.label} <ExternalLink className="w-3 h-3" />
                </a>
              ))}
              <Link href="/bases" className="botao-primario">
                Bases e integrações
              </Link>
            </div>
          }
        />
        <Aviso>
          Quando conectada, esta conferência mostra, por empreendimento e campanha: leads segundo a plataforma, leads que chegaram no CV,
          a diferença, o investimento e o custo por lead real (sobre o que chegou no CRM).
        </Aviso>
      </div>
    );
  }

  const r = dados.resumo;
  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      {dados.formularios && dados.formularios.disponivel && <FormulariosMeta f={dados.formularios} onRecarregar={recarregar} />}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatTile destaque label={`Leads segundo ${dados.label}`} valor={numero(r.leads_plataforma)} sub={`${numero(r.conversas_whatsapp)} conversas no WhatsApp à parte`} />
        <StatTile label="Chegaram no CV" valor={numero(r.leads_crm)} sub={`${pct(r.pct_chegou)} do que a plataforma reporta`} />
        <StatTile label="Investimento" valor={reais(r.investimento)} />
        <StatTile label="CPL da plataforma" valor={r.cpl_plataforma ? reaisCentavos(r.cpl_plataforma) : '—'} subirEBom={false} />
        <StatTile label="CPL real (CRM)" valor={r.cpl_crm ? reaisCentavos(r.cpl_crm) : '—'} sub="investimento ÷ leads que chegaram" subirEBom={false} />
      </div>

      <Card titulo="Por dia" acao={<AlternarVisao modo={modo} setModo={setModo} />}>
        <PlataformaCrmChart serie={dados.serie} labelPlataforma={dados.label} modo={modo} />
      </Card>

      <Card titulo="Por empreendimento" subtitulo="Empreendimento atribuído pelo nome da conta de anúncio">
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Empreendimento</th>
                <th className="text-right">Segundo a plataforma</th>
                <th className="text-right">No CV</th>
                <th className="w-36">% que chegou</th>
                <th className="text-right">Investimento</th>
                <th className="text-right">CPL plataforma</th>
                <th className="text-right">CPL real</th>
                <th className="text-right">Vendas (coorte)</th>
                <th className="text-right">Custo por venda</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_empreendimento.map((e) => (
                <tr key={e.empreendimento}>
                  <td title={e.empreendimento}>{empreendimentoCurto(e.empreendimento)}</td>
                  <td className="num">{numero(e.leads_plataforma)}</td>
                  <td className="num">{numero(e.leads_crm)}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="flex-1">
                        <Medidor valor={Math.min(e.pct_chegou ?? 0, 100)} cor={SERIES.s1} />
                      </div>
                      <span className="text-[11px] tabular-nums w-12 text-right">{pct(e.pct_chegou)}</span>
                    </div>
                  </td>
                  <td className="num">{reais(e.investimento)}</td>
                  <td className="num">{e.cpl_plataforma ? reaisCentavos(e.cpl_plataforma) : '—'}</td>
                  <td className="num">{e.cpl_crm ? reaisCentavos(e.cpl_crm) : '—'}</td>
                  <td className="num">{numero(e.vendas_coorte)}</td>
                  <td className="num">{e.custo_por_venda ? reais(e.custo_por_venda) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card titulo="Por campanha" subtitulo="Nome da campanha na plataforma × utm_campaign no CV">
        <div className="overflow-x-auto">
          <table className="tabela">
            <thead>
              <tr>
                <th>Campanha</th>
                <th className="text-right">Segundo a plataforma</th>
                <th className="text-right">No CV</th>
                <th className="text-right">% que chegou</th>
                <th className="text-right">Investimento</th>
              </tr>
            </thead>
            <tbody>
              {dados.por_campanha.map((c) => (
                <tr key={c.campanha}>
                  <td>{c.campanha}</td>
                  <td className="num">{numero(c.leads_plataforma)}</td>
                  <td className="num">{numero(c.leads_crm)}</td>
                  <td className="num">{pct(c.pct_chegou)}</td>
                  <td className="num">{c.investimento ? reais(c.investimento) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="space-y-2">
        {dados.notas.map((n) => (
          <Aviso key={n}>{n}</Aviso>
        ))}
      </div>
    </div>
  );
}

const RD_COR: Record<StatusRD, string> = {
  no_cv: STATUS.bom,
  inbound_fora: STATUS.critico,
  importado: '#64748b',
  disparo: '#64748b',
  outro_fora: STATUS.atencao,
  pendente: '#334155',
};

function ConfRD() {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchConferenciaRD(filtros), [chave, versao]);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Cruzando contatos da RD com o CV...</p>;
  const r = dados.resumo;
  const ordem: StatusRD[] = ['no_cv', 'inbound_fora', 'outro_fora', 'importado', 'disparo', 'pendente'];

  if (r.contatos === 0) {
    return (
      <Vazio
        titulo="Nenhum contato da RD Station no período"
        texto={dados.base.status?.message ?? 'Amplie o período ou atualize a base da RD em Bases e integrações.'}
      />
    );
  }

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile destaque label="Contatos criados na RD" valor={numero(r.contatos)} sub={`${pct(r.pct_no_cv)} estão no CV`} />
        <StatTile
          label="Formulário sem chegar no CV"
          valor={numero(r.inbound_fora)}
          sub={`${pct(r.pct_inbound_perdido)} dos leads de formulário`}
          alerta={(r.pct_inbound_perdido ?? 0) >= 5 ? 'critico' : r.inbound_fora ? 'atencao' : undefined}
        />
        <StatTile label="Listas e disparos" valor={numero(r.importado + r.disparo)} sub="não são leads novos: ficam fora da falha" />
      </div>

      {r.pendente > 0 && (
        <Aviso tipo="atencao">
          {numero(r.pendente)} contato(s) fora do CV ainda estão com a origem em classificação ({pct(r.pct_classificado)} concluído). A
          classificação avança a cada atualização da base &quot;RD Station — Entrada dos contatos fora do CV&quot;. Até lá, eles não são
          contados como falha.
        </Aviso>
      )}

      <div className="grid xl:grid-cols-3 gap-5">
        <Card titulo="Situação dos contatos" subtitulo="Pela primeira conversão de cada contato na RD">
          <div className="space-y-3">
            {ordem.map((s) => (
              <div key={s}>
                <div className="flex justify-between text-xs mb-1 gap-2">
                  <span className="inline-flex items-center gap-2 text-slate-300">
                    <span className="w-2 h-2 rounded-full" style={{ background: RD_COR[s] }} />
                    {dados.status_labels[s]}
                  </span>
                  <span className="tabular-nums text-slate-200 shrink-0">
                    {numero(r[s])} <span className="text-slate-500">· {pct(r.contatos ? (r[s] / r.contatos) * 100 : null)}</span>
                  </span>
                </div>
                <Medidor valor={r.contatos ? (r[s] / r.contatos) * 100 : 0} cor={RD_COR[s]} />
              </div>
            ))}
          </div>
        </Card>

        <Card titulo="Formulários que não chegaram no CV" subtitulo="Onde está o furo da integração">
          {dados.inbound_fora_por_conversao.length === 0 ? (
            <p className="text-xs text-slate-500">Nenhum lead de formulário fora do CV entre os já classificados.</p>
          ) : (
            <table className="tabela">
              <tbody>
                {dados.inbound_fora_por_conversao.map((c) => (
                  <tr key={c.conversao}>
                    <td className="max-w-[240px] truncate" title={c.conversao}>
                      {c.conversao}
                    </td>
                    <td className="num font-semibold">{numero(c.contatos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card titulo="Listas importadas na RD" subtitulo="Entraram por importação: é esperado que não estejam no CV">
          <table className="tabela">
            <tbody>
              {dados.importados_por_lista.slice(0, 12).map((c) => (
                <tr key={c.conversao}>
                  <td className="max-w-[240px] truncate" title={c.conversao}>
                    {c.conversao}
                  </td>
                  <td className="num">{numero(c.contatos)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Card titulo={`Leads de formulário fora do CV (${numero(dados.itens_inbound_fora.length)})`} subtitulo="Sem dados pessoais: abra na RD para ver o contato">
        <div className="overflow-x-auto max-h-[480px]">
          <table className="tabela">
            <thead className="sticky top-0 bg-slate-900">
              <tr>
                <th>Criado na RD</th>
                <th>Primeira conversão</th>
                <th>Tipo de entrada</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {dados.itens_inbound_fora.map((i) => (
                <tr key={i.uuid}>
                  <td className="whitespace-nowrap">{data(i.data)}</td>
                  <td className="max-w-[320px] truncate" title={i.primeira_conversao ?? ''}>
                    {i.primeira_conversao}
                  </td>
                  <td className="text-slate-400">{i.tipo_entrada}</td>
                  <td>
                    {i.link_rd && (
                      <a href={i.link_rd} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200 whitespace-nowrap">
                        Abrir na RD <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function FormulariosMeta({ f, onRecarregar }: { f: ConferenciaFormulariosMeta; onRecarregar: () => void }) {
  const r = f.resumo;
  const confirmando = f.confirmacao.pendentes > 0 || f.confirmacao.em_andamento;

  // Enquanto a confirmação ao vivo roda, recarrega a conferência sozinha
  useEffect(() => {
    if (!confirmando) return;
    const t = setTimeout(onRecarregar, 6000);
    return () => clearTimeout(t);
  }, [f, confirmando, onRecarregar]);

  return (
    <div className="space-y-5">
      {!f.indice_cv.cobre_todos_os_leads && (
        <Aviso tipo="atencao">
          O índice com <strong>todos os leads do CV</strong> ainda não foi baixado: leads cadastrados antes do período da base podem
          aparecer como &quot;não chegou&quot; até a confirmação ao vivo. Baixe a base &quot;CV — Índice de todos os leads&quot; em Bases e integrações.
        </Aviso>
      )}
      {confirmando && (
        <Aviso tipo="atencao">
          Confirmando {numero(f.confirmacao.pendentes)} lead(s) direto na API do CV e do RD
          {f.confirmacao.em_andamento ? ` (${numero(f.confirmacao.feitos)} de ${numero(f.confirmacao.total)})` : ''}. Nenhum lead é dado como
          &quot;não chegou&quot; sem essa confirmação — a lista se atualiza sozinha.
        </Aviso>
      )}
      {f.confirmacao.corrigidos > 0 && (
        <Aviso>
          {numero(f.confirmacao.corrigidos)} lead(s) que não estavam na base salva foram encontrados no CV pela verificação ao vivo e saíram da
          lista de &quot;não chegaram&quot;.
        </Aviso>
      )}
      <Aviso>
        Conferência <strong>lead a lead</strong> dos formulários nativos da Meta: cada lead procurado no CV por e-mail e telefone. A
        Meta só devolve formulários dos últimos 90 dias — dados disponíveis de {data(f.cobertura.inicio)} a {data(f.cobertura.fim)}.
      </Aviso>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile destaque label="Leads de formulário no período" valor={numero(r.leads)} sub={`${numero(r.vendidos)} já viraram venda`} />
        <StatTile
          label="Não chegaram no CV"
          valor={numero(r.nao_chegou)}
          sub={
            f.rd_disponivel
              ? `${pct(r.pct_nao_chegou)} dos novos · ${numero(r.nao_chegou_mas_no_rd)} pararam no RD`
              : `${pct(r.pct_nao_chegou)} dos leads novos`
          }
          alerta={(r.pct_nao_chegou ?? 0) >= 5 ? 'critico' : r.nao_chegou ? 'atencao' : undefined}
        />
        <StatTile label="Prováveis no CV" valor={numero(r.provavel_no_cv)} sub="telefone ou nome parecido — confira o link" />
        <StatTile label="Já eram leads do CV" valor={numero(r.ja_era_lead)} sub="não é falha: origem do primeiro contato" />
      </div>

      <div className="grid xl:grid-cols-3 gap-5">
        <Card titulo="Por formulário" subtitulo="Onde os leads se perdem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Formulário</th>
                <th className="text-right">Leads</th>
                <th className="text-right">Não chegaram</th>
              </tr>
            </thead>
            <tbody>
              {f.por_formulario.slice(0, 12).map((x) => (
                <tr key={x.formulario}>
                  <td className="max-w-[200px] truncate" title={x.formulario}>
                    {x.formulario}
                  </td>
                  <td className="num">{numero(x.leads)}</td>
                  <td className="num">
                    {numero(x.nao_chegou)} <span className="text-slate-500">({pct(x.pct_nao_chegou)})</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card titulo="Por empreendimento">
          <table className="tabela">
            <thead>
              <tr>
                <th>Empreendimento</th>
                <th className="text-right">Leads</th>
                <th className="text-right">Não chegaram</th>
              </tr>
            </thead>
            <tbody>
              {f.por_empreendimento.map((x) => (
                <tr key={x.empreendimento}>
                  <td title={x.empreendimento}>{empreendimentoCurto(x.empreendimento)}</td>
                  <td className="num">{numero(x.leads)}</td>
                  <td className="num">
                    {numero(x.nao_chegou)} <span className="text-slate-500">({pct(x.pct_nao_chegou)})</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card titulo="Chegaram, mas com outra origem no CV" subtitulo="Lead de anúncio da Meta registrado como outro canal">
          {f.credito_errado_no_cv.length === 0 ? (
            <p className="text-xs text-slate-500">Todos os que chegaram estão creditados à Meta.</p>
          ) : (
            <table className="tabela">
              <tbody>
                {f.credito_errado_no_cv.map((c) => (
                  <tr key={c.canal}>
                    <td>{c.canal}</td>
                    <td className="num font-semibold">{numero(c.leads)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <ListaParaConferir f={f} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Lista para conferir no CV
// ---------------------------------------------------------------------------

const TIPO_RD: Record<string, string> = {
  inbound: 'formulário/inbound',
  importacao: 'lista importada',
  disparo: 'disparo de e-mail',
  cadastro_manual: 'cadastro manual',
  sem_conversao: 'sem conversão',
  outro: 'outro',
};

const COLUNAS_EXPORT: [string, (l: LeadFormularioConferir) => string][] = [
  ['Data', (l) => (l.data_hora || l.data || '').replace('T', ' ').slice(0, 16)],
  ['Nome', (l) => l.nome ?? ''],
  ['E-mail', (l) => l.email ?? ''],
  ['Telefone', (l) => l.telefone ?? ''],
  ['Empreendimento', (l) => l.empreendimento],
  ['Plataforma', (l) => `${l.plataforma ?? ''}${l.organico ? ' (orgânico)' : ''}`],
  ['Página', (l) => l.pagina ?? ''],
  ['Formulário', (l) => l.formulario ?? ''],
  ['Campanha', (l) => l.campanha ?? ''],
  ['Conjunto', (l) => l.conjunto ?? ''],
  ['Anúncio', (l) => l.anuncio ?? ''],
  ['Respostas', (l) => Object.entries(l.respostas || {}).map(([k, v]) => `${k}: ${v ?? ''}`).join(' | ')],
  ['No RD Station', (l) => (l.rd.no_rd ? `Sim — 1ª conversão: ${l.rd.primeira_conversao ?? '—'}` : 'Não')],
  ['Link no RD Station', (l) => l.rd.link ?? ''],
  ['Motivo (provável)', (l) => l.provavel_motivo ?? ''],
  ['Link no CV (provável)', (l) => l.provavel_link ?? ''],
  ['ID do lead na Meta', (l) => l.id],
];

async function copiarTexto(texto: string) {
  try {
    await navigator.clipboard.writeText(texto);
  } catch {
    const area = document.createElement('textarea');
    area.value = texto;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }
}

function BotaoCopiar({ texto, rotulo, className = '' }: { texto: string; rotulo: string; className?: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      onClick={async () => {
        await copiarTexto(texto);
        setOk(true);
        setTimeout(() => setOk(false), 1500);
      }}
      className={className || 'botao-secundario text-xs'}
      disabled={!texto}
    >
      {ok ? 'Copiado!' : rotulo}
    </button>
  );
}

function ListaParaConferir({ f }: { f: ConferenciaFormulariosMeta }) {
  const [aba, setAba] = useState<'nao_chegou' | 'provavel_no_cv'>('nao_chegou');
  const [busca, setBusca] = useState('');
  const [verificacoes, setVerificacoes] = useState<Record<string, EstadoVerificacao>>({});
  const [verificandoTodos, setVerificandoTodos] = useState(false);

  const verificar = async (l: LeadFormularioConferir) => {
    setVerificacoes((v) => ({ ...v, [l.id]: { carregando: true } }));
    try {
      const resultado = await verificarLead(l.email, l.telefone);
      setVerificacoes((v) => ({ ...v, [l.id]: { resultado } }));
    } catch (e) {
      setVerificacoes((v) => ({ ...v, [l.id]: { erro: (e as Error).message } }));
    }
  };
  const lista = aba === 'nao_chegou' ? f.itens_nao_chegaram : f.itens_provaveis;

  const filtrada = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    if (!termo) return lista;
    return lista.filter((l) =>
      [l.nome, l.email, l.telefone, l.formulario, l.campanha, l.conjunto, l.anuncio, l.empreendimento]
        .some((v) => (v ?? '').toLowerCase().includes(termo))
    );
  }, [lista, busca]);

  const tabela = [COLUNAS_EXPORT.map(([c]) => c), ...filtrada.map((l) => COLUNAS_EXPORT.map(([, fn]) => fn(l)))];
  const tsv = tabela.map((linha) => linha.map((c) => c.replace(/[\t\n]/g, ' ')).join('\t')).join('\n');
  const emails = Array.from(new Set(filtrada.map((l) => l.email).filter(Boolean))).join('\n');
  const telefones = Array.from(new Set(filtrada.map((l) => l.telefone).filter(Boolean))).join('\n');

  const verificarTodos = async () => {
    setVerificandoTodos(true);
    const fila = [...filtrada];
    // 3 consultas por vez para não sobrecarregar as APIs do CV e do RD
    await Promise.all(
      Array.from({ length: 3 }, async () => {
        for (let l = fila.shift(); l; l = fila.shift()) await verificar(l);
      })
    );
    setVerificandoTodos(false);
  };
  const verificados = filtrada.map((l) => verificacoes[l.id]?.resultado).filter(Boolean) as VerificacaoLead[];
  const confirmadosFora = verificados.filter((v) => v.cv.consultado && !v.cv.encontrado).length;

  const baixarCsv = () => {
    const csv = tabela.map((linha) => linha.map((c) => `"${c.replace(/"/g, '""')}"`).join(';')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `leads-meta-${aba === 'nao_chegou' ? 'nao-chegaram' : 'provaveis'}-no-cv.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card
      titulo="Leads para conferir no CV"
      subtitulo="Dados de contato e origem completa do anúncio. Copie e procure no CV (Comercial → Leads)."
    >
      <div className="flex flex-wrap items-center gap-2 mb-3">
        {(['nao_chegou', 'provavel_no_cv'] as const).map((a) => (
          <button
            key={a}
            onClick={() => setAba(a)}
            aria-pressed={aba === a}
            className={`px-3 py-1.5 rounded-md text-xs font-medium ${aba === a ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200 bg-slate-800/60'}`}
          >
            {a === 'nao_chegou' ? `Não chegaram (${numero(f.itens_nao_chegaram.length)})` : `Prováveis no CV (${numero(f.itens_provaveis.length)})`}
          </button>
        ))}
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar nome, e-mail, telefone, formulário..."
          className="controle text-xs min-w-[240px] flex-1 bg-transparent outline-none text-slate-200 placeholder:text-slate-600"
        />
        <BotaoCopiar texto={emails} rotulo="Copiar e-mails" />
        <BotaoCopiar texto={telefones} rotulo="Copiar telefones" />
        <BotaoCopiar texto={tsv} rotulo="Copiar tabela (Excel)" />
        <button onClick={verificarTodos} className="botao-primario text-xs" disabled={!filtrada.length || verificandoTodos}>
          {verificandoTodos ? 'Verificando...' : `Verificar todos agora (${numero(filtrada.length)})`}
        </button>
        <button onClick={baixarCsv} className="botao-secundario text-xs" disabled={!filtrada.length}>
          Baixar CSV
        </button>
      </div>

      {verificados.length > 0 && (
        <p className="text-[11px] text-slate-300 mb-2">
          Verificação ao vivo: <strong className="text-white">{numero(confirmadosFora)}</strong> de {numero(verificados.length)} lead(s)
          verificados <strong className="text-white">não existem no CV</strong> (busca por e-mail e telefone em todos os leads do CV, de qualquer data).
        </p>
      )}

      {aba === 'provavel_no_cv' && (
        <p className="text-[11px] text-slate-400 mb-2">
          Não achamos pelo e-mail nem pelo telefone exatos, mas há um lead no CV com o mesmo telefone escrito de outro jeito ou com o
          mesmo nome. Abra o link e confirme se é a mesma pessoa.
        </p>
      )}

      {filtrada.length === 0 ? (
        <p className="text-xs text-slate-500 py-6 text-center">Nenhum lead nesta lista.</p>
      ) : (
        <div className="overflow-x-auto max-h-[560px]">
          <table className="tabela">
            <thead className="sticky top-0 bg-slate-900 z-10">
              <tr>
                <th>Data</th>
                <th>Lead</th>
                <th>De onde veio</th>
                <th>Respostas do formulário</th>
                <th>No RD Station?</th>
                <th>{aba === 'provavel_no_cv' ? 'Provável no CV' : 'Empreendimento'}</th>
                <th>Conferir</th>
              </tr>
            </thead>
            <tbody>
              {filtrada.map((l) => (
                <tr key={l.id} className="align-top">
                  <td className="whitespace-nowrap tabular-nums text-slate-300">
                    {data(l.data)}
                    <span className="block text-[10px] text-slate-500">{(l.data_hora || '').slice(11, 16)}</span>
                  </td>
                  <td className="min-w-[220px]">
                    <span className="block text-slate-100 font-medium">{l.nome || '—'}</span>
                    {l.email && (
                      <BotaoCopiar
                        texto={l.email}
                        rotulo={l.email}
                        className="block text-left text-[11px] text-sky-300 hover:text-sky-200 break-all"
                      />
                    )}
                    {l.telefone && (
                      <BotaoCopiar
                        texto={l.telefone}
                        rotulo={l.telefone}
                        className="block text-left text-[11px] text-sky-300 hover:text-sky-200 tabular-nums"
                      />
                    )}
                  </td>
                  <td className="min-w-[260px] text-[11px] leading-relaxed">
                    <span className="block text-slate-200">
                      {l.plataforma || 'Meta'}
                      {l.organico ? ' · orgânico' : ' · anúncio'} · {l.pagina}
                    </span>
                    <span className="block text-slate-400">Formulário: {l.formulario || '—'}</span>
                    <span className="block text-slate-400">Campanha: {l.campanha || '—'}</span>
                    {l.conjunto && <span className="block text-slate-500">Conjunto: {l.conjunto}</span>}
                    {l.anuncio && <span className="block text-slate-500">Anúncio: {l.anuncio}</span>}
                  </td>
                  <td className="min-w-[180px] text-[11px] text-slate-400">
                    {Object.keys(l.respostas || {}).length === 0
                      ? '—'
                      : Object.entries(l.respostas).map(([k, v]) => (
                          <span key={k} className="block">
                            <span className="text-slate-500">{k}:</span> {v}
                          </span>
                        ))}
                  </td>
                  <td className="min-w-[160px] text-[11px]">
                    {!f.rd_disponivel ? (
                      <span className="text-slate-500">base do RD não baixada</span>
                    ) : l.rd.no_rd ? (
                      <>
                        <span className="text-amber-300 font-medium">Sim — parou entre RD e CV</span>
                        <span className="block text-slate-400">1ª conversão: {l.rd.primeira_conversao || '—'}</span>
                        {l.rd.tipo && <span className="block text-slate-500">{TIPO_RD[l.rd.tipo] ?? l.rd.tipo}</span>}
                      </>
                    ) : (
                      <span className="text-slate-400">Não — parou antes do RD</span>
                    )}
                  </td>
                  <td className="min-w-[160px] text-[11px]">
                    {aba === 'provavel_no_cv' ? (
                      <>
                        <span className="block text-slate-300">{l.provavel_motivo}</span>
                        {l.provavel_situacao && <span className="block text-slate-500">Situação: {l.provavel_situacao}</span>}
                        {l.provavel_link && (
                          <a href={l.provavel_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sky-300 hover:text-sky-200">
                            Abrir no CV <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </>
                    ) : (
                      <span title={l.empreendimento}>{empreendimentoCurto(l.empreendimento)}</span>
                    )}
                  </td>
                  <td className="min-w-[210px]">
                    <AcoesConferencia
                      lead={l}
                      cvBuscaUrl={f.cv_busca_url}
                      rdDisponivel={f.rd_disponivel}
                      estado={verificacoes[l.id]}
                      onVerificar={() => verificar(l)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[11px] text-slate-500 mt-3">
        Dados pessoais aparecem só para os leads que precisam ser conferidos. Não compartilhe este painel fora da equipe.
      </p>
    </Card>
  );
}

type EstadoVerificacao = { carregando?: boolean; resultado?: VerificacaoLead; erro?: string };

/** Base de contatos do RD Station Marketing (a busca é por e-mail). */
const RD_BASE_CONTATOS_URL = 'https://app.rdstation.com.br/leads';

function AcoesConferencia({
  lead,
  cvBuscaUrl,
  rdDisponivel,
  estado,
  onVerificar,
}: {
  lead: LeadFormularioConferir;
  cvBuscaUrl: string | null;
  rdDisponivel: boolean;
  estado?: EstadoVerificacao;
  onVerificar: () => void;
}) {
  const r = estado?.resultado;
  const chave = lead.email || lead.telefone || '';
  return (
    <div className="space-y-1.5 text-[11px]">
      {lead.confirmacao?.estado === 'confirmado' ? (
        <p className="text-emerald-300 font-medium">
          ✓ Confirmado ao vivo às{' '}
          {new Date(lead.confirmacao.verificado_em ?? '').toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}: e-mail e
          telefone não estão no CV
          {rdDisponivel && !lead.rd.no_rd && (
            <span className="block text-amber-300">
              Também não está no RD: o lead só existe na Meta (Central de Leads da página {lead.pagina ?? ''}). O formulário não enviou
              para nenhuma integração.
            </span>
          )}
        </p>
      ) : lead.confirmacao?.estado === 'pendente' ? (
        <p className="text-slate-400">Confirmando no CV e no RD…</p>
      ) : null}
      <div className="flex flex-wrap gap-1.5">
        {lead.rd.link ? (
          <a href={lead.rd.link} target="_blank" rel="noreferrer" className="botao-secundario !py-1 !px-2 text-[11px] inline-flex items-center gap-1">
            Abrir no RD <ExternalLink className="w-3 h-3" />
          </a>
        ) : (
          <a
            href={RD_BASE_CONTATOS_URL}
            target="_blank"
            rel="noreferrer"
            onClick={() => lead.email && copiarTexto(lead.email)}
            title="Abre a base de contatos do RD Station e copia o e-mail para colar na busca"
            className="botao-secundario !py-1 !px-2 text-[11px] inline-flex items-center gap-1"
          >
            Buscar no RD <ExternalLink className="w-3 h-3" />
          </a>
        )}
        {cvBuscaUrl && (
          <a
            href={cvBuscaUrl}
            target="_blank"
            rel="noreferrer"
            onClick={() => chave && copiarTexto(chave)}
            title="Abre a tela de leads do CV e copia o e-mail (ou telefone) para colar na busca"
            className="botao-secundario !py-1 !px-2 text-[11px] inline-flex items-center gap-1"
          >
            Buscar no CV <ExternalLink className="w-3 h-3" />
          </a>
        )}
        <button onClick={onVerificar} disabled={estado?.carregando} className="botao-primario !py-1 !px-2 text-[11px]">
          {estado?.carregando ? 'Verificando...' : r ? 'Verificar de novo' : 'Verificar agora'}
        </button>
      </div>

      {estado?.erro && <p className="text-rose-300">Falha na verificação: {estado.erro}</p>}

      {r && (
        <div className="rounded-md border border-slate-700 bg-slate-900/60 p-2 space-y-1">
          {!r.cv.consultado ? (
            <p className="text-amber-300">CV: não foi possível consultar ({r.cv.erros.join('; ') || 'sem e-mail e telefone'})</p>
          ) : r.cv.encontrado ? (
            <div>
              <p className="text-emerald-300 font-medium">CV: encontrado agora</p>
              {r.cv.leads.map((c) => (
                <a key={String(c.idlead)} href={c.link ?? '#'} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sky-300 hover:text-sky-200">
                  Lead #{c.idlead} · {c.situacao ?? '—'} · {(c.data_cad ?? '').slice(0, 10)} <ExternalLink className="w-3 h-3" />
                </a>
              ))}
              <p className="text-slate-500">Chegou depois da última atualização da base ou com outro cadastro.</p>
            </div>
          ) : (
            <p className="text-rose-300 font-medium">
              CV: não existe
              <span className="block font-normal text-slate-400">
                Buscado por {r.cv.consultas.map((c) => c.por).join(', ')} em todos os leads do CV.
              </span>
            </p>
          )}

          {!r.rd.consultado ? (
            <p className="text-slate-400">RD: {r.rd.erro ?? 'não consultado'}</p>
          ) : r.rd.encontrado ? (
            <a href={r.rd.link ?? '#'} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-amber-300 hover:text-amber-200">
              RD: contato existe — abrir <ExternalLink className="w-3 h-3" />
            </a>
          ) : (
            <p className="text-slate-400">RD: contato não existe</p>
          )}
          <p className="text-slate-600">Verificado às {new Date(r.verificado_em).toLocaleTimeString('pt-BR')}</p>
        </div>
      )}
    </div>
  );
}
