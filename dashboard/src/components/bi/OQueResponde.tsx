'use client';

/**
 * O cartão de abertura de uma análise: qual pergunta ela responde, com que régua, e qual é a
 * análise vizinha que responde a outra pergunta.
 *
 * Duas telas olham as mesmas vendas com perguntas diferentes e chegam a números diferentes de
 * propósito. Sem isso escrito na própria tela, os dois números parecem um erro.
 */

import React from 'react';
import Link from 'next/link';
import { ArrowRight, HelpCircle } from 'lucide-react';

export function OQueResponde({
  pergunta,
  regua,
  naoResponde,
  outra,
}: {
  pergunta: React.ReactNode;
  regua: React.ReactNode[];
  naoResponde: React.ReactNode;
  outra?: { href: string; label: string };
}) {
  return (
    <section className="painel p-4 border-l-4 border-l-sky-500/60">
      <div className="flex items-start gap-2">
        <HelpCircle className="w-4 h-4 mt-0.5 shrink-0 text-sky-400" />
        <div className="min-w-0 space-y-2">
          <p className="text-sm text-slate-100 leading-relaxed">
            <span className="font-semibold">O que esta análise responde: </span>
            {pergunta}
          </p>
          <ul className="text-xs text-slate-300 leading-relaxed list-disc pl-4 space-y-0.5">
            {regua.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
          <p className="text-xs text-slate-400 leading-relaxed">
            <span className="font-medium text-slate-300">O que ela não responde: </span>
            {naoResponde}
            {outra && (
              <>
                {' '}
                <Link href={outra.href} className="text-sky-300 hover:text-sky-200 inline-flex items-center gap-0.5">
                  {outra.label} <ArrowRight className="w-3 h-3" />
                </Link>
              </>
            )}
          </p>
        </div>
      </div>
    </section>
  );
}
