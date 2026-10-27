'use client';

/**
 * Quadro de slide no modelo do relatório da Qamar: fundo creme, título em caixa alta, faixa colorida no rodapé.
 * 1280×720 fixo, escalado para caber na tela; o PNG sai sem a escala (2560×1440) e cola direto no PowerPoint.
 */

import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Check, Copy, Download, Loader2 } from 'lucide-react';
import { toBlob, toPng } from 'html-to-image';
import { ALTURA, FONTE, LARGURA, OPCOES, QuadroRef, comLimite } from '../apresentacao/Slide';
import { IconeRede } from './icones';

export const Q = {
  verde: '#14503a',
  verde2: '#1f7a3d',
  verdeClaro: '#edf3ec',
  verdeBorda: '#c9d6cb',
  laranja: '#f58a2e',
  laranjaClaro: '#fdebdc',
  creme: '#fbf9f3',
  texto: '#2b3a31',
  mudo: '#6a766e',
  linha: '#d9d6cc',
  bom: '#1f7a3d',
  ruim: '#c0392b',
};

const FAIXA = ['#14503a', '#1f7a3d', '#8fbf9f', '#8aa396', '#f26b5b', '#f7a8a0', '#fbbf8c', '#f58a2e'];

interface Props {
  id: string;
  /** nome que aparece acima do slide, na tela */
  titulo: string;
  /** "01" · "Instagram" */
  numeroSecao?: string;
  secao?: string;
  /** título grande do slide */
  tituloSlide?: string;
  pagina: number;
  /** capa e encerramento: fundo verde */
  capa?: boolean;
  children: React.ReactNode;
}

export const QuadroQamar = forwardRef<QuadroRef, Props>(function QuadroQamar(
  { id, titulo, numeroSecao, secao, tituloSlide, pagina, capa = false, children },
  ref
) {
  const area = useRef<HTMLDivElement>(null);
  const slide = useRef<HTMLDivElement>(null);
  const [escala, setEscala] = useState(0.8);
  const [estado, setEstado] = useState<'parado' | 'gerando' | 'copiado' | 'erro'>('parado');
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const medir = () => area.current && setEscala(area.current.clientWidth / LARGURA);
    medir();
    const obs = new ResizeObserver(medir);
    if (area.current) obs.observe(area.current);
    return () => obs.disconnect();
  }, []);

  const baixar = useCallback(async () => {
    if (!slide.current) return;
    setErro(null);
    setEstado('gerando');
    try {
      const png = await comLimite(toPng(slide.current, OPCOES));
      const a = document.createElement('a');
      a.href = png;
      a.download = `${id}-${new Date().toISOString().slice(0, 10)}.png`;
      a.click();
      setEstado('parado');
    } catch (e: any) {
      setErro(e?.message || 'Não foi possível gerar a imagem.');
      setEstado('erro');
    }
  }, [id]);

  useImperativeHandle(ref, () => ({ baixar }), [baixar]);

  async function copiar() {
    if (!slide.current) return;
    setErro(null);
    setEstado('gerando');
    try {
      const blob = await comLimite(toBlob(slide.current, OPCOES));
      if (!blob) throw new Error('A imagem saiu vazia.');
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
      setEstado('copiado');
      setTimeout(() => setEstado('parado'), 2000);
    } catch (e: any) {
      setErro(e?.message || 'Não foi possível copiar a imagem. Use "Baixar PNG".');
      setEstado('erro');
    }
  }

  const ocupado = estado === 'gerando';
  return (
    <section className="space-y-2" aria-label={titulo}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-100">
          <span className="text-slate-400 font-normal mr-2">{pagina}</span>
          {titulo}
        </h2>
        <div className="flex items-center gap-2">
          {erro && <span className="text-[11px] text-rose-300">{erro}</span>}
          <button onClick={copiar} disabled={ocupado} className="botao-secundario">
            {estado === 'copiado' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {estado === 'copiado' ? 'Copiado' : 'Copiar imagem'}
          </button>
          <button onClick={baixar} disabled={ocupado} className="botao-secundario">
            {ocupado ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            Baixar PNG
          </button>
        </div>
      </div>

      <div
        ref={area}
        className="relative w-full overflow-hidden rounded-xl shadow-lg"
        style={{ height: ALTURA * escala, border: `1px solid ${Q.linha}`, background: capa ? Q.verde : Q.creme }}
      >
        <div
          ref={slide}
          style={{
            width: LARGURA,
            height: ALTURA,
            transform: `scale(${escala})`,
            transformOrigin: 'top left',
            background: capa ? Q.verde : Q.creme,
            color: capa ? '#fff' : Q.texto,
            fontFamily: FONTE,
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
          }}
        >
          {capa ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 90px' }}>{children}</div>
          ) : (
            <>
              <div style={{ position: 'absolute', top: 28, right: 56, width: 560, borderBottom: `2px solid ${Q.verde}`, paddingBottom: 6, display: 'flex', justifyContent: 'flex-end', gap: 14, fontSize: 15, fontWeight: 700, color: Q.verde }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  <IconeRede secao={secao} tam={24} />
                  {secao || ''}
                </span>
                <span style={{ fontWeight: 500, color: Q.mudo }}>{pagina}</span>
              </div>
              <div style={{ padding: '64px 56px 0', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 18 }}>
                  <div style={{ minWidth: 0 }}>
                    {secao && numeroSecao && (
                      <p style={{ margin: 0, fontSize: 14, fontWeight: 800, letterSpacing: 1.4, color: Q.verde2, textTransform: 'uppercase' }}>
                        {numeroSecao} · {secao}
                      </p>
                    )}
                    {tituloSlide && (
                      <h1 style={{ margin: '2px 0 0', fontSize: 40, fontWeight: 900, lineHeight: 1.05, color: Q.verde, textTransform: 'uppercase', letterSpacing: -0.5 }}>{tituloSlide}</h1>
                    )}
                  </div>
                </div>
                <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>{children}</div>
              </div>
            </>
          )}
          <div style={{ display: 'flex', height: 14, marginTop: 'auto', marginLeft: capa ? 108 : 0 }}>
            {FAIXA.map((c) => (
              <div key={c} style={{ flex: 1, background: c }} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
});
