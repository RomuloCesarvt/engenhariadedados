'use client';

/**
 * A audiência do site (Google Analytics) compilada: de onde vêm as sessões, em que aparelho, de
 * que cidade e para qual empreendimento — cada quadro com o período anterior do lado.
 *
 * A leitura vem antes dos quadros de propósito: o que interessa não é o número solto, é o que
 * mudou em relação ao período anterior e o que fazer com isso.
 */

import React from 'react';
import Link from 'next/link';
import { AlertTriangle, Info, Lightbulb, Monitor, Smartphone, Tablet } from 'lucide-react';
import { Card, StatTile } from './ui';
import { empreendimentoCurto, numero, pct } from '../../lib/format';
import { AnaliseAudiencia, AudienciaResposta, LinhaAudiencia } from '../../types/bi';

const ESTILO_ANALISE = {
  alerta: { borda: 'border-l-rose-400', cor: 'text-rose-300', Icone: AlertTriangle, label: 'Alerta' },
  destaque: { borda: 'border-l-emerald-400', cor: 'text-emerald-300', Icone: Lightbulb, label: 'Destaque' },
  contexto: { borda: 'border-l-slate-600', cor: 'text-slate-400', Icone: Info, label: 'Contexto' },
} as const;

const ICONE_APARELHO: Record<string, typeof Smartphone> = {
  Celular: Smartphone,
  Computador: Monitor,
  Tablet: Tablet,
};

const segundos = (s: number | null) => (s === null ? '—' : `${numero(s)}s`);

/** A variação de uma linha, curtinha, para caber na tabela. */
function Variacao({ valor, antes }: { valor: number | null; antes: number }) {
  if (valor === null) {
    return <span className="text-slate-600" title="Não havia sessões neste item no período anterior">novo</span>;
  }
  const subiu = valor > 0;
  return (
    <span className={subiu ? 'text-emerald-400' : valor < 0 ? 'text-rose-400' : 'text-slate-400'} title={`${numero(antes)} no período anterior`}>
      {subiu ? '+' : ''}
      {pct(valor)}
    </span>
  );
}

/** Barra de participação: a proporção lida antes do número. */
function Barra({ valor }: { valor: number | null }) {
  return (
    <span className="inline-flex items-center gap-2 w-full">
      <span className="h-1.5 rounded-full bg-slate-800 flex-1 min-w-[40px] overflow-hidden">
        <span className="block h-full bg-sky-500/70" style={{ width: `${Math.min(valor ?? 0, 100)}%` }} />
      </span>
      <span className="tabular-nums text-slate-400 w-12 text-right">{pct(valor)}</span>
    </span>
  );
}

function Tabela({
  linhas,
  rotulo,
  campo,
  nome,
  vazio = 'Sem dados no período.',
}: {
  linhas: LinhaAudiencia[];
  rotulo: string;
  campo: keyof LinhaAudiencia;
  nome?: (l: LinhaAudiencia) => React.ReactNode;
  vazio?: string;
}) {
  if (!linhas.length) return <p className="text-xs text-slate-500">{vazio}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-slate-400 border-b border-slate-700">
            <th className="py-2 pr-2 font-medium text-left">{rotulo}</th>
            <th className="py-2 px-2 font-medium text-right">Sessões</th>
            <th className="py-2 px-2 font-medium text-left w-40">Participação</th>
            <th className="py-2 px-2 font-medium text-right">vs anterior</th>
            <th className="py-2 px-2 font-medium text-right">Engajamento</th>
            <th className="py-2 pl-2 font-medium text-right">Conversões</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={String(l[campo])} className="border-b border-slate-800/60">
              <td className="py-2 pr-2 text-slate-200">{nome ? nome(l) : String(l[campo])}</td>
              <td className="py-2 px-2 text-right tabular-nums text-slate-100">{numero(l.sessoes)}</td>
              <td className="py-2 px-2">
                <Barra valor={l.pct} />
              </td>
              <td className="py-2 px-2 text-right tabular-nums">
                <Variacao valor={l.variacao} antes={l.sessoes_antes} />
              </td>
              <td className="py-2 px-2 text-right tabular-nums text-slate-400">{pct(l.engajamento)}</td>
              <td className="py-2 pl-2 text-right tabular-nums text-slate-300">
                {numero(l.conversoes)}
                {l.conversoes > 0 && <span className="text-slate-500"> · {pct(l.taxa_conversao)}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Leitura({ analises }: { analises: AnaliseAudiencia[] }) {
  if (!analises.length) return null;
  return (
    <Card titulo="O que a comparação mostra" subtitulo="Cada leitura compara com o período anterior de mesmo tamanho e só aparece com amostra suficiente.">
      <div className="grid md:grid-cols-2 gap-2">
        {analises.map((a) => {
          const { borda, cor, Icone, label } = ESTILO_ANALISE[a.tipo];
          return (
            <div key={a.chave} className={`rounded-lg border-l-2 ${borda} bg-slate-900/40 px-3 py-2.5`}>
              <p className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide ${cor}`}>
                <Icone className="w-3 h-3" /> {label}
              </p>
              <p className="text-sm text-slate-100 font-medium mt-1 leading-snug">{a.titulo}</p>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">{a.texto}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function Aparelhos({ dispositivos }: { dispositivos: LinhaAudiencia[] }) {
  if (!dispositivos.length) return null;
  return (
    <Card
      titulo="Celular, computador e tablet"
      subtitulo="Quanto cada aparelho traz de gente e quanto cada um converte no site."
    >
      <div className="grid sm:grid-cols-3 gap-3">
        {dispositivos.map((d) => {
          const Icone = ICONE_APARELHO[d.dispositivo ?? ''] ?? Monitor;
          return (
            <div key={d.dispositivo} className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <p className="inline-flex items-center gap-1.5 text-xs text-slate-400">
                <Icone className="w-3.5 h-3.5" /> {d.dispositivo}
              </p>
              <p className="text-3xl font-semibold text-slate-50 tabular-nums mt-1">{pct(d.pct)}</p>
              <p className="text-xs text-slate-400 mt-0.5">
                {numero(d.sessoes)} sessões · <Variacao valor={d.variacao} antes={d.sessoes_antes} />
              </p>
              <p className="text-xs text-slate-500 mt-2">
                Converte <span className="text-slate-200 tabular-nums">{pct(d.taxa_conversao)}</span> · engajamento{' '}
                <span className="text-slate-200 tabular-nums">{pct(d.engajamento)}</span>
              </p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export function Audiencia({ dados }: { dados: AudienciaResposta }) {
  const t = dados.totais;
  const cidades = dados.cidades;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatTile label="Sessões no site" valor={numero(t.sessoes)} delta={t.variacao.sessoes} sub={`${numero(t.anterior.sessoes)} no período anterior`} />
        <StatTile label="Usuários" valor={numero(t.usuarios)} delta={t.variacao.usuarios} sub={`${pct(t.pct_novos)} são novos`} />
        <StatTile label="Engajamento" valor={pct(t.engajamento)} sub={`${pct(t.anterior.engajamento)} antes · ${segundos(t.tempo_medio)} por sessão`} />
        <StatTile label="Conversões no site" valor={numero(t.conversoes)} delta={t.variacao.conversoes} sub={`${pct(t.taxa_conversao)} das sessões`} />
        <StatTile label="Cidades de origem" valor={numero(cidades.distintas)} sub={`${pct(cidades.pct_das_nossas_pracas)} das sessões vêm das nossas praças`} />
        <StatTile
          label="Entram por página de produto"
          valor={pct(dados.entradas.find((e) => e.tipo === 'Página de empreendimento')?.pct ?? null)}
          sub="o resto entra pela home, pelo blog ou por página institucional"
        />
      </div>

      <Leitura analises={dados.analises} />

      <div className="grid lg:grid-cols-2 gap-5">
        <Card titulo="De onde vêm as sessões" subtitulo="Canal que o Google Analytics atribui a cada sessão.">
          <Tabela linhas={dados.canais} rotulo="Canal" campo="canal" />
        </Card>
        <Card titulo="Origem e mídia" subtitulo="O par origem/mídia por trás do canal — é onde aparece google/cpc, meta/cpc, orgânico.">
          <Tabela linhas={dados.origens} rotulo="Origem / mídia" campo="origem" />
        </Card>
      </div>

      <Aparelhos dispositivos={dados.dispositivos} />

      <div className="grid lg:grid-cols-2 gap-5">
        <Card
          titulo="Por empreendimento"
          subtitulo="Quem entrou por uma página de empreendimento. Só esse tráfego diz qual produto a pessoa procurava."
        >
          <Tabela
            linhas={dados.produtos}
            rotulo="Empreendimento"
            campo="empreendimento"
            nome={(l) => <span title={l.empreendimento}>{empreendimentoCurto(l.empreendimento ?? '')}</span>}
            vazio="Nenhuma sessão entrou por uma página de empreendimento no período."
          />
        </Card>
        <Card titulo="Por onde entram no site" subtitulo="Tipo da primeira página da visita.">
          <Tabela linhas={dados.entradas} rotulo="Tipo de página" campo="tipo" />
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <Card
          titulo="De que cidade acessam"
          subtitulo={`${numero(cidades.das_nossas_pracas)} de ${numero(cidades.sessoes)} sessões vêm de cidades onde temos empreendimento.`}
        >
          <Tabela
            linhas={cidades.cidades}
            rotulo="Cidade"
            campo="cidade"
            nome={(l) => (
              <span>
                {/* o GA4 escreve sem acento ("Avare"); quando é praça nossa, vale o nome do catálogo */}
                {l.praca ?? l.cidade}
                {l.praca ? (
                  <span className="text-sky-300/80"> · praça nossa</span>
                ) : l.estado?.length && l.cidade !== 'Não informado' ? (
                  <span className="text-slate-500"> · {l.estado[0]}</span>
                ) : null}
              </span>
            )}
          />
        </Card>
        <Card titulo="Páginas de entrada mais usadas" subtitulo="A primeira página que a pessoa abriu.">
          <Tabela
            linhas={dados.paginas}
            rotulo="Página"
            campo="pagina"
            nome={(l) => <span className="font-mono text-[11px] text-slate-300">{l.pagina || '(não informada)'}</span>}
          />
        </Card>
      </div>

      <p className="text-[11px] text-slate-500 leading-relaxed">
        {dados.observacao} Período anterior usado na comparação: {dados.anterior.inicio.split('-').reverse().join('/')} a{' '}
        {dados.anterior.fim.split('-').reverse().join('/')} ({dados.periodo.dias} dias). Cada relatório do Analytics é
        contado separadamente, então o total de sessões das cidades pode diferir um pouco do total geral.{' '}
        <Link href="/bases" className="text-sky-300 hover:text-sky-200">
          Bases e integrações
        </Link>{' '}
        mostra quando o Analytics foi lido pela última vez.
      </p>
    </div>
  );
}
