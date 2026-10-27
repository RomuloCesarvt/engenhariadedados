/** Relatório mensal da Qamar: o que o motor devolve em /api/qamar. */

export type StatusBloco = 'real' | 'parcial' | 'nao_conectado' | 'erro' | 'manual';

export interface BlocoBase {
  status: StatusBloco;
  mensagem?: string;
  passos?: string[];
  campos?: string[];
  seguidores_hoje?: number | null;
}

export interface LinhaMetrica {
  metrica: string;
  atual: number | null;
  antes: number | null;
  variacao: number | null;
  fmt?: 'n' | 'pct' | 'sinal' | 'reais';
  delta_pp?: number | null;
}

export interface PublicacaoDestaque {
  rotulo: string;
  tipo: 'post' | 'reel';
  dia: string;
  titulo: string;
  link?: string;
  visualizacoes?: number | null;
  interacoes?: number | null;
  comentarios?: number | null;
  curtidas?: number | null;
  alcance?: number | null;
  miniatura?: string | null;
}

export interface ResumoPosts {
  quantidade: number;
  interacoes: number;
  media_interacoes: number | null;
  media_visualizacoes: number | null;
  engajamento_medio: number | null;
  comentarios: number;
  alcance: number;
}

export interface ResumoReels {
  quantidade: number;
  visualizacoes: number;
  media_visualizacoes: number | null;
  interacoes: number;
  alcance: number;
}

export interface StoryGuardado {
  id: string;
  dia: string;
  alcance?: number | null;
  visualizacoes?: number | null;
  interacoes?: number | null;
  miniatura?: string | null;
  titulo?: string;
  arquivo?: string | null;
}

export interface Barra {
  rotulo: string;
  pct: number;
}

export interface QamarInstagram extends BlocoBase {
  visao_geral: LinhaMetrica[];
  tipos_de_interacao: LinhaMetrica[];
  publicacoes: { posts: [number | null, number]; reels: [number | null, number]; stories: [number | null, number] };
  alcance_por_formato: { posts: [number | null, number]; reels: [number | null, number]; stories: [number | null, number] };
  conteudo: { antes: { posts: ResumoPosts; reels: ResumoReels } | null; atual: { posts: ResumoPosts; reels: ResumoReels } };
  stories: {
    atual: { coletados: number; inicio_da_coleta: string | null; cobre_o_mes_inteiro: boolean };
    visualizacoes: number;
    conta: { visualizacoes: number | null; alcance: number | null; interacoes: number | null; compartilhamentos: number | null; curtidas: number | null };
    melhores: StoryGuardado[];
  };
  destaques: PublicacaoDestaque[];
  conteudos: PublicacaoDestaque[];
  mais_comentados: PublicacaoDestaque[];
  publico: { genero: Barra[]; faixas: Barra[]; cidades: Barra[] };
  seguidores_total: number | null;
  seguidores_obs: string | null;
}

export interface QamarFacebook extends BlocoBase {
  visao_geral?: LinhaMetrica[];
  seguidores_hoje?: number | null;
}

export interface DadosSiteMes {
  usuarios: number;
  novos: number;
  tempo_engajamento_s: number | null;
  eventos: number;
  paginas: [string, number][];
}

export interface QamarSite extends BlocoBase {
  atual: DadosSiteMes;
  antes: DadosSiteMes | null;
}

export interface PostBlog {
  data: string;
  titulo: string;
  link: string;
  categoria: string;
  imagem?: string | null;
}

export interface QamarBlog extends BlocoBase {
  atual: PostBlog[];
  antes: PostBlog[];
}

export interface AnuncioPago {
  anuncio: string;
  campanha: string;
  objetivo: string;
  periodo: [string, string];
  investimento: number;
  resultado: number;
  resultado_rotulo: string;
  custo_por_resultado: number | null;
  alcance: number;
  impressoes: number;
  frequencia: number;
  cpm: number;
  miniatura?: string | null;
  ad_id?: string;
  grupo: 'agencia' | 'automatico';
}

export interface QamarTrafego extends BlocoBase {
  anuncios: AnuncioPago[];
  total: number;
  total_agencia: number;
}

export interface VideoYoutube {
  id?: string;
  dia: string;
  titulo: string;
  visualizacoes: number | null;
  curtidas: number | null;
  link: string | null;
  miniatura?: string | null;
}

export interface QamarYoutube extends BlocoBase {
  videos: VideoYoutube[];
  inscritos: string | null;
  ultimo_video: string | null;
  cobre_o_mes?: boolean;
  mais_antigo_lido?: string | null;
}

export interface QamarImprensa extends BlocoBase {
  itens: string[];
  observacoes: string;
}

export interface QamarManual {
  imprensa: string[];
  observacoes: string;
}

export interface QamarRelatorio {
  mes: string;
  anterior: string;
  rotulo: string;
  rotulos: { atual: string; antes: string | null };
  comparar: boolean;
  gerado_em: string;
  instagram: QamarInstagram;
  facebook: QamarFacebook;
  linkedin: BlocoBase;
  tiktok: BlocoBase;
  youtube: QamarYoutube;
  gmn: BlocoBase;
  site: QamarSite;
  blog: QamarBlog;
  imprensa: QamarImprensa;
  trafego_pago: QamarTrafego;
}

type BlocoMes = Record<string, any>;

export interface ResumoMes {
  mes: string;
  rotulo: string;
  instagram: BlocoMes;
  site: BlocoMes;
  blog: BlocoMes;
  trafego_pago: BlocoMes;
  facebook: BlocoMes;
  youtube: BlocoMes;
}

/** Números de cada mês escolhido, lado a lado (/api/qamar/comparativo). */
export interface QamarComparativo {
  meses: string[];
  resumos: ResumoMes[];
  mes_em_andamento: string | null;
  gerado_em: string;
}
