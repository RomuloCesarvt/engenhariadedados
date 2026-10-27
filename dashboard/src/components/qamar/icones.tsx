'use client';

/** Ícone de cada seção do relatório da Qamar: selo com a cor da marca e o desenho da rede (SVG embutido, sai igual no PNG). */

import React from 'react';
import { BarChart3, BookOpen, Facebook, Globe, Instagram, Linkedin, ListOrdered, Megaphone, MapPin, Newspaper, PenLine, Youtube } from 'lucide-react';

const TikTok = ({ size }: { size: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="#fff" aria-hidden>
    <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z" />
  </svg>
);

type Definicao = { fundo: string; glifo: (tam: number) => React.ReactNode };

const traco = { color: '#fff', strokeWidth: 2 } as const;

const ICONES: Record<string, Definicao> = {
  Instagram: { fundo: 'linear-gradient(45deg,#f9a03c 0%,#e1306c 50%,#833ab4 100%)', glifo: (t) => <Instagram size={t} {...traco} /> },
  Facebook: { fundo: '#1877f2', glifo: (t) => <Facebook size={t} {...traco} fill="#fff" /> },
  LinkedIn: { fundo: '#0a66c2', glifo: (t) => <Linkedin size={t} {...traco} fill="#fff" /> },
  TikTok: { fundo: '#111111', glifo: (t) => <TikTok size={t} /> },
  YouTube: { fundo: '#ff0000', glifo: (t) => <Youtube size={t} {...traco} /> },
  'Google Meu Negócio': { fundo: '#4285f4', glifo: (t) => <MapPin size={t} {...traco} /> },
  Site: { fundo: '#14503a', glifo: (t) => <Globe size={t} {...traco} /> },
  Blog: { fundo: '#f58a2e', glifo: (t) => <PenLine size={t} {...traco} /> },
  'Assessoria de Imprensa': { fundo: '#6a766e', glifo: (t) => <Newspaper size={t} {...traco} /> },
  'Tráfego pago': { fundo: '#1f7a3d', glifo: (t) => <Megaphone size={t} {...traco} /> },
  Comparativo: { fundo: '#14503a', glifo: (t) => <BarChart3 size={t} {...traco} /> },
  Glossário: { fundo: '#14503a', glifo: (t) => <BookOpen size={t} {...traco} /> },
  Índice: { fundo: '#14503a', glifo: (t) => <ListOrdered size={t} {...traco} /> },
};

export function IconeRede({ secao, tam = 48 }: { secao?: string; tam?: number }) {
  const def = secao ? ICONES[secao] : undefined;
  if (!def) return null;
  return (
    <span
      style={{
        width: tam,
        height: tam,
        borderRadius: Math.round(tam * 0.26),
        background: def.fundo,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      {def.glifo(Math.round(tam * 0.56))}
    </span>
  );
}

/** Fileira de redes da capa. */
export function FileiraDeRedes({ tam = 32 }: { tam?: number }) {
  return (
    <div style={{ display: 'flex', gap: 10, marginTop: 26 }}>
      {['Instagram', 'Facebook', 'LinkedIn', 'TikTok', 'YouTube'].map((r) => (
        <IconeRede key={r} secao={r} tam={tam} />
      ))}
    </div>
  );
}
