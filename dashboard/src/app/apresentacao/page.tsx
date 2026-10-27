'use client';

import React, { Suspense, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Download, Loader2 } from 'lucide-react';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { Aviso, ErroCarga } from '../../components/bi/ui';
import { Quadro, QuadroRef } from '../../components/apresentacao/Slide';
import {
  SlideAnuncios,
  SlideAnunciosGoogle,
  SlideCenarioPraca,
  SlideConcorrencia,
  SlideAnunciosNovos,
  SlideQuadroAnuncios,
  SlideCriativos,
  SlideDetalhesGoogle,
  SlideEmpreendimentos,
  SlideGoogle,
  SlideCtwFormulario,
  SlideMetas,
  SlideCustoOrigem,
  SlideOrganicos,
  SlideOrigem,
  SlideResumo,
  SlideSite,
  SlideTermosPesquisa,
  SlideTermosPmax,
} from '../../components/apresentacao/slides';
import { fetchApresentacao, fetchCenario } from '../../lib/biApi';
import { empreendimentoCurto } from '../../lib/format';
import { Apresentacao } from '../../types/apresentacao';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell titulo="Apresentação" subtitulo="Os slides da reunião de segunda: baixe cada um em PNG ou copie e cole direto no PowerPoint">
        <ApresentacaoSemanal />
      </AppShell>
    </Suspense>
  );
}

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

function rotuloPeriodo(d: Apresentacao) {
  const { inicio, fim } = d.periodo;
  const mesmoMes = inicio.slice(0, 7) === fim.slice(0, 7);
  const mes = mesmoMes ? `${MESES[Number(fim.slice(5, 7)) - 1]}/${fim.slice(0, 4)} · ` : '';
  return `${mes}${dm(inicio)} a ${dm(fim)}${mesmoMes ? '' : `/${fim.slice(0, 4)}`}`;
}

function ApresentacaoSemanal() {
  const router = useRouter();
  const params = useSearchParams();
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();

  // A reunião é do mês em andamento: sem período na URL, abre em "Este mês" (as demais telas abrem em 30 dias)
  useEffect(() => {
    if (!params.get('periodo')) {
      const q = new URLSearchParams(params.toString());
      q.set('periodo', 'mes_atual');
      router.replace(`/apresentacao?${q.toString()}`, { scroll: false });
    }
  }, [params, router]);

  const { dados, erro, carregando, recarregar } = useDados(() => fetchApresentacao(filtros), [chave, versao]);
  // O cenário carrega à parte: lê 14 meses de Meta e Google e não deve segurar os outros slides
  const cen = useDados(() => fetchCenario(filtros), [chave, versao]);
  const refs = useRef<(QuadroRef | null)[]>([]);
  const [baixando, setBaixando] = useState(false);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Compilando leads, anúncios, Google e site do período...</p>;

  const periodo = `${rotuloPeriodo(dados)}  ·  vs ${dm(dados.comparacao.inicio)} a ${dm(dados.comparacao.fim)}`;
  const filtro =
    dados.filtro.empreendimentos.length || dados.filtro.pracas.length
      ? [...dados.filtro.empreendimentos.map(empreendimentoCurto), ...dados.filtro.pracas].join(' · ')
      : 'Todos os empreendimentos';
  const cvAte = dados.bases.find((b) => b.base === 'cv_leads')?.dados_de;
  const fonteRodape = `Leads: CV (cadastro) · Investimento: Meta Ads e Google Ads${cvAte ? ` · dados do CV até ${cvAte.slice(8, 10)}/${cvAte.slice(5, 7)}` : ''}`;

  const slugPraca = (t: string) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-');
  // Depois dos campeões de cada praça: o quadro completo de anúncios (Meta e Google) e a concorrência
  const extrasDaPraca = (praca: string) => [
    ...(dados.anuncios_por_praca?.[praca]?.novos
      ? [
          {
            id: `apresentacao-novos-${slugPraca(praca)}`,
            titulo: `Anúncios novos · ${praca}`,
            tituloSlide: `Anúncios novos em ${praca}`,
            subtitulo: 'Como estão se comportando os que entraram neste mês',
            filtro: praca,
            rodape: 'Resultados da Meta = formulários + conversas de WhatsApp registrados no anúncio. Novo = começou a gastar dentro do mês selecionado. Comparados com a mediana dos anúncios que já rodavam antes. O CV só liga ao anúncio parte dos leads (clique no WhatsApp não traz o anúncio), então os leads do CV de anúncio novo ficam abaixo do real.',
            corpo: <SlideAnunciosNovos d={dados} praca={praca} />,
          },
        ]
      : []),
    ...(dados.anuncios_por_praca?.[praca]?.quadro
      ? [
          {
            id: `apresentacao-quadro-${slugPraca(praca)}`,
            titulo: `Quadro de anúncios · ${praca}`,
            tituloSlide: `Todos os anúncios de ${praca}`,
            subtitulo: 'Meta e Google: custo, leads, SQL e conversão',
            filtro: praca,
            rodape: `Anúncios da Meta e campanhas do Google de ${praca}, no período.`,
            corpo: <SlideQuadroAnuncios d={dados} praca={praca} />,
          },
        ]
      : []),
    ...(dados.concorrencia?.pracas?.[praca]
      ? [
          {
            id: `apresentacao-concorrencia-${slugPraca(praca)}`,
            titulo: `Concorrência · ${praca}`,
            tituloSlide: `Concorrência em ${praca}`,
            subtitulo: 'Quem anuncia, a pressão no leilão e o que a nossa conta mostra',
            filtro: praca,
            rodape: 'Leilão do Google: participação de impressões da própria conta. Anunciantes: Biblioteca de Anúncios da Meta (amostra).',
            corpo: <SlideConcorrencia d={dados} praca={praca} />,
          },
        ]
      : []),
  ];

  const slides: { id: string; titulo: string; tituloSlide: string; subtitulo?: string; rodape?: string; periodo?: string; filtro?: string; corpo: React.ReactNode }[] = [
    {
      id: 'apresentacao-1-resumo',
      titulo: '1 · Resumo do mês',
      tituloSlide: 'Resumo do mês',
      subtitulo: 'Investimento, leads e custo por fonte',
      rodape: `${fonteRodape}. Leads e origem como no Power BI da gestão (conversão do mês). *SQL: leads que entraram em SQL (ou além) no período, pelo histórico do CV, como no BI; pode diferir em poucas unidades.`,
      corpo: <SlideResumo d={dados} />,
    },
    ...(cen.dados
      ? [
          ...cen.dados.cenarios_por_praca.flatMap((p) => [{
            id: `apresentacao-cenario-${p.praca.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-')}`,
            titulo: `Cenário · ${p.praca}`,
            tituloSlide: `Cenário de ${p.praca}`,
            subtitulo: 'O que mudou no CPL, no leilão e na concorrência desta praça',
            periodo: `Antes da campanha (${cen.dados!.janelas.base[0].slice(8, 10)}/${cen.dados!.janelas.base[0].slice(5, 7)} a ${cen.dados!.janelas.base[1].slice(8, 10)}/${cen.dados!.janelas.base[1].slice(5, 7)})  ·  agora (${cen.dados!.janelas.recente[0].slice(8, 10)}/${cen.dados!.janelas.recente[0].slice(5, 7)} a ${cen.dados!.janelas.recente[1].slice(8, 10)}/${cen.dados!.janelas.recente[1].slice(5, 7)})`,
            filtro: p.praca,
            rodape: 'Indício, não prova: eleição, concorrência e o nosso investimento mexem no leilão ao mesmo tempo. CPL da plataforma. Concorrência: anúncios ativos na Meta que citam a praça.',
            corpo: <SlideCenarioPraca p={p} />,
          },
          ...(dados.anuncios_por_praca?.[p.praca]
            ? [
                {
                  id: `apresentacao-anuncios-${p.praca.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-')}`,
                  titulo: `Anúncios campeões · ${p.praca}`,
                  tituloSlide: `Anúncios que melhor performaram em ${p.praca}`,
                  subtitulo: 'Menor custo, mais leads, mais SQL e maior conversão',
                  filtro: p.praca,
                  rodape: `Anúncios da Meta de ${p.praca}. Amostra mínima: ${dados.anuncios_por_praca[p.praca].minimos.leads_cpl}+ leads para custo, ${dados.anuncios_por_praca[p.praca].minimos.leads_conversao}+ para conversão.`,
                  corpo: <SlideAnuncios d={dados} praca={p.praca} />,
                },
              ]
            : // Sem o cenário (ainda carregando ou com erro), os anúncios de cada praça aparecem do mesmo jeito
        Object.keys(dados.anuncios_por_praca ?? {}).map((praca) => ({
          id: `apresentacao-anuncios-${praca.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-')}`,
          titulo: `Anúncios campeões · ${praca}`,
          tituloSlide: `Anúncios que melhor performaram em ${praca}`,
          subtitulo: 'Menor custo, mais leads, mais SQL e maior conversão',
          filtro: praca,
          rodape: `Anúncios da Meta de ${praca}.`,
          corpo: <SlideAnuncios d={dados} praca={praca} />,
        }))),
          ...extrasDaPraca(p.praca),
        ]),
        ]
      : []),
    {
      id: 'apresentacao-2-origem',
      titulo: '2 · Origem dos leads',
      tituloSlide: 'Origem dos leads',
      subtitulo: 'Pago × orgânico e de onde vieram os orgânicos',
      rodape:
        'Origem = mídia da conversão do lead no CV, com os mesmos nomes e a mesma regra do Power BI da gestão (origens offline, como corretor e indicação, ficam fora).',
      corpo: <SlideOrigem d={dados} />,
    },
    ...(dados.metas_leads
      ? [
          {
            id: 'apresentacao-1b-metas',
            titulo: '1b · Meta de leads por praça',
            tituloSlide: 'Meta de leads por praça',
            subtitulo: 'Meta do mês, o que faltou nos meses anteriores, o que atingimos e quanto investir para chegar lá',
            rodape: 'Meta de leads da planilha "Metas Anuais - comercial e mkt" (cenário de 100%). Leads atingidos: MQL online pela regra do Power BI da gestão. O que não é atingido no mês passa para a meta do mês seguinte.',
            corpo: <SlideMetas d={dados} />,
          },
        ]
      : []),
    {
      id: 'apresentacao-2a-custo-origem',
      titulo: '2a · Custo por origem',
      tituloSlide: 'Custo por origem',
      subtitulo: 'Meta e Google com custo; orgânicas abertas por onde vieram',
      rodape: 'Investimento: Meta Ads e Google Ads. Leads e origem como no Power BI da gestão, com os leads de rastro de anúncio contados como mídia paga.',
      corpo: <SlideCustoOrigem d={dados} />,
    },
    {
      id: 'apresentacao-2c-ctw-formulario',
      titulo: '2c · Clique no WhatsApp × formulário',
      tituloSlide: 'Clique no WhatsApp × formulário',
      subtitulo: 'Custo e resultado de cada tipo de campanha da Meta, por praça',
      rodape: 'Campanha pelo nome (whatsapp = clique no WhatsApp; cadastro/gdc = formulário). Formulário = lead que preencheu formulário da Meta até 30 dias antes ou depois (casado por e-mail ou telefone; em Itu, marcador do CV). "Meta registra" = contagem da própria Meta.',
      corpo: <SlideCtwFormulario d={dados} />,
    },
    ...((dados.organicos_origem?.total || dados.organicos_origem?.reclassificados?.total)
      ? [
          {
            id: 'apresentacao-2b-organicos',
            titulo: '2b · Orgânicos: de onde vieram',
            tituloSlide: 'Orgânicos e indicação: o que há por trás',
            subtitulo: 'Anúncio que virou conversa, busca, WhatsApp direto e Indique e Ganhe',
            rodape: 'Cada lead orgânico ou de indicação aberto no CV: UTM, conversas anteriores e a base do BeeViral. A conta do BI não muda; aqui aparece o que está por trás dela.',
            corpo: <SlideOrganicos d={dados} />,
          },
        ]
      : []),
    {
      id: 'apresentacao-3-empreendimentos',
      titulo: '3 · Por empreendimento',
      tituloSlide: 'Resultado por empreendimento',
      subtitulo: 'Onde o investimento virou lead',
      rodape: fonteRodape,
      corpo: <SlideEmpreendimentos d={dados} />,
    },
    {
      id: 'apresentacao-5-pmax',
      titulo: '5 · Google: o que buscaram no Performance Max',
      tituloSlide: 'Performance Max: o que as pessoas buscaram',
      subtitulo: 'Termos de pesquisa reais, com custo e conversões',
      rodape:
        'Termos reais da API do Google Ads. O Google omite os termos com pouquíssimo volume. Conversão é a ação principal da conta do Google, não a venda do CV.',
      corpo: <SlideTermosPmax d={dados} />,
    },
    {
      id: 'apresentacao-6-pesquisa',
      titulo: '6 · Google: termos das campanhas de pesquisa',
      tituloSlide: 'Campanhas de pesquisa: o que as pessoas buscaram',
      subtitulo: 'Termos de pesquisa reais, com custo e conversões',
      rodape: 'Termos reais da API do Google Ads. Conversão é a ação principal da conta do Google, não a venda do CV.',
      corpo: <SlideTermosPesquisa d={dados} />,
    },
    {
      id: 'apresentacao-7-google-anuncios',
      titulo: '7 · Google: anúncios que melhor performaram',
      tituloSlide: 'Google: anúncios que melhor performaram',
      subtitulo: 'Anúncios de pesquisa e grupos de recursos do Performance Max',
      rodape: 'No Performance Max, o “anúncio” é o grupo de recursos (textos e imagens). Conversões e custo são os da conta do Google Ads.',
      corpo: <SlideAnunciosGoogle d={dados} />,
    },
    {
      id: 'apresentacao-8-google',
      titulo: '8 · Google: campanhas e palavras-chave',
      tituloSlide: 'Google Ads: campanhas e palavras-chave',
      subtitulo: 'Onde o investimento do Google trouxe conversão',
      rodape: 'Conversões e custo por conversão são os da conta do Google Ads (não o lead no CV).',
      corpo: <SlideGoogle d={dados} />,
    },
    {
      id: 'apresentacao-9-google-detalhes',
      titulo: '9 · Google: conversões, aparelho e impressões',
      tituloSlide: 'Google: como as conversões acontecem',
      subtitulo: 'Ações de conversão, aparelho e participação de impressões',
      rodape: 'Dados da conta do Google Ads. A ação “Clique no botão WhatsApp” conta como conversão, mas ainda não é lead no CV.',
      corpo: <SlideDetalhesGoogle d={dados} />,
    },
    {
      id: 'apresentacao-10-criativos',
      titulo: '10 · Criativos: tema e formato',
      tituloSlide: 'O que os criativos mostram',
      subtitulo: 'Leads, custo e SQL por tema e por formato dos anúncios da Meta',
      rodape: dados.criativos.observacao,
      corpo: <SlideCriativos d={dados} />,
    },
    {
      id: 'apresentacao-11-site',
      titulo: '11 · Site (Google Analytics)',
      tituloSlide: 'Site: de onde vem o tráfego',
      subtitulo: 'Origem (UTM), páginas de entrada e conversões do site',
      rodape: `Google Analytics${dados.site.dados_ate ? ` · dados até ${dm(dados.site.dados_ate)}` : ''}. Conversão do site é o evento principal da propriedade, não o lead no CV.`,
      corpo: <SlideSite d={dados} />,
    },
  ];

  async function baixarTodos() {
    setBaixando(true);
    try {
      for (const ref of refs.current) {
        await ref?.baixar();
        await new Promise((r) => setTimeout(r, 400));
      }
    } finally {
      setBaixando(false);
    }
  }

  return (
    <div className={`space-y-8 max-w-[1100px] transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-slate-400 max-w-xl">
          Use os filtros acima para escolher o período (“Este mês” vai até hoje; “Personalizado” fecha em outra data) e o empreendimento. A
          comparação é sempre o mesmo intervalo do mês anterior.
        </p>
        <button onClick={baixarTodos} disabled={baixando} className="botao-primario">
          {baixando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          Baixar os {slides.length} slides
        </button>
      </div>

      {dados.completude && !dados.completude.ok && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          <p className="font-semibold mb-1">Antes de apresentar: {dados.completude.itens.length} pendência(s) nos dados</p>
          <ul className="list-disc pl-5 space-y-0.5">
            {dados.completude.itens.map((i) => (
              <li key={i.texto} className={i.nivel === 'erro' ? 'font-semibold' : ''}>{i.texto}</li>
            ))}
          </ul>
        </div>
      )}
      {dados.avisos.length > 0 && (
        <div className="grid md:grid-cols-2 gap-2">
          {dados.avisos.map((a) => (
            <Aviso key={a} tipo="atencao">
              {a}
            </Aviso>
          ))}
        </div>
      )}

      {slides.map((s, i) => (
        <Quadro
          key={s.id}
          ref={(r) => {
            refs.current[i] = r;
          }}
          id={s.id.replace(/^apresentacao-(\d+-)?/, `apresentacao-${String(i + 1).padStart(2, '0')}-`)}
          titulo={`${i + 1} · ${s.titulo.replace(/^\d+ · /, '')}`}
          tituloSlide={s.tituloSlide}
          subtituloSlide={s.subtitulo}
          periodo={s.periodo ?? periodo}
          filtro={s.filtro ?? filtro}
          rodape={s.rodape}
        >
          {s.corpo}
        </Quadro>
      ))}
    </div>
  );
}
