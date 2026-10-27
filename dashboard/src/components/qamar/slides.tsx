'use client';

/** Conteúdo dos slides do relatório da Qamar. Cada slide recebe só o pedaço do relatório que ele mostra. */

import React from 'react';
import { numero, reaisCentavos } from '../../lib/format';
import { urlImagemAnuncio } from '../../lib/biApi';
import {
  AnuncioPago,
  BlocoBase,
  LinhaMetrica,
  PostBlog,
  PublicacaoDestaque,
  QamarFacebook,
  QamarImprensa,
  QamarInstagram,
  QamarRelatorio,
  QamarSite,
  QamarYoutube,
} from '../../types/qamar';
import { Q } from './QuadroQamar';
import { FileiraDeRedes } from './icones';

/* ---------------------------------------------------------------------------------------------- formatação */

const MENOS = '−';
const dec = (n: number, casas = 1) => n.toFixed(casas).replace('.', ',');

export function compactoQ(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  if (Math.abs(n) >= 1_000_000) return `${dec(n / 1_000_000)} mi`;
  if (Math.abs(n) >= 10_000) return `${dec(n / 1_000)} mil`;
  return numero(n);
}

function valorLinha(l: LinhaMetrica, v: number | null): string {
  if (v === null || v === undefined) return '—';
  if (l.fmt === 'pct') return `${dec(v, 2)}%`;
  if (l.fmt === 'reais') return `R$ ${numero(Math.round(v))}`;
  if (l.fmt === 'sinal') return `${v > 0 ? '+' : v < 0 ? MENOS : ''}${numero(Math.abs(v))}`;
  return numero(v);
}

function variacaoLinha(l: LinhaMetrica): string {
  if (l.fmt === 'pct' && l.delta_pp !== null && l.delta_pp !== undefined) return `${l.delta_pp >= 0 ? '+' : MENOS}${dec(Math.abs(l.delta_pp), 2)} p.p.`;
  if (l.variacao === null || l.variacao === undefined) return '—';
  return `${l.variacao >= 0 ? '+' : MENOS}${dec(Math.abs(l.variacao))}%`;
}

const variacaoSimples = (atual: number | null | undefined, antes: number | null | undefined) =>
  atual === null || atual === undefined || !antes ? '—' : `${atual >= antes ? '+' : MENOS}${dec(Math.abs(((atual - antes) / antes) * 100))}%`;


type Rot = { atual: string; antes: string | null };

/** Cabeçalho de tabela: só o mês, ou antes · atual · variação quando a comparação está ligada. */
function cab(r: Rot, primeiro: string, curto = false): string[] {
  const c = (t: string) => (curto ? t.slice(0, 3) : t);
  return r.antes ? [primeiro, c(r.antes), c(r.atual), 'Variação'] : [primeiro, c(r.atual)];
}
function cabPar(r: Rot, primeiro: string, curto = false): string[] {
  const c = (t: string) => (curto ? t.slice(0, 3) : t);
  return r.antes ? [primeiro, c(r.antes), c(r.atual)] : [primeiro, c(r.atual)];
}
const linhaMetrica = (l: LinhaMetrica, r: Rot): React.ReactNode[] =>
  r.antes ? [l.metrica, valorLinha(l, l.antes), valorLinha(l, l.atual), variacaoLinha(l)] : [l.metrica, valorLinha(l, l.atual)];
const nQ = (v: number | null | undefined) => (v === null || v === undefined ? '—' : numero(v));
const linhaPar = (nome: string, par: [number | null, number], r: Rot, f: (v: number | null) => string = nQ): React.ReactNode[] =>
  r.antes ? [nome, f(par[0]), f(par[1])] : [nome, f(par[1])];

const dm = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

/* ---------------------------------------------------------------------------------------------- blocos visuais */

export function Tabela({ colunas, linhas, larguras, fonte = 17, compacta = false }: { colunas: string[]; linhas: React.ReactNode[][]; larguras?: string[]; fonte?: number; compacta?: boolean }) {
  const pad = compacta ? '6px 10px' : '9px 12px';
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: fonte, tableLayout: 'fixed' }}>
      {larguras && (
        <colgroup>
          {larguras.map((w, i) => (
            <col key={i} style={{ width: w }} />
          ))}
        </colgroup>
      )}
      <thead>
        <tr>
          {colunas.map((c, i) => (
            <th key={i} style={{ background: Q.verde, color: '#fff', textAlign: i === 0 ? 'left' : 'right', padding: pad, fontWeight: 700, border: `1px solid ${Q.verde}` }}>
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((l, r) => (
          <tr key={r}>
            {l.map((c, i) => (
              <td key={i} style={{ textAlign: i === 0 ? 'left' : 'right', padding: pad, border: `1px solid ${Q.linha}`, color: i === 0 ? Q.verde2 : Q.texto, background: '#fff', verticalAlign: 'top' }}>
                {c}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Cartao({ children, tom = 'verde', estilo }: { children: React.ReactNode; tom?: 'verde' | 'laranja'; estilo?: React.CSSProperties }) {
  return (
    <div style={{ background: tom === 'verde' ? Q.verdeClaro : Q.laranjaClaro, borderRadius: 18, padding: '20px 24px', ...estilo }}>{children}</div>
  );
}

const Mini = ({ children }: { children: React.ReactNode }) => (
  <p style={{ margin: 0, fontSize: 13.5, fontWeight: 800, letterSpacing: 1, color: Q.verde2, textTransform: 'uppercase' }}>{children}</p>
);

const Grande = ({ children, tam = 56 }: { children: React.ReactNode; tam?: number }) => (
  <p style={{ margin: '4px 0', fontSize: tam, fontWeight: 900, color: Q.verde, lineHeight: 1 }}>{children}</p>
);

const Nota = ({ children }: { children: React.ReactNode }) => <p style={{ margin: '14px 0 0', fontSize: 13.5, color: Q.mudo }}>{children}</p>;

function Imagem({ url, w, h, raio = 10 }: { url?: string | null; w: number | string; h: number | string; raio?: number }) {
  if (!url) return <div style={{ width: w, height: h, background: '#e7e4da', borderRadius: raio }} />;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url.startsWith('/') ? url : urlImagemAnuncio(url)} alt="" style={{ width: w, height: h, objectFit: 'cover', borderRadius: raio, display: 'block' }} />;
}

/* ---------------------------------------------------------------------------------------------- capa, índice, glossário */

export function Capa({ rotulo }: { rotulo: string }) {
  return (
    <>
      <p style={{ margin: 0, fontSize: 18, fontWeight: 800, letterSpacing: 2.2, color: '#f2b27a' }}>RELATÓRIO DE RESULTADOS</p>
      <h1 style={{ margin: '14px 0 18px', fontSize: 84, fontWeight: 900, lineHeight: 1.02 }}>{rotulo}</h1>
      <p style={{ margin: 0, fontSize: 21, maxWidth: 620, opacity: 0.88, lineHeight: 1.4 }}>
        Redes sociais, Google Meu Negócio, site, blog, assessoria de imprensa e tráfego pago
      </p>
      <FileiraDeRedes />
      <p style={{ margin: '56px 0 0', fontSize: 26, fontWeight: 900, letterSpacing: 1 }}>
        MOURA LEITE <span style={{ fontWeight: 400, letterSpacing: 6, fontSize: 17, marginLeft: 8 }}>LOTEAMENTOS</span>
      </p>
    </>
  );
}

export function Indice({ itens }: { itens: { numero: string; nome: string; pagina: number }[] }) {
  const meio = Math.ceil(itens.length / 2);
  const coluna = (lista: typeof itens) => (
    <div style={{ flex: 1 }}>
      {lista.map((i) => (
        <div key={i.numero} style={{ display: 'flex', alignItems: 'baseline', gap: 16, padding: '13px 0', borderBottom: `1px solid ${Q.linha}` }}>
          <span style={{ color: Q.laranja, fontWeight: 900, fontSize: 22, width: 34 }}>{i.numero}</span>
          <span style={{ flex: 1, color: Q.verde, fontWeight: 700, fontSize: 20, alignSelf: 'center' }}>{i.nome}</span>
          <span style={{ color: Q.mudo, fontSize: 18 }}>{i.pagina}</span>
        </div>
      ))}
    </div>
  );
  return (
    <div style={{ display: 'flex', gap: 56, marginTop: 6 }}>
      {coluna(itens.slice(0, meio))}
      {coluna(itens.slice(meio))}
    </div>
  );
}

const GLOSSARIO: [string, string][] = [
  ['Alcance', 'Número de pessoas diferentes que viram o conteúdo ou o anúncio.'],
  ['Impressões', 'Total de vezes que o anúncio apareceu, contando repetições.'],
  ['Frequência', 'Quantas vezes, em média, cada pessoa viu o anúncio (impressões ÷ alcance).'],
  ['CPM', 'Custo por mil impressões: quanto custa o anúncio aparecer mil vezes.'],
  ['Interações', 'Curtidas, comentários, compartilhamentos, salvamentos e cliques.'],
  ['Custo por interação', 'Quanto custou, em média, cada interação.'],
  ['ThruPlay', 'Vídeo assistido até o fim ou por pelo menos 15 segundos.'],
  ['Visualização da página de destino', 'Quando a pessoa clica no anúncio e a página do site carrega.'],
  ['Taxa de engajamento', 'Interações ÷ alcance (no LinkedIn, ÷ impressões).'],
  ['Alcance acumulado', 'Soma do alcance de cada dia; a mesma pessoa pode contar mais de uma vez.'],
];

export function Glossario() {
  const meio = Math.ceil(GLOSSARIO.length / 2);
  const col = (l: [string, string][]) => (
    <div style={{ flex: 1 }}>
      {l.map(([t, d]) => (
        <div key={t} style={{ padding: '9px 0', borderBottom: `1px solid ${Q.linha}` }}>
          <p style={{ margin: 0, fontWeight: 800, color: Q.verde, fontSize: 17 }}>{t}</p>
          <p style={{ margin: '2px 0 0', fontSize: 14.5, color: Q.texto }}>{d}</p>
        </div>
      ))}
    </div>
  );
  return (
    <div style={{ display: 'flex', gap: 44 }}>
      {col(GLOSSARIO.slice(0, meio))}
      {col(GLOSSARIO.slice(meio))}
    </div>
  );
}

export function Encerramento() {
  return (
    <div style={{ textAlign: 'center' }}>
      <p style={{ margin: 0, fontSize: 30, fontWeight: 900, letterSpacing: 1 }}>
        MOURA LEITE <span style={{ fontWeight: 400, letterSpacing: 6, fontSize: 18, marginLeft: 8 }}>LOTEAMENTOS</span>
      </p>
      <p style={{ margin: '34px 0 0', fontSize: 52, fontWeight: 900 }}>Obrigada!</p>
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- fonte ainda sem conexão */

export function AConectar({ bloco, rede }: { bloco: BlocoBase; rede: string }) {
  return (
    <div style={{ display: 'flex', gap: 28, flex: 1 }}>
      <Cartao tom="laranja" estilo={{ flex: 1.15 }}>
        <Mini>Fonte ainda não conectada</Mini>
        <p style={{ margin: '8px 0 14px', fontSize: 22, fontWeight: 800, color: Q.verde, lineHeight: 1.25 }}>{bloco.mensagem}</p>
        <Mini>Como conectar</Mini>
        <ol style={{ margin: '8px 0 0', paddingLeft: 22, fontSize: 16, lineHeight: 1.45, color: Q.texto }}>
          {(bloco.passos || []).map((p, i) => (
            <li key={i} style={{ marginBottom: 6 }}>
              {p}
            </li>
          ))}
        </ol>
      </Cartao>
      <div style={{ flex: 0.85, display: 'flex', flexDirection: 'column', gap: 18 }}>
        {bloco.seguidores_hoje != null && (
          <Cartao tom="verde" estilo={{ padding: '16px 24px' }}>
            <Mini>Seguidores hoje</Mini>
            <Grande tam={48}>{numero(bloco.seguidores_hoje)}</Grande>
            <p style={{ margin: 0, fontSize: 13, color: Q.mudo }}>Número que a página pública mostra. O desempenho do mês só vem com a conexão.</p>
          </Cartao>
        )}
        <Cartao estilo={{ flex: 1 }}>
          <Mini>O que o relatório de {rede} terá</Mini>
          <ul style={{ margin: '10px 0 0', paddingLeft: 20, fontSize: 17, lineHeight: 1.6, color: Q.texto }}>
            {(bloco.campos || ['visão geral', 'conteúdos', 'público']).map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </Cartao>
      </div>
    </div>
  );
}

export function YtVisao({ yt, rotulos }: { yt: QamarYoutube; rotulos: Rot }) {
  const soma = yt.videos.reduce((t, v) => t + (v.visualizacoes || 0), 0);
  const ultimo = yt.ultimo_video ? `${yt.ultimo_video.slice(8, 10)}/${yt.ultimo_video.slice(5, 7)}/${yt.ultimo_video.slice(0, 4)}` : null;
  const lido = yt.mais_antigo_lido ? `${yt.mais_antigo_lido.slice(8, 10)}/${yt.mais_antigo_lido.slice(5, 7)}/${yt.mais_antigo_lido.slice(0, 4)}` : null;
  return (
    <div style={{ display: 'flex', gap: 28, flex: 1 }}>
      <div style={{ flex: 1.4, minWidth: 0 }}>
        {yt.videos.length ? (
          <Tabela
            colunas={['Vídeo', 'Data', 'Visualiz.', 'Curtidas']}
            larguras={['56%', '14%', '15%', '15%']}
            linhas={yt.videos.map((v) => [
              <span key={v.id ?? v.titulo} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Imagem url={v.miniatura} w={64} h={36} raio={5} />
                <span>{v.titulo}</span>
              </span>,
              dm(v.dia),
              nQ(v.visualizacoes),
              nQ(v.curtidas),
            ])}
            compacta
            fonte={15}
          />
        ) : (
          <Cartao tom="laranja" estilo={{ padding: '26px 30px' }}>
            <p style={{ margin: 0, fontSize: 26, fontWeight: 900, color: Q.verde, lineHeight: 1.2 }}>Nenhum vídeo encontrado em {rotulos.atual.toLowerCase()}.</p>
            {yt.cobre_o_mes === false && lido && (
              <p style={{ margin: '12px 0 0', fontSize: 16, color: Q.texto }}>O YouTube só entrega os 15 vídeos mais recentes, e o mais antigo que o sistema já leu é de {lido}. Meses anteriores a essa data não têm como ser lidos.</p>
            )}
            {ultimo && <p style={{ margin: '12px 0 0', fontSize: 17, color: Q.texto }}>O último vídeo do canal foi publicado em {ultimo}.</p>}
          </Cartao>
        )}
        {yt.cobre_o_mes === false && yt.videos.length > 0 && lido && (
          <Cartao tom="laranja" estilo={{ marginTop: 12, padding: '10px 16px' }}>
            <p style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: Q.verde, lineHeight: 1.35 }}>
              Lista possivelmente incompleta: o YouTube só entrega os 15 vídeos mais recentes, e o mais antigo que o sistema leu é de {lido}.
            </p>
          </Cartao>
        )}
        <Nota>{yt.mensagem}</Nota>
      </div>
      <Cartao estilo={{ flex: 0.6, alignSelf: 'flex-start' }}>
        <Mini>Canal @mouraleiteloteamentos</Mini>
        <Grande tam={52}>{yt.inscritos ? yt.inscritos.replace(' inscritos', '') : '—'}</Grande>
        <p style={{ margin: '0 0 14px', fontSize: 15, color: Q.mudo }}>inscritos hoje</p>
        <p style={{ margin: 0, fontSize: 17, fontWeight: 800, color: Q.verde }}>{yt.videos.length} vídeo(s) no mês</p>
        <p style={{ margin: '4px 0 0', fontSize: 15, color: Q.texto }}>{numero(soma)} visualizações somadas</p>
      </Cartao>
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- Instagram */

function leituraInstagram(v: LinhaMetrica[], rotulos: Rot): string {
  const alcance = v.find((l) => l.metrica.startsWith('Alcance'));
  const inter = v.find((l) => l.metrica === 'Interações');
  if (alcance?.variacao != null && inter?.variacao != null) {
    if (alcance.variacao < 0 && inter.variacao > 0) return `Menos pessoas alcançadas, mais interação: quem viu o conteúdo de ${rotulos.atual.toLowerCase()} interagiu mais.`;
    if (alcance.variacao > 0 && inter.variacao > 0) return `Mais pessoas alcançadas e mais interação em ${rotulos.atual.toLowerCase()}.`;
    if (alcance.variacao < 0 && inter.variacao < 0) return `Alcance e interações caíram em ${rotulos.atual.toLowerCase()} frente a ${(rotulos.antes || '').toLowerCase()}.`;
  }
  return `${rotulos.atual} comparado a ${(rotulos.antes || '').toLowerCase()}.`;
}

function leituraMes(v: LinhaMetrica[], r: Rot): string {
  const inter = v.find((l) => l.metrica === 'Interações')?.atual;
  const views = v.find((l) => l.metrica === 'Visualizações')?.atual;
  return `Em ${r.atual.toLowerCase()}: ${numero(inter ?? 0)} interações e ${numero(views ?? 0)} visualizações no perfil.`;
}

export function IgVisao({ ig, rotulos }: { ig: QamarInstagram; rotulos: Rot }) {
  const taxa = ig.visao_geral.find((l) => l.metrica === 'Taxa de engajamento');
  const cmp = !!rotulos.antes;
  return (
    <div style={{ display: 'flex', gap: 28, flex: 1 }}>
      <div style={{ flex: 1.25 }}>
        <Tabela
          colunas={cab(rotulos, 'Métrica')}
          larguras={cmp ? ['34%', '22%', '22%', '22%'] : ['64%', '36%']}
          linhas={ig.visao_geral.map((l) => linhaMetrica(l, rotulos))}
          compacta
          fonte={16.5}
        />
        {ig.seguidores_obs && <Nota>Seguidores líquidos: {ig.seguidores_obs}</Nota>}
      </div>
      <Cartao estilo={{ flex: 0.75, alignSelf: 'flex-start' }}>
        <p style={{ margin: 0, fontSize: 16, color: Q.mudo }}>Taxa de engajamento em {rotulos.atual.toLowerCase()}</p>
        <Grande tam={72}>{valorLinha(taxa || ({ fmt: 'pct' } as LinhaMetrica), taxa?.atual ?? null)}</Grande>
        <p style={{ margin: '4px 0 12px', fontSize: 15, color: Q.mudo }}>
          {cmp && taxa?.delta_pp != null
            ? `${taxa.delta_pp >= 0 ? '+' : MENOS}${dec(Math.abs(taxa.delta_pp), 2)} ponto percentual sobre ${rotulos.antes!.toLowerCase()} (${valorLinha(taxa, taxa.antes)}).`
            : 'Interações ÷ alcance no mês.'}
        </p>
        <p style={{ margin: 0, fontSize: 17, fontWeight: 800, color: Q.verde, lineHeight: 1.35 }}>
          {cmp ? leituraInstagram(ig.visao_geral, rotulos as { atual: string; antes: string }) : leituraMes(ig.visao_geral, rotulos)}
        </p>
      </Cartao>
    </div>
  );
}

export function IgInteracoes({ ig, rotulos }: { ig: QamarInstagram; rotulos: Rot }) {
  const cmp = !!rotulos.antes;
  const compacto = (v: number | null) => (v === null || v === undefined ? '—' : compactoQ(v));
  const semStories = cmp ? ['Stories', '—', '—'] : ['Stories', '—'];
  const stories = ig.stories.atual.cobre_o_mes_inteiro;
  return (
    <div style={{ display: 'flex', gap: 32, flex: 1 }}>
      <div style={{ flex: 1 }}>
        <p style={{ margin: '0 0 8px', fontWeight: 800, color: Q.verde, fontSize: 18 }}>Tipos de interação</p>
        <Tabela
          colunas={cab(rotulos, 'Interação', true)}
          larguras={cmp ? ['40%', '20%', '20%', '20%'] : ['62%', '38%']}
          linhas={ig.tipos_de_interacao.map((l) => linhaMetrica(l, rotulos))}
          compacta
          fonte={16}
        />
        <Nota>Interações somadas pela API do Instagram; a ferramenta de gestão da agência pode contar de outro jeito.</Nota>
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ margin: '0 0 8px', fontWeight: 800, color: Q.verde, fontSize: 18 }}>Publicações</p>
        <Tabela
          colunas={cabPar(rotulos, 'Formato', true)}
          larguras={cmp ? ['44%', '28%', '28%'] : ['62%', '38%']}
          linhas={[linhaPar('Posts', ig.publicacoes.posts, rotulos), linhaPar('Reels', ig.publicacoes.reels, rotulos), stories ? linhaPar('Stories', ig.publicacoes.stories, rotulos) : semStories]}
          compacta
          fonte={16}
        />
        <p style={{ margin: '18px 0 8px', fontWeight: 800, color: Q.verde, fontSize: 18 }}>Visualizações por formato</p>
        <Tabela
          colunas={cabPar(rotulos, 'Formato', true)}
          larguras={cmp ? ['44%', '28%', '28%'] : ['62%', '38%']}
          linhas={[
            linhaPar('Posts', ig.alcance_por_formato.posts, rotulos, compacto),
            linhaPar('Reels', ig.alcance_por_formato.reels, rotulos, compacto),
            linhaPar('Stories', ig.alcance_por_formato.stories, rotulos, compacto),
          ]}
          compacta
          fonte={16}
        />
      </div>
    </div>
  );
}

export function IgConteudo({ ig, rotulos }: { ig: QamarInstagram; rotulos: Rot }) {
  const { antes, atual } = ig.conteudo;
  const cmp = !!rotulos.antes && !!antes;
  const n = (v: number | null | undefined, casas = 0) => (v === null || v === undefined ? '—' : casas ? dec(v, casas) : numero(v));
  const pc = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${dec(v, 2)}%`);
  const lin = (nome: string, a: string, b: string) => (cmp ? [nome, a, b] : [nome, b]);
  const sufixoPosts = cmp ? ` · interações ${variacaoSimples(atual.posts.interacoes, antes!.posts.interacoes)}` : '';
  const sufixoReels = cmp ? ` · visualizações ${variacaoSimples(atual.reels.visualizacoes, antes!.reels.visualizacoes)}` : '';
  const larg = cmp ? ['52%', '24%', '24%'] : ['64%', '36%'];
  return (
    <div style={{ display: 'flex', gap: 28, flex: 1 }}>
      <div style={{ flex: 1 }}>
        <p style={{ margin: '0 0 8px', fontWeight: 800, color: Q.verde, fontSize: 18 }}>Posts do feed{sufixoPosts}</p>
        <Tabela
          colunas={cabPar(rotulos, 'Posts', true)}
          larguras={larg}
          linhas={[
            lin('Quantidade', n(antes?.posts.quantidade), n(atual.posts.quantidade)),
            lin('Interações', n(antes?.posts.interacoes), n(atual.posts.interacoes)),
            lin('Média de interações por post', n(antes?.posts.media_interacoes, 1), n(atual.posts.media_interacoes, 1)),
            lin('Média de visualizações por post', n(antes?.posts.media_visualizacoes), n(atual.posts.media_visualizacoes)),
            lin('Engajamento médio por post', pc(antes?.posts.engajamento_medio), pc(atual.posts.engajamento_medio)),
            lin('Comentários', n(antes?.posts.comentarios), n(atual.posts.comentarios)),
          ]}
          compacta
          fonte={15.5}
        />
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ margin: '0 0 8px', fontWeight: 800, color: Q.verde, fontSize: 18 }}>Reels{sufixoReels}</p>
        <Tabela
          colunas={cabPar(rotulos, 'Reels', true)}
          larguras={larg}
          linhas={[
            lin('Quantidade', n(antes?.reels.quantidade), n(atual.reels.quantidade)),
            lin('Visualizações', n(antes?.reels.visualizacoes), n(atual.reels.visualizacoes)),
            lin('Média de visualizações por reel', n(antes?.reels.media_visualizacoes), n(atual.reels.media_visualizacoes)),
            lin('Interações', n(antes?.reels.interacoes), n(atual.reels.interacoes)),
          ]}
          compacta
          fonte={15.5}
        />
        <Cartao tom="laranja" estilo={{ marginTop: 18, padding: '14px 18px' }}>
          <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: Q.verde, lineHeight: 1.35 }}>
            {cmp
              ? `Com ${atual.posts.quantidade} post(s) no feed e ${atual.reels.quantidade} reel(s), as interações dos posts foram de ${n(antes!.posts.interacoes)} para ${n(atual.posts.interacoes)} e os comentários, de ${n(antes!.posts.comentarios)} para ${n(atual.posts.comentarios)}.`
              : `${atual.posts.quantidade} post(s) no feed somaram ${n(atual.posts.interacoes)} interações e ${n(atual.posts.comentarios)} comentários; ${atual.reels.quantidade} reel(s) somaram ${n(atual.reels.visualizacoes)} visualizações.`}
          </p>
        </Cartao>
        <Nota>Apenas conteúdos publicados no mês. Fonte: Instagram (API).</Nota>
      </div>
    </div>
  );
}

export function IgConteudos({ itens }: { itens: PublicacaoDestaque[] }) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        {itens.map((p, i) => (
          <Cartao key={p.dia + p.titulo + i} tom={i % 2 ? 'laranja' : 'verde'} estilo={{ padding: '10px 10px 12px', minWidth: 0 }}>
            <Imagem url={p.miniatura} w="100%" h={150} raio={8} />
            <p style={{ margin: '8px 0 2px', fontSize: 12.5, fontWeight: 800, letterSpacing: 0.6, color: Q.verde2, textTransform: 'uppercase' }}>
              {p.tipo === 'reel' ? 'Reel' : 'Post'} · {dm(p.dia)}
            </p>
            <p style={{ margin: 0, fontSize: 14.5, fontWeight: 800, color: Q.verde, lineHeight: 1.2, height: 35, overflow: 'hidden' }}>{p.titulo}</p>
            <p style={{ margin: '6px 0 0', fontSize: 13, color: Q.texto }}>
              {p.visualizacoes != null ? `${numero(p.visualizacoes)} visualizações · ` : ''}
              {numero(p.interacoes)} interações
            </p>
          </Cartao>
        ))}
      </div>
      <Nota>Fonte: Instagram (API). Foto e legenda de cada conteúdo publicado no mês.</Nota>
    </>
  );
}

export function IgStories({ ig }: { ig: QamarInstagram }) {
  const s = ig.stories;
  const c = s.conta;
  const guardados = s.atual.coletados;
  const desde = s.atual.inicio_da_coleta ? `${dm(s.atual.inicio_da_coleta)}/${s.atual.inicio_da_coleta.slice(0, 4)}` : null;
  const cartoes: [string, string, string][] = [
    [nQ(c.visualizacoes), 'visualizações', 'dos stories no mês'],
    [nQ(c.alcance), 'contas alcançadas', 'pelos stories no mês'],
    [nQ(c.interacoes), 'interações', `${nQ(c.curtidas)} curtidas · ${nQ(c.compartilhamentos)} compartilhamentos`],
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
      <div style={{ display: 'flex', gap: 18 }}>
        {cartoes.map(([g, t, sub]) => (
          <Cartao key={t} estilo={{ flex: 1, padding: '14px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <span style={{ fontSize: 44, fontWeight: 900, color: Q.verde }}>{g}</span>
              <span style={{ fontSize: 16, fontWeight: 700, color: Q.texto }}>{t}</span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: Q.mudo }}>{sub}</p>
          </Cartao>
        ))}
      </div>
      {!s.atual.cobre_o_mes_inteiro && (
        <Cartao tom="laranja" estilo={{ padding: '12px 18px' }}>
          <p style={{ margin: 0, fontSize: 15.5, fontWeight: 700, color: Q.verde, lineHeight: 1.35 }}>
            Os totais do mês vêm direto da conta do Instagram. A contagem de stories e a lista dos de maior alcance só existem a partir de {desde || 'hoje'}, porque o Instagram só mostra cada story por 24 horas
            {guardados ? ` (${guardados} guardados até agora)` : ''}.
          </p>
        </Cartao>
      )}
      {s.melhores.length > 0 && (
        <>
          <p style={{ margin: '4px 0 0', fontWeight: 800, color: Q.verde, fontSize: 17 }}>Os stories de maior alcance</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
            {s.melhores.map((st, i) => (
              <Cartao key={st.id} tom={i % 2 ? 'laranja' : 'verde'} estilo={{ display: 'flex', gap: 14, alignItems: 'center', padding: '10px 14px' }}>
                <Imagem url={st.miniatura} w={50} h={72} raio={8} />
                <div>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 800, color: Q.verde2 }}>{dm(st.dia)}</p>
                  <p style={{ margin: 0, fontSize: 30, fontWeight: 900, color: Q.verde, lineHeight: 1 }}>{numero(st.alcance)}</p>
                  <p style={{ margin: 0, fontSize: 12.5, color: Q.mudo }}>contas alcançadas · {numero(st.visualizacoes)} visualizações · {numero(st.interacoes)} interações</p>
                </div>
              </Cartao>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function CartaoPublicacao({ p, tom }: { p: PublicacaoDestaque; tom: 'verde' | 'laranja' }) {
  return (
    <Cartao tom={tom} estilo={{ flex: 1, minWidth: 0, padding: '14px 16px' }}>
      <Imagem url={p.miniatura} w="100%" h={130} raio={8} />
      <div style={{ height: 8 }} />
      <Mini>
        {p.tipo === 'reel' ? 'Reel' : 'Post'} · {dm(p.dia)}
      </Mini>
      <p style={{ margin: '4px 0 6px', fontSize: 16.5, fontWeight: 800, color: Q.verde, lineHeight: 1.2, height: 60, overflow: 'hidden' }}>{p.titulo}</p>
      {p.visualizacoes != null && (
        <>
          <Grande tam={34}>{numero(p.visualizacoes)}</Grande>
          <p style={{ margin: '0 0 4px', fontSize: 13, color: Q.mudo }}>visualizações</p>
        </>
      )}
      <Grande tam={34}>{numero(p.interacoes)}</Grande>
      <p style={{ margin: 0, fontSize: 13, color: Q.mudo }}>interações</p>
      {p.comentarios != null && <p style={{ margin: '6px 0 0', fontSize: 14, fontWeight: 700, color: Q.verde }}>{numero(p.comentarios)} comentários</p>}
    </Cartao>
  );
}

export function IgDestaques({ ig, rotulos }: { ig: QamarInstagram; rotulos: Rot }) {
  return (
    <>
      <div style={{ display: 'flex', gap: 18 }}>
        {ig.destaques.slice(0, 4).map((p, i) => (
          <div key={p.rotulo + p.dia} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 800, color: Q.laranja, textTransform: 'uppercase', letterSpacing: 0.6 }}>{p.rotulo}</p>
            <CartaoPublicacao p={p} tom={i % 2 ? 'verde' : 'laranja'} />
          </div>
        ))}
      </div>
      <Nota>Números acumulados até a consulta. Fonte: Instagram (API). Mês de referência: {rotulos.atual}.</Nota>
    </>
  );
}

export function IgMaisComentados({ itens }: { itens: PublicacaoDestaque[] }) {
  return (
    <>
      <div style={{ display: 'flex', gap: 24, flex: 1 }}>
        {itens.map((p, i) => (
          <Cartao key={p.dia + p.titulo} tom={i % 2 ? 'verde' : 'laranja'} estilo={{ flex: 1, minWidth: 0, display: 'flex', gap: 18, alignItems: 'flex-start' }}>
            <Imagem url={p.miniatura} w={190} h={250} />
            <div style={{ minWidth: 0 }}>
              <Mini>
                {p.tipo === 'reel' ? 'Reel' : 'Post'} · {dm(p.dia)}
              </Mini>
              <p style={{ margin: '6px 0 12px', fontSize: 19, fontWeight: 800, color: Q.verde, lineHeight: 1.2 }}>{p.titulo}</p>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ fontSize: 46, fontWeight: 900, color: Q.verde }}>{numero(p.comentarios)}</span>
                <span style={{ fontSize: 15, color: Q.mudo }}>comentários</span>
              </div>
              <p style={{ margin: '4px 0 0', fontSize: 15, color: Q.texto }}>
                {numero(p.interacoes)} interações{p.visualizacoes != null ? ` · ${numero(p.visualizacoes)} visualizações` : ''}
              </p>
            </div>
          </Cartao>
        ))}
      </div>
      <Nota>Fonte: Instagram (API).</Nota>
    </>
  );
}

function Barras({ titulo, itens, destaque }: { titulo: string; itens: { rotulo: string; pct: number }[]; destaque?: boolean }) {
  return (
    <Cartao estilo={{ flex: 1, padding: '20px 22px' }}>
      <p style={{ margin: '0 0 12px', fontSize: 20, fontWeight: 900, color: Q.verde }}>{titulo}</p>
      {itens.map((i, idx) => (
        <div key={i.rotulo} style={{ marginBottom: 11 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 15, color: Q.texto, marginBottom: 3 }}>
            <span>{i.rotulo}</span>
            <span>{dec(i.pct)}%</span>
          </div>
          <div style={{ height: 7, background: '#fff', borderRadius: 4 }}>
            <div style={{ width: `${Math.min(100, i.pct * (destaque ? 1.2 : 2))}%`, height: 7, borderRadius: 4, background: destaque && idx === 0 ? Q.laranja : Q.verde2 }} />
          </div>
        </div>
      ))}
    </Cartao>
  );
}

export function IgPublico({ ig }: { ig: QamarInstagram }) {
  const { genero, faixas, cidades } = ig.publico;
  const central = faixas.filter((f) => f.rotulo === '35–44' || f.rotulo === '45–54').reduce((a, f) => a + f.pct, 0);
  return (
    <>
      <div style={{ display: 'flex', gap: 22 }}>
        <Barras titulo="Gênero" itens={genero} destaque />
        <Barras titulo="Faixa etária" itens={faixas.filter((f) => f.pct >= 0.5)} />
        <Barras titulo="Cidades" itens={cidades} destaque />
      </div>
      <Nota>
        {central ? `${dec(central)}% têm entre 35 e 54 anos. ` : ''}Dados do perfil como um todo, hoje{ig.seguidores_total ? ` (${numero(ig.seguidores_total)} seguidores)` : ''}. Cidades: participação no total de seguidores. Fonte: Instagram Insights.
      </Nota>
    </>
  );
}

/* ---------------------------------------------------------------------------------------------- Facebook */

export function FbVisao({ fb, rotulos }: { fb: QamarFacebook; rotulos: Rot }) {
  const cmp = !!rotulos.antes;
  const parcial = fb.status === 'parcial';
  return (
    <div style={{ display: 'flex', gap: 28, flex: 1 }}>
      <div style={{ flex: 1.3 }}>
        <Tabela
          colunas={cab(rotulos, 'Métrica')}
          larguras={cmp ? ['40%', '20%', '20%', '20%'] : ['62%', '38%']}
          linhas={(fb.visao_geral || []).map((l) => linhaMetrica(l, rotulos))}
        />
        <Nota>{parcial ? 'Fonte: Meta Ads (posicionamento Facebook). Alcance somado entre contas de anúncio, então pessoas repetidas contam mais de uma vez.' : 'Fonte: Facebook (API).'}</Nota>
      </div>
      {parcial && (
        <div style={{ flex: 0.8, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {fb.seguidores_hoje != null && (
            <Cartao>
              <Mini>Seguidores hoje</Mini>
              <Grande tam={48}>{numero(fb.seguidores_hoje)}</Grande>
              <p style={{ margin: 0, fontSize: 13, color: Q.mudo }}>Página Moura Leite Loteamentos</p>
            </Cartao>
          )}
          <Cartao tom="laranja" estilo={{ padding: '16px 20px' }}>
            <Mini>Falta o orgânico</Mini>
            <p style={{ margin: '8px 0 0', fontSize: 15, lineHeight: 1.4, color: Q.texto }}>
              Visualizações e alcance da página e interações nos posts só chegam com a permissão read_insights, que um administrador do negócio Moura Leite precisa liberar.
            </p>
          </Cartao>
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- Site */

export function SiteVisao({ site, rotulos }: { site: QamarSite; rotulos: Rot }) {
  const { atual, antes } = site;
  const cmp = !!antes && !!rotulos.antes;
  const c = (t: string, a: string | null, b: string) => (
    <Cartao estilo={{ flex: 1, padding: '20px 26px' }}>
      <p style={{ margin: 0, fontSize: 16, color: Q.mudo }}>{t}</p>
      <p style={{ margin: '10px 0 0', fontSize: 20, color: Q.mudo }}>
        {a !== null && (
          <>
            {a} <span style={{ margin: '0 6px' }}>→</span>
          </>
        )}
        <span style={{ fontSize: 56, fontWeight: 900, color: Q.verde }}> {b}</span>
      </p>
    </Cartao>
  );
  const dif = antes ? atual.usuarios - antes.usuarios : 0;
  const arred = Math.round(Math.abs(dif) / 50) * 50;
  return (
    <>
      <p style={{ margin: '0 0 12px', fontSize: 16, color: Q.mudo }}>{cmp ? `${rotulos.antes} → ${rotulos.atual}` : rotulos.atual}</p>
      <div style={{ display: 'flex', gap: 22, marginBottom: 22 }}>
        {c('Usuários ativos', cmp ? compactoQ(antes!.usuarios) : null, compactoQ(atual.usuarios))}
        {c('Novos usuários', cmp ? compactoQ(antes!.novos) : null, compactoQ(atual.novos))}
      </div>
      <div style={{ display: 'flex', gap: 22 }}>
        {c('Tempo médio de engajamento', cmp ? `${antes!.tempo_engajamento_s ?? '—'}s` : null, `${atual.tempo_engajamento_s ?? '—'}s`)}
        {c('Eventos', cmp ? compactoQ(antes!.eventos) : null, compactoQ(atual.eventos))}
      </div>
      {cmp && (
        <p style={{ margin: '22px 0 0', fontSize: 18, fontWeight: 800, color: Q.verde }}>
          {`O site recebeu cerca de ${numero(arred)} usuários a ${dif >= 0 ? 'mais' : 'menos'} em ${rotulos.atual.toLowerCase()}.`}
        </p>
      )}
      <Nota>Fonte: Google Analytics 4.</Nota>
    </>
  );
}

export function SitePaginas({ site, rotulos }: { site: QamarSite; rotulos: Rot }) {
  const linhas = (d: QamarSite['atual']) => d.paginas.map(([nome, v]) => [nome, numero(v)]);
  const top = site.atual.paginas[0]?.[0];
  const topAntes = site.antes?.paginas[0]?.[0];
  const cmp = !!site.antes && !!rotulos.antes;
  return (
    <>
      <div style={{ display: 'flex', gap: 28 }}>
        {cmp && (
          <div style={{ flex: 1 }}>
            <Tabela colunas={[rotulos.antes!, 'Visualiz.']} larguras={['76%', '24%']} linhas={linhas(site.antes!)} compacta fonte={16} />
          </div>
        )}
        <div style={{ flex: 1 }}>
          <Tabela colunas={[rotulos.atual, 'Visualiz.']} larguras={['76%', '24%']} linhas={linhas(site.atual)} compacta fonte={16} />
        </div>
      </div>
      <p style={{ margin: '18px 0 0', fontSize: 17, fontWeight: 800, color: Q.verde }}>
        {top && cmp && topAntes === top ? `${top} lidera nos dois meses.` : top ? `${top} lidera em ${rotulos.atual.toLowerCase()}.` : ''}
      </p>
      <Nota>Fonte: Google Analytics 4 (páginas e telas).</Nota>
    </>
  );
}

/* ---------------------------------------------------------------------------------------------- Blog e imprensa */

function ListaPosts({ titulo, posts }: { titulo: string; posts: PostBlog[] }) {
  return (
    <Cartao estilo={{ flex: 1, padding: '18px 22px' }}>
      <p style={{ margin: '0 0 8px', fontSize: 20, fontWeight: 900, color: Q.verde }}>
        {titulo} · {posts.length} post{posts.length === 1 ? '' : 's'}
      </p>
      {posts.length === 0 && <p style={{ margin: 0, fontSize: 15, color: Q.mudo }}>Nenhum post publicado.</p>}
      {posts.map((p) => (
        <div key={p.link} style={{ display: 'flex', gap: 12, padding: '5px 0', borderBottom: `1px solid ${Q.linha}`, fontSize: 14, alignItems: 'center' }}>
          <Imagem url={p.imagem} w={58} h={36} raio={5} />
          <span style={{ fontWeight: 800, color: Q.verde, width: 44, flexShrink: 0 }}>{dm(p.data)}</span>
          <span style={{ color: Q.texto }}>{p.titulo}</span>
        </div>
      ))}
    </Cartao>
  );
}

export function BlogPosts({ blog, rotulos }: { blog: QamarRelatorio['blog']; rotulos: Rot }) {
  const cmp = !!rotulos.antes;
  const midia = blog.atual.filter((p) => /m[ií]dia/i.test(p.categoria)).length + (cmp ? blog.antes.filter((p) => /m[ií]dia/i.test(p.categoria)).length : 0);
  return (
    <>
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {cmp && <ListaPosts titulo={rotulos.antes!} posts={blog.antes} />}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <ListaPosts titulo={rotulos.atual} posts={blog.atual} />
          <Cartao tom="laranja" estilo={{ padding: '14px 18px' }}>
            <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: Q.verde, lineHeight: 1.35 }}>
              {cmp ? `${blog.antes.length} post(s) em ${rotulos.antes!.toLowerCase()} e ${blog.atual.length} em ${rotulos.atual.toLowerCase()}` : `${blog.atual.length} post(s) em ${rotulos.atual.toLowerCase()}`}
              {midia ? `; ${midia} na categoria "Na Mídia"` : ''}.
            </p>
          </Cartao>
        </div>
      </div>
      <Nota>Fonte: blog do site mouraleite.com.br.</Nota>
    </>
  );
}

export function Imprensa({ imprensa }: { imprensa: QamarImprensa }) {
  const vazio = !imprensa.itens.length && !imprensa.observacoes;
  return (
    <div style={{ display: 'flex', gap: 28, flex: 1 }}>
      <Cartao estilo={{ flex: 1.3 }}>
        <Mini>Cobertura e ações do mês</Mini>
        {vazio && <p style={{ margin: '12px 0 0', fontSize: 17, color: Q.mudo }}>Preencha o texto na tela do sistema (abaixo do slide) e ele aparece aqui.</p>}
        <ul style={{ margin: '12px 0 0', paddingLeft: 22, fontSize: 18, lineHeight: 1.5, color: Q.texto }}>
          {imprensa.itens.map((i, k) => (
            <li key={k} style={{ marginBottom: 8 }}>
              {i}
            </li>
          ))}
        </ul>
      </Cartao>
      {imprensa.observacoes && (
        <Cartao tom="laranja" estilo={{ flex: 0.9, alignSelf: 'flex-start' }}>
          <Mini>Aproveitamento do conteúdo</Mini>
          <p style={{ margin: '10px 0 0', fontSize: 17, lineHeight: 1.45, color: Q.texto, whiteSpace: 'pre-wrap' }}>{imprensa.observacoes}</p>
        </Cartao>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------------------------------- Tráfego pago */

const periodoAnuncio = (a: AnuncioPago) => (a.periodo[0] === a.periodo[1] ? dm(a.periodo[0]) : `${dm(a.periodo[0])}–${dm(a.periodo[1])}`);

export function PagoAnuncios({ pago, rotulos }: { pago: QamarRelatorio['trafego_pago']; rotulos: Rot }) {
  const agencia = pago.anuncios.filter((a) => a.grupo === 'agencia');
  const auto = pago.anuncios.filter((a) => a.grupo === 'automatico');
  const totalAuto = auto.reduce((s, a) => s + a.investimento, 0);
  return (
    <>
      <Tabela
        colunas={['Anúncio', 'Período', 'Objetivo', 'Investimento', 'Resultado']}
        larguras={['30%', '12%', '19%', '16%', '23%']}
        compacta
        fonte={15.5}
        linhas={agencia.map((a) => [
          <span key="a" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Imagem url={a.miniatura} w={40} h={40} raio={6} />
            <span>{a.anuncio}</span>
          </span>,
          periodoAnuncio(a),
          a.objetivo,
          reaisCentavos(a.investimento),
          <span key="r">
            {numero(a.resultado)} {a.resultado_rotulo}
            <br />
            <span style={{ color: Q.mudo, fontSize: 13 }}>{a.custo_por_resultado != null ? `(${reaisCentavos(a.custo_por_resultado)} cada)` : ''}</span>
          </span>,
        ])}
      />
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', marginTop: 16 }}>
        <div>
          <p style={{ margin: 0, fontSize: 16, color: Q.mudo }}>Investimento total em {rotulos.atual.toLowerCase()}</p>
          <p style={{ margin: 0, fontSize: 44, fontWeight: 900, color: Q.verde, lineHeight: 1.05 }}>{reaisCentavos(pago.total_agencia)}</p>
        </div>
        <p style={{ margin: 0, fontSize: 14, color: Q.mudo, flex: 1, lineHeight: 1.4 }}>
          Meta Ads (Instagram e Facebook), conta CA Moura Leite. Só o gasto dentro do mês.
          {auto.length ? ` Mais ${reaisCentavos(totalAuto)} em ${auto.length} impulsionamento(s) automático(s) do aplicativo, fora deste total.` : ''}
        </p>
      </div>
    </>
  );
}

export function PagoEntrega({ pago }: { pago: QamarRelatorio['trafego_pago'] }) {
  const agencia = pago.anuncios.filter((a) => a.grupo === 'agencia').slice(0, 4);
  return (
    <>
      <div style={{ display: 'flex', gap: 18 }}>
        {agencia.map((a, i) => (
          <Cartao key={a.ad_id ?? a.anuncio} tom={i % 2 ? 'laranja' : 'verde'} estilo={{ flex: 1, minWidth: 0, padding: '14px 16px' }}>
            <Imagem url={a.miniatura} w="100%" h={120} raio={8} />
            <p style={{ margin: '10px 0 0', fontSize: 17, fontWeight: 900, color: Q.verde, lineHeight: 1.15, height: 40, overflow: 'hidden' }}>{a.anuncio}</p>
            <p style={{ margin: '4px 0 12px', fontSize: 13.5, fontWeight: 800, color: Q.verde2 }}>{a.objetivo}</p>
            {[
              ['Alcance', numero(a.alcance)],
              ['Impressões', numero(a.impressoes)],
              ['Frequência', dec(a.frequencia, 2)],
              ['CPM', reaisCentavos(a.cpm)],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${Q.verdeBorda}`, fontSize: 15 }}>
                <span style={{ color: Q.mudo }}>{k}</span>
                <span style={{ fontWeight: 800, color: Q.texto }}>{v}</span>
              </div>
            ))}
          </Cartao>
        ))}
      </div>
      <Nota>Frequência = impressões ÷ alcance. CPM = custo por mil impressões. Fonte: Meta Ads.</Nota>
    </>
  );
}
