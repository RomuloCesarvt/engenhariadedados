'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import { AppShell, useShell } from '../../components/bi/AppShell';
import { useDados, useFiltros } from '../../components/bi/useFiltros';
import { Audiencia } from '../../components/bi/Audiencia';
import { OQueResponde } from '../../components/bi/OQueResponde';
import { ErroCarga, Vazio } from '../../components/bi/ui';
import { fetchAudiencia } from '../../lib/biApi';

export default function Pagina() {
  return (
    <Suspense fallback={null}>
      <AppShell
        titulo="Site (Analytics)"
        subtitulo="Quem entra no site: de onde vem, em que aparelho, de que cidade e atrás de qual empreendimento"
      >
        <Site />
      </AppShell>
    </Suspense>
  );
}

function Site() {
  const { filtros, chave } = useFiltros();
  const { versao } = useShell();
  const { dados, erro, carregando, recarregar } = useDados(() => fetchAudiencia(filtros), [chave, versao]);

  if (erro && !dados) return <ErroCarga mensagem={erro} onTentar={recarregar} />;
  if (!dados) return <p className="text-xs text-slate-400">Lendo o Google Analytics do período...</p>;

  return (
    <div className={`space-y-5 transition-opacity ${carregando ? 'opacity-60' : ''}`}>
      <OQueResponde
        pergunta={
          <>
            <strong>quem chega ao site, de onde vem e atrás de quê</strong> — sempre comparado com o período anterior de
            mesmo tamanho, para a leitura ser o que mudou, não o número solto.
          </>
        }
        regua={[
          <>
            Os números são do <strong>Google Analytics</strong>, por dia: o período escolhido no filtro vale exatamente, e
            o período anterior é o mesmo número de dias logo antes.
          </>,
          <>
            O empreendimento sai da <strong>página de entrada</strong> (&quot;/empreendimento/reserva-dos-ipes&quot;). Quem entra
            pela home ou pelo blog não diz qual produto procurava: esse tráfego fica separado, não é rateado entre os
            produtos.
          </>,
          <>
            <strong>Conversão</strong> aqui é o evento principal marcado na propriedade (formulário, WhatsApp). Não é o
            lead no CV nem a venda.
          </>,
        ]}
        naoResponde={
          <>
            quantos desses acessos viraram lead e venda: isso depende do cruzamento com o CV. Para leads e custo por lead
            por empreendimento, use
          </>
        }
        outra={{ href: '/empreendimentos', label: 'Empreendimentos' }}
      />

      {dados.totais.sessoes === 0 ? (
        <Vazio
          titulo="Nenhuma sessão do Analytics neste período"
          texto={
            <>
              Ou a base do Google Analytics ainda não foi baixada, ou o período está fora do que foi lido.{' '}
              <Link href="/bases" className="text-sky-300 hover:text-sky-200">
                Baixe a base &quot;Google Analytics — Origem das sessões&quot;
              </Link>
              .
            </>
          }
        />
      ) : (
        <Audiencia dados={dados} />
      )}
    </div>
  );
}
