'use client';

/**
 * Quadro de slide: 1280×720 fixo, escalado para caber na tela. O PNG é gerado do quadro sem a escala,
 * então sai sempre do mesmo tamanho (2560×1440) e cola direto no PowerPoint ou no Google Slides.
 * As cores são fixas (não seguem o tema claro/escuro do sistema) para o slide sair igual em qualquer tela.
 */

import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Check, Copy, Download, Loader2 } from 'lucide-react';
import { toBlob, toPng } from 'html-to-image';

export const LARGURA = 1280;
export const ALTURA = 720;

export const COR = {
  verde: '#1a7a10',
  escuro: '#1b4f38',
  claro: '#edf7e9',
  laranja: '#ff7f00',
  laranjaClaro: '#fff3e6',
  texto: '#1f2d24',
  mudo: '#5b6b60',
  linha: '#e3ebe0',
  fundo: '#ffffff',
  bom: '#1a7a10',
  ruim: '#c0392b',
  azul: '#2563a8',
};

export interface QuadroRef {
  baixar: () => Promise<void>;
}

interface Props {
  id: string;
  titulo: string;
  /** o que aparece no cabeçalho do slide */
  tituloSlide: string;
  subtituloSlide?: string;
  periodo: string;
  filtro?: string;
  rodape?: string;
  children: React.ReactNode;
}

// Fonte do sistema e sem embutir fontes da web: buscar as do Google para colocar no PNG dependia da rede e
// travava a geração. Segoe UI/Arial existem em todo computador da empresa, então o PNG sai igual à tela.
export const FONTE = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif";
export const OPCOES = { pixelRatio: 2, width: LARGURA, height: ALTURA, cacheBust: false, includeQueryParams: true, skipFonts: true, style: { transform: 'none' } };
const LIMITE_MS = 45000;

export function comLimite<T>(promessa: Promise<T>): Promise<T> {
  return Promise.race([
    promessa,
    new Promise<T>((_, rejeitar) => setTimeout(() => rejeitar(new Error('A imagem demorou demais para ficar pronta. Tente de novo.')), LIMITE_MS)),
  ]);
}

export const Quadro = forwardRef<QuadroRef, Props>(function Quadro(
  { id, titulo, tituloSlide, subtituloSlide, periodo, filtro, rodape, children },
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
        <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
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
        style={{ height: ALTURA * escala, border: `1px solid ${COR.linha}`, background: COR.fundo }}
      >
        <div
          ref={slide}
          style={{
            width: LARGURA,
            height: ALTURA,
            transform: `scale(${escala})`,
            transformOrigin: 'top left',
            background: COR.fundo,
            color: COR.texto,
            fontFamily: FONTE,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <header
            style={{
              background: COR.escuro,
              color: '#fff',
              padding: '22px 44px 18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 24,
              borderBottom: `5px solid ${COR.laranja}`,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <h1 style={{ fontSize: 32, fontWeight: 700, lineHeight: 1.15, margin: 0 }}>{tituloSlide}</h1>
              {subtituloSlide && <p style={{ fontSize: 16, margin: '5px 0 0', opacity: 0.85 }}>{subtituloSlide}</p>}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <p style={{ fontSize: 17, fontWeight: 600, margin: 0 }}>{periodo}</p>
              {filtro && <p style={{ fontSize: 14, margin: '4px 0 0', color: '#ffd9a8' }}>{filtro}</p>}
            </div>
          </header>

          <div style={{ flex: 1, minHeight: 0, padding: '26px 44px 0', display: 'flex', flexDirection: 'column' }}>{children}</div>

          <footer
            style={{
              padding: '10px 44px 14px',
              fontSize: 12.5,
              color: COR.mudo,
              display: 'flex',
              justifyContent: 'space-between',
              gap: 24,
            }}
          >
            <span>{rodape}</span>
            <span style={{ whiteSpace: 'nowrap', fontWeight: 600, color: COR.escuro }}>Moura Leite · Marketing</span>
          </footer>
        </div>
      </div>
    </section>
  );
});
