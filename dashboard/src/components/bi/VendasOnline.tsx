'use client';

/**
 * Vendas online do período, na régua da planilha revisada com a gestão. Só o tipo "Vendas SDR" conta
 * direto; em toda outra venda com conversão online na janela o sistema lê a conversa — inclusive nas
 * que o CV já conta como online pelo lead vinculado, porque ter mídia online por trás só diz que a
 * venda PODERIA ser SDR. É venda online quando o cliente quis seguir com a gente e comprou com o
 * nosso time. Se conversou e comprou com outro corretor, é venda que perdemos; se não respondeu, não
 * quis ou já estava com outro corretor, não era venda nossa. O analista pode corrigir a leitura.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, ChevronDown, Download, ExternalLink, Loader2, MessageSquare, Pencil, RefreshCw, Undo2 } from 'lucide-react';
import {
  analisarVendasOnline,
  desfazerRevisaoLeitura,
  fetchVendasOnline,
  revisarLeituraConversa,
  urlRelatorioVendasOnline,
} from '../../lib/biApi';
import { data, numero, pct, reais, reaisCompacto } from '../../lib/format';
import { CasoVendaOnline, LeituraConversa, VendasOnlineResposta } from '../../types/bi';
import { OQueResponde } from './OQueResponde';
import { Aviso, Card, ErroCarga, StatTile, Vazio } from './ui';

const INTERVALO_ENQUANTO_RODA = 4000;

const OPCOES_LEITURA: { valor: LeituraConversa; label: string }[] = [
  { valor: 'online', label: 'Venda online (a conversa confirma)' },
  { valor: 'perda', label: 'Atendemos, mas comprou com outro corretor' },
  { valor: 'nao_nossa', label: 'Não era venda nossa' },
];

const ESTILO_RESULTADO: Record<CasoVendaOnline['resultado'], { borda: string; selo: string }> = {
  caso: { borda: 'border-l-emerald-400', selo: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300' },
  perda: { borda: 'border-l-orange-400', selo: 'border-orange-500/40 bg-orange-500/10 text-orange-300' },
  nao_nossa: { borda: 'border-l-slate-500', selo: 'border-slate-600 bg-slate-700/30 text-slate-300' },
};

export function VendasOnline({ inicio, fim, filtrosAtivos = 0 }: { inicio: string; fim: string; filtrosAtivos?: number }) {
  const [dados, setDados] = useState<VendasOnlineResposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [pedindo, setPedindo] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const buscar = useCallback(async () => {
    try {
      const resposta = await fetchVendasOnline(inicio, fim);
      setDados(resposta);
      setErro(null);
      return resposta;
    } catch (e) {
      setErro((e as Error).message);
      return null;
    } finally {
      setCarregando(false);
    }
  }, [inicio, fim]);

  // Enquanto a análise roda, a tela se atualiza sozinha até ela terminar
  useEffect(() => {
    let vivo = true;
    const ciclo = async () => {
      const resposta = await buscar();
      if (vivo && resposta?.execucao?.em_andamento) {
        timer.current = setTimeout(ciclo, INTERVALO_ENQUANTO_RODA);
      }
    };
    setCarregando(true);
    ciclo();
    return () => {
      vivo = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [buscar]);

  const analisar = async () => {
    setPedindo(true);
    try {
      await analisarVendasOnline(inicio, fim);
      setErro(null);
      setDados(await fetchVendasOnline(inicio, fim));
      timer.current = setTimeout(async function ciclo() {
        const r = await fetchVendasOnline(inicio, fim).catch(() => null);
        if (r) setDados(r);
        if (r?.execucao?.em_andamento) timer.current = setTimeout(ciclo, INTERVALO_ENQUANTO_RODA);
      }, INTERVALO_ENQUANTO_RODA);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setPedindo(false);
    }
  };

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={buscar} />;
  if (carregando && !dados) return <p className="text-xs text-slate-400">Carregando a análise do período...</p>;
  if (!dados) return null;

  const rodando = dados.execucao?.em_andamento;
  const botaoAnalisar = (
    <button onClick={analisar} disabled={rodando || pedindo} className="botao-secundario inline-flex items-center gap-1.5 disabled:opacity-50">
      {rodando || pedindo ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
      {dados.disponivel ? 'Refazer a análise' : 'Analisar este período'}
    </button>
  );
  const perdas = (dados.nao_viraram ?? []).filter((v) => v.resultado === 'perda');
  const naoNossas = (dados.nao_viraram ?? []).filter((v) => v.resultado === 'nao_nossa');

  return (
    <div className="space-y-5">
      <OQueResponde
        pergunta={
          <>
            <strong>quais vendas do período são mesmo venda online.</strong> Não basta o cliente ter vindo do online: a
            conversa precisa mostrar que ele quis seguir com a gente e comprou com o nosso time.
          </>
        }
        regua={[
          <>
            A venda do tipo <strong>Vendas SDR</strong> conta direto: o CV já registra que o SDR passou o cliente ao
            especialista.
          </>,
          <>
            Em <strong>toda outra venda</strong> com conversão online do cliente <strong>na janela</strong> (90 dias antes da
            compra ou pré-campanha do lançamento) e sem corretor atendendo antes, o sistema <strong>lê a conversa</strong>:
            relatos da GlorIA, anotações do SDR, visita agendada, SQL e motivo de cancelamento. Vale também para as que o CV
            conta como online pelo lead vinculado — ter mídia online só diz que a venda <em>poderia</em> ser SDR.
          </>,
          <>
            Conversou e comprou com o time: é <strong>venda online</strong> — e, quando o CV não a conta assim, vira{' '}
            <strong>caso para investigar</strong>. Conversou e comprou com outro corretor:{' '}
            <strong>atendemos e perdemos</strong>. Não respondeu, não quis, já estava com outro corretor ou era pós-venda:{' '}
            <strong>não era venda nossa</strong> — mesmo que o CV conte como online.
          </>,
          <>
            A leitura é automática. Confira a conversa e, se precisar, use <strong>Corrigir leitura</strong>: a correção vale
            para a tela e para a planilha.
          </>,
        ]}
        naoResponde={
          <>
            o que aconteceu fora do CV: conversa por telefone ou com o corretor que não foi registrada não aparece aqui. Para
            ver todos os sinais de origem de cada venda, use
          </>
        }
        outra={{ href: '/vendas', label: 'Vendas × leads' }}
      />

      {rodando && (
        <Aviso>
          <span className="inline-flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Analisando {dados.execucao.periodo?.replace('..', ' a ')}: {dados.execucao.mensagem || 'lendo o CV...'} A tela
            se atualiza sozinha quando terminar.
          </span>
        </Aviso>
      )}
      {dados.execucao?.erro && <Aviso tipo="atencao">A última análise falhou: {dados.execucao.erro}</Aviso>}
      {filtrosAtivos > 0 && (
        <Aviso>
          Esta análise cobre <strong>todos os empreendimentos com venda no período</strong>: o filtro de empreendimento e
          praça não muda os números aqui.
        </Aviso>
      )}

      {!dados.disponivel ? (
        <Vazio
          titulo={dados.regra_desatualizada ? 'A análise gravada deste período usa a regra anterior' : 'Este período ainda não foi analisado'}
          texto={
            dados.regra_desatualizada
              ? 'Refaça a análise para aplicar a leitura das conversas.'
              : 'A análise lê no CV os compradores de cada venda do período, cruza com todos os leads e lê as conversas. Leva alguns minutos na primeira vez; depois fica pronta.'
          }
          acao={botaoAnalisar}
        />
      ) : (
        <>
          <Resumo dados={dados} inicio={inicio} fim={fim} acao={botaoAnalisar} />
          <PorProduto dados={dados} />
          <Lista
            titulo="Casos para investigar: vendas online não registradas no CV"
            texto="A conversa mostra que o cliente seguiu no atendimento e comprou com o nosso time. Para a venda contar como online, vincule o lead à reserva no CV."
            vendas={dados.casos ?? []}
            vazio="Nenhuma venda online fora do CV neste período."
            onAtualizar={buscar}
          />
          <Lista
            titulo="O que estamos perdendo: atendemos, mas o cliente comprou com outro corretor"
            texto="Conversaram com a GlorIA ou o SDR e fecharam com outro corretor. Não contam como venda online."
            vendas={perdas}
            onAtualizar={buscar}
          />
          <Lista
            titulo="Vieram do online, mas não era venda nossa"
            texto="Já estavam com outro corretor, não responderam, não tiveram interesse ou era pós-venda. Inclui vendas que o CV conta como online pelo lead vinculado."
            vendas={naoNossas}
            onAtualizar={buscar}
            fechada
          />
        </>
      )}
    </div>
  );
}

function Resumo({ dados, inicio, fim, acao }: { dados: VendasOnlineResposta; inicio: string; fim: string; acao: React.ReactNode }) {
  const r = dados.resumo!;
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatTile label="Vendas no período" valor={numero(r.vendas)} sub={`${reaisCompacto(r.vgv)} · ${numero(r.distratos)} distrato(s)`} />
        <StatTile
          label="Vendas online (pela conversa)"
          valor={numero(r.online)}
          sub={`${pct(r.vendas ? (r.online / r.vendas) * 100 : 0)} das vendas · ${numero(r.online_cv_sdr)} Vendas SDR, ${numero(r.online_cv_lead)} lead online confirmado, ${numero(r.casos)} caso(s)`}
        />
        <StatTile
          label="Online no CV"
          valor={numero(r.online_cv)}
          sub={`como o BI gerencial conta · ${numero(r.tirados_do_online)} que a conversa desmente (${reaisCompacto(r.vgv_tirados_do_online)})`}
        />
        <StatTile
          destaque
          label="Casos: vendas online não registradas"
          valor={numero(r.casos)}
          sub={`${reaisCompacto(r.vgv_casos)}${r.casos_distrato ? ` · ${numero(r.casos_distrato)} distratada(s) depois` : ''}`}
        />
        <StatTile label="Atendemos e perdemos" valor={numero(r.perdas)} sub={`${reaisCompacto(r.vgv_perdas)} · comprou com outro corretor`} />
        <StatTile
          label="Não era venda nossa"
          valor={numero(r.nao_nossas + r.ja_atendia)}
          sub={`${numero(r.nao_nossas)} pela conversa · ${numero(r.ja_atendia)} com corretor já atendendo`}
        />
      </div>

      <Card
        titulo="A planilha deste período"
        subtitulo={`Vendas de ${data(dados.periodo.inicio)} a ${data(dados.periodo.fim)}${dados.gerado_em ? ` · análise de ${data(dados.gerado_em)}` : ''}${r.leituras_revisadas ? ` · ${numero(r.leituras_revisadas)} leitura(s) revisada(s)` : ''}`}
        acao={
          <div className="flex items-center gap-2">
            {acao}
            <a href={urlRelatorioVendasOnline(inicio, fim)} className="botao-primario inline-flex items-center gap-1.5">
              <Download className="w-3.5 h-3.5" /> Baixar planilha
            </a>
          </div>
        }
      >
        <p className="text-xs text-slate-300 leading-relaxed">
          Abas: <strong>Leia primeiro</strong>, <strong>Resumo por produto</strong>, <strong>Casos para investigar</strong>,{' '}
          <strong>Não viraram venda online</strong> (em laranja, o que perdemos), <strong>Todas as vendas</strong> e{' '}
          <strong>Como foi feito</strong>. A planilha sai na hora, já com as leituras corrigidas.
        </p>
      </Card>
    </>
  );
}

const celula = 'py-2 px-2 text-right tabular-nums text-slate-300';

function PorProduto({ dados }: { dados: VendasOnlineResposta }) {
  const linhas = dados.por_produto ?? [];
  if (!linhas.length) return null;
  const cabecalho = ['Produto', 'Vendas', 'Online (conversa)', '% online', 'Online no CV', 'CV diz online, a conversa não', 'Com conversão online', 'Comprou com outro corretor', 'Casos', 'VGV dos casos', 'Perdemos'];
  return (
    <Card titulo="Por produto">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400 border-b border-slate-700">
              {cabecalho.map((c, i) => (
                <th key={c} className={`py-2 px-2 font-medium ${i === 0 ? 'text-left pl-0' : 'text-right'}`}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((l) => (
              <tr key={l.produto} className="border-b border-slate-800/60">
                <td className="py-2 pr-2 text-slate-200">{l.produto}</td>
                <td className={celula}>{numero(l.vendas)}</td>
                <td className={`${celula} text-slate-100`}>{numero(l.online)}</td>
                <td className={celula}>{pct(l.pct_online)}</td>
                <td className={celula}>{numero(l.online_cv)}</td>
                <td className={celula}>{numero(l.tirados_do_online)}</td>
                <td className={celula}>{numero(l.com_conversao)}</td>
                <td className={celula}>{numero(l.outro_corretor)}</td>
                <td className={`${celula} font-semibold text-emerald-300`}>{numero(l.casos)}</td>
                <td className={celula}>{reaisCompacto(l.vgv_casos)}</td>
                <td className={`${celula} text-orange-300`}>{numero(l.perdas)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Lista({
  titulo,
  texto,
  vendas,
  vazio,
  onAtualizar,
  fechada = false,
}: {
  titulo: string;
  texto: string;
  vendas: CasoVendaOnline[];
  vazio?: string;
  onAtualizar: () => void;
  fechada?: boolean;
}) {
  const [aberta, setAberta] = useState(!fechada);
  if (!vendas.length && !vazio) return null;
  const vgv = vendas.reduce((soma, v) => soma + v.valor, 0);
  return (
    <section className="space-y-3">
      <button onClick={() => setAberta(!aberta)} className="w-full text-left">
        <h2 className="text-sm font-semibold text-slate-100 inline-flex items-center gap-1.5">
          {titulo}{' '}
          <span className="text-slate-500 font-normal">
            ({numero(vendas.length)}
            {vendas.length ? ` · ${reaisCompacto(vgv)}` : ''})
          </span>
          <ChevronDown className={`w-3.5 h-3.5 text-slate-500 transition-transform ${aberta ? 'rotate-180' : ''}`} />
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">{texto}</p>
      </button>
      {aberta && (vendas.length ? vendas.map((v) => <CartaoCaso key={v.idreserva} venda={v} onAtualizar={onAtualizar} />) : (
        <p className="text-xs text-slate-500">{vazio}</p>
      ))}
    </section>
  );
}

function CartaoCaso({ venda: v, onAtualizar }: { venda: CasoVendaOnline; onAtualizar: () => void }) {
  const [conversa, setConversa] = useState(false);
  const [detalhes, setDetalhes] = useState(false);
  const [editando, setEditando] = useState(false);
  const [leitura, setLeitura] = useState<LeituraConversa>(v.leitura.leitura || 'nao_nossa');
  const [texto, setTexto] = useState(v.leitura.revisada ? v.leitura.texto || '' : '');
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const estilo = ESTILO_RESULTADO[v.resultado];
  const distrato = v.situacao === 'Distrato';

  const salvar = async () => {
    setSalvando(true);
    setErro(null);
    try {
      await revisarLeituraConversa(v.idreserva, leitura, texto);
      setEditando(false);
      onAtualizar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  };

  const desfazer = async () => {
    setSalvando(true);
    setErro(null);
    try {
      await desfazerRevisaoLeitura(v.idreserva);
      onAtualizar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  };

  return (
    <article className={`painel p-4 border-l-4 ${estilo.borda}`}>
      <div className="flex flex-wrap items-center gap-2 mb-1.5">
        <span className="text-[10px] text-slate-500 uppercase tracking-wide">{v.produto}</span>
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium ${estilo.selo}`}>
          {v.leitura.leitura_label || v.resultado_label}
        </span>
        {v.leitura.motivo && v.leitura.motivo !== 'conversou' && v.leitura.motivo !== 'revisado' && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium border-slate-600 bg-slate-700/30 text-slate-300">
            {v.leitura.motivo_label}
          </span>
        )}
        {v.leitura.revisada && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium border-sky-500/40 bg-sky-500/10 text-sky-300">
            Leitura revisada{v.leitura.revisado_em ? ` em ${data(v.leitura.revisado_em)}` : ''}
          </span>
        )}
        {distrato && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium border-rose-500/40 bg-rose-500/10 text-rose-300">
            <AlertTriangle className="w-3 h-3" /> Distrato em {data(v.data_distrato)}
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold text-white">
        {v.cliente} <span className="text-slate-400 font-normal">· {reais(v.valor)}</span>
      </h3>
      <p className="text-xs text-slate-200 mt-1 leading-relaxed">{v.leitura.texto}</p>
      {v.conversao && <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">{v.conversao}</p>}

      <dl className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 text-[11px]">
        <Item rotulo="Venda" valor={`${data(v.data_venda)} · reserva ${v.idreserva}`} />
        <Item rotulo="Comprou com" valor={[v.corretor, v.imobiliaria].filter(Boolean).join(' · ') || '—'} />
        <Item rotulo="Canal da venda no CV" valor={v.canal} />
        <Item rotulo="Tratativa do lead" valor={v.tratativa} />
      </dl>

      <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
        <button onClick={() => setConversa(!conversa)} className="botao-secundario inline-flex items-center gap-1">
          <MessageSquare className="w-3 h-3" /> O que a conversa mostra
          <ChevronDown className={`w-3 h-3 transition-transform ${conversa ? 'rotate-180' : ''}`} />
        </button>
        <button onClick={() => setDetalhes(!detalhes)} className="botao-secundario inline-flex items-center gap-1">
          Detalhes <ChevronDown className={`w-3 h-3 transition-transform ${detalhes ? 'rotate-180' : ''}`} />
        </button>
        <button onClick={() => setEditando(!editando)} className="botao-secundario inline-flex items-center gap-1">
          <Pencil className="w-3 h-3" /> Corrigir leitura
        </button>
        {v.lead?.link && (
          <a href={v.lead.link} target="_blank" rel="noreferrer" className="botao-secundario inline-flex items-center gap-1">
            Abrir lead {v.lead.id} <ExternalLink className="w-3 h-3" />
          </a>
        )}
        {v.link_reserva && (
          <a href={v.link_reserva} target="_blank" rel="noreferrer" className="botao-secundario inline-flex items-center gap-1">
            Abrir reserva <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>

      {conversa && (
        <div className="mt-3 pt-3 border-t border-slate-800 space-y-1.5 text-[11px]">
          {v.leitura.destaques.length > 0 && (
            <p className="text-slate-300">
              <span className="text-slate-500">Sinais de atendimento: </span>
              {v.leitura.destaques.join(' · ')}
            </p>
          )}
          {v.leitura.trechos.length ? (
            v.leitura.trechos.map((t, i) => (
              <p key={i} className="text-slate-200 leading-relaxed">
                <span className="text-slate-500 tabular-nums">{t.data ? data(t.data) : '—'} · lead {t.lead}: </span>
                {t.texto}
              </p>
            ))
          ) : (
            <p className="text-slate-500">Nenhum registro de conversa no lead online desse período.</p>
          )}
        </div>
      )}

      {detalhes && (
        <div className="mt-3 pt-3 border-t border-slate-800 grid md:grid-cols-2 gap-x-6 gap-y-1 text-[11px]">
          <Item rotulo="Nome no lead" valor={v.lead?.nome || '—'} />
          <Item rotulo="Origem do lead" valor={v.lead?.origem || '—'} />
          <Item rotulo="Como a origem foi identificada" valor={v.lead?.detalhe_origem || '—'} />
          <Item rotulo="Janela usada" valor={v.janela} />
          <Item rotulo="Tipo de venda no CV" valor={v.tipo_venda} />
          <div className="md:col-span-2 mt-1">
            <dt className="text-slate-500">Registros de tratativa</dt>
            <dd className="text-slate-200 whitespace-pre-line leading-relaxed">{v.registros_tratativa}</dd>
          </div>
        </div>
      )}

      {editando && (
        <div className="mt-3 pt-3 border-t border-slate-800 space-y-2">
          <div className="flex flex-wrap gap-2">
            {OPCOES_LEITURA.map((o) => (
              <label
                key={o.valor}
                className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[11px] cursor-pointer ${
                  leitura === o.valor ? 'border-sky-500/60 bg-sky-500/10 text-sky-200' : 'border-slate-700 text-slate-300'
                }`}
              >
                <input type="radio" className="sr-only" checked={leitura === o.valor} onChange={() => setLeitura(o.valor)} />
                {o.label}
              </label>
            ))}
          </div>
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            rows={2}
            placeholder="O que a conversa mostra (opcional; sem texto, fica o texto da leitura automática)"
            className="w-full rounded border border-slate-700 bg-slate-900/60 p-2 text-xs text-slate-200"
          />
          {erro && <p className="text-[11px] text-rose-300">{erro}</p>}
          <div className="flex flex-wrap justify-end gap-2">
            {v.leitura.revisada && (
              <button onClick={desfazer} disabled={salvando} className="botao-secundario inline-flex items-center gap-1 disabled:opacity-50">
                <Undo2 className="w-3 h-3" /> Voltar à leitura automática
              </button>
            )}
            <button onClick={() => setEditando(false)} className="botao-secundario">
              Cancelar
            </button>
            <button onClick={salvar} disabled={salvando} className="botao-primario inline-flex items-center gap-1 disabled:opacity-50">
              {salvando && <Loader2 className="w-3 h-3 animate-spin" />} Salvar leitura
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

function Item({ rotulo, valor }: { rotulo: string; valor: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-slate-500">{rotulo}</dt>
      <dd className="text-slate-200 truncate" title={typeof valor === 'string' ? valor : undefined}>
        {valor}
      </dd>
    </div>
  );
}
