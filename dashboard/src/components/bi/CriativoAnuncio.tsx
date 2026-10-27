'use client';

/**
 * Criativo do anúncio como o público viu: pré-visualização oficial da Meta em cada formato
 * (com o vídeo tocando), imagens no tamanho original com o formato de cada peça, vídeos e textos.
 */

import React, { useEffect, useState } from 'react';
import { ExternalLink, Image as ImageIcon, MonitorPlay, Type, Video } from 'lucide-react';
import { fetchCriativo } from '../../lib/biApi';
import { CriativoAnuncio as Criativo } from '../../types/bi';

type Aba = 'previews' | 'imagens' | 'videos' | 'textos';

export function CriativoAnuncio({ anuncioIds }: { anuncioIds: string[] }) {
  const [indice, setIndice] = useState(0);
  const [dados, setDados] = useState<Criativo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aba, setAba] = useState<Aba>('previews');
  const anuncioId = anuncioIds[indice];

  useEffect(() => {
    if (!anuncioId) return;
    let vivo = true;
    setDados(null);
    setErro(null);
    fetchCriativo(anuncioId)
      .then((d) => {
        if (!vivo) return;
        setDados(d);
        setAba(d.previews.length ? 'previews' : d.videos.length ? 'videos' : 'imagens');
      })
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, [anuncioId]);

  if (!anuncioIds.length) {
    return <p className="text-xs text-slate-500">Anúncio sem ID da Meta: não é possível mostrar o criativo.</p>;
  }

  const abas: { id: Aba; label: string; icone: React.ElementType; qtd: number }[] = dados
    ? [
        { id: 'previews', label: 'Como aparece', icone: MonitorPlay, qtd: dados.previews.length },
        { id: 'videos', label: 'Vídeos', icone: Video, qtd: dados.videos.length },
        { id: 'imagens', label: 'Imagens', icone: ImageIcon, qtd: dados.imagens.length },
        { id: 'textos', label: 'Textos', icone: Type, qtd: dados.textos.titulos.length + dados.textos.textos.length },
      ]
    : [];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <p className="text-sm font-semibold text-white mr-2">Criativo</p>
        {abas.map((a) => (
          <button
            key={a.id}
            onClick={() => setAba(a.id)}
            disabled={!a.qtd}
            aria-pressed={aba === a.id}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium disabled:opacity-40 ${
              aba === a.id ? 'bg-sky-600 text-white' : 'bg-slate-800/60 text-slate-300 hover:text-white'
            }`}
          >
            <a.icone className="w-3 h-3" /> {a.label} ({a.qtd})
          </button>
        ))}
        {anuncioIds.length > 1 && (
          <select
            value={indice}
            onChange={(e) => setIndice(Number(e.target.value))}
            className="controle text-[11px] bg-transparent text-slate-200 ml-auto"
            title="O mesmo anúncio foi publicado com mais de um ID"
          >
            {anuncioIds.map((id, i) => (
              <option key={id} value={i} className="bg-slate-900">
                Versão {i + 1} (ID {id})
              </option>
            ))}
          </select>
        )}
      </div>

      {erro && <p className="text-xs text-rose-300">Não foi possível carregar o criativo: {erro}</p>}
      {!dados && !erro && <p className="text-xs text-slate-400">Buscando o criativo na Meta...</p>}
      {dados?.erro && <p className="text-xs text-amber-300">{dados.erro}</p>}

      {dados && !dados.erro && aba === 'previews' && (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {dados.previews.map((p) => (
            <figure key={p.formato} className="shrink-0">
              <figcaption className="text-[11px] text-slate-400 mb-1">{p.rotulo}</figcaption>
              <iframe
                src={p.src}
                title={`${dados.nome ?? 'Anúncio'} — ${p.rotulo}`}
                width={p.largura ?? 320}
                height={p.altura ?? 560}
                loading="lazy"
                className="rounded-lg bg-white border border-slate-700"
                allow="autoplay; encrypted-media; picture-in-picture"
              />
            </figure>
          ))}
        </div>
      )}

      {dados && !dados.erro && aba === 'videos' && (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {dados.videos.map((v) => {
            const vertical = (v.altura ?? 0) > (v.largura ?? 0);
            const largura = vertical ? 270 : 400;
            const altura = v.largura && v.altura ? Math.round((largura * v.altura) / v.largura) : vertical ? 480 : 400;
            return (
              <figure key={v.video_id} className="shrink-0">
                <figcaption className="text-[11px] text-slate-400 mb-1">
                  {v.formato} · {v.duracao_s}s{v.onde ? ` · ${v.onde}` : ''}
                </figcaption>
                {v.player ? (
                  <iframe
                    src={v.player}
                    title={`Vídeo ${v.video_id}`}
                    width={largura}
                    height={altura}
                    loading="lazy"
                    className="rounded-lg bg-black border border-slate-700"
                    allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share"
                    allowFullScreen
                  />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  v.capa && <img src={v.capa} alt="" width={largura} className="rounded-lg" referrerPolicy="no-referrer" />
                )}
                {v.link && (
                  <a href={v.link} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-[11px] text-sky-300 hover:text-sky-200">
                    Abrir o vídeo na Meta <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </figure>
            );
          })}
        </div>
      )}

      {dados && !dados.erro && aba === 'imagens' && (
        <div className="flex gap-4 overflow-x-auto pb-2 items-start">
          {dados.imagens.map((img) => (
            <figure key={img.url} className="shrink-0 max-w-[260px]">
              <a href={img.url} target="_blank" rel="noopener noreferrer" title="Abrir no tamanho original">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={img.url}
                  alt={img.formato}
                  referrerPolicy="no-referrer"
                  className="rounded-lg border border-slate-700 object-contain bg-slate-950"
                  style={{ width: 220, height: img.largura && img.altura ? Math.min(400, Math.round((220 * img.altura) / img.largura)) : 220 }}
                />
              </a>
              <figcaption className="text-[11px] text-slate-300 mt-1">
                {img.formato}
                {img.largura && img.altura ? <span className="text-slate-500"> · {img.largura}×{img.altura}</span> : null}
                {img.onde && <span className="block text-[10px] text-slate-500">{img.onde}</span>}
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      {dados && !dados.erro && aba === 'textos' && (
        <div className="grid md:grid-cols-2 gap-3 text-xs">
          {(['titulos', 'textos', 'descricoes'] as const).map((k) =>
            dados.textos[k].length ? (
              <div key={k}>
                <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">{k === 'titulos' ? 'Títulos' : k === 'textos' ? 'Textos' : 'Descrições'}</p>
                <ul className="space-y-1.5">
                  {dados.textos[k].map((t) => (
                    <li key={t} className="rounded-md bg-slate-800/50 px-2 py-1.5 text-slate-200 whitespace-pre-line">
                      {t}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null
          )}
        </div>
      )}

      {dados && !dados.erro && dados.links.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {dados.links.map((l) => (
            <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="botao-secundario !py-1 !px-2 text-[11px] inline-flex items-center gap-1">
              {l.label} <ExternalLink className="w-3 h-3" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
