/** Resposta de /api/apresentacao: o que a reunião de segunda apresenta, já compilado pela engine. */

import { BaseInfo } from './bi';

export type FonteChave = 'meta' | 'google' | 'organico' | 'indicacao' | 'pago_outro';

export interface BlocoFonte {
  leads: number;
  sql: number;
  pct_sql: number | null;
  vendas: number;
  investimento: number;
  cpl: number | null;
  custo_sql: number | null;
  leads_plataforma?: number;
  cpl_plataforma?: number | null;
  investimento_whatsapp?: number;
  leads_whatsapp?: number;
  cpl_com_whatsapp?: number | null;
}

export interface BlocoTotal extends BlocoFonte {
  leads_pagos: number;
  opps?: number;
  leads_pagos_com_custo?: number;
  leads_whatsapp?: number;
  cpl_com_whatsapp?: number | null;
  pessoas_unicas: number;
}

export type VariacaoBloco = Record<'leads' | 'sql' | 'vendas' | 'investimento' | 'cpl' | 'custo_sql', number | null>;

export interface ResumoApresentacao {
  total: BlocoTotal;
  fontes: Record<FonteChave, BlocoFonte>;
  anterior: { total: BlocoTotal; fontes: Record<FonteChave, BlocoFonte> };
  variacao: { total: VariacaoBloco; fontes: Record<FonteChave, VariacaoBloco> };
}

export interface EmpreendimentoApresentacao {
  empreendimento: string;
  praca: string;
  leads: number;
  meta: number;
  google: number;
  organico: number;
  meta_ctw?: number;
  meta_form?: number;
  outros: number;
  sql: number;
  vendas: number;
  investimento: number;
  invest_meta: number;
  invest_google: number;
  cpl: number | null;
  pct_sql: number | null;
  custo_sql?: number | null;
}

export interface OrigemOrganica {
  origem: string;
  canal?: string;
  pago?: boolean;
  leads: number;
  sql: number;
  vendas: number;
  pct: number | null;
  pct_sql: number | null;
}

export interface OrganicosApresentacao {
  total: number;
  com_utm?: number;
  pct_com_utm?: number | null;
  por_origem: OrigemOrganica[];
  por_canal?: OrigemOrganica[];
}

export interface AnuncioRanking {
  chave: string;
  anuncio: string;
  conjunto: string | null;
  campanha: string | null;
  empreendimento: string;
  miniatura: string | null;
  anuncio_ids: string[];
  status: string | null;
  sem_dados_da_plataforma: boolean;
  investimento: number;
  impressoes: number;
  cliques: number;
  ctr: number | null;
  leads_plataforma: number;
  leads_cv: number;
  cpl_real: number | null;
  leads_efetivos?: number | null;
  cpl_efetivo?: number | null;
  base_leads?: 'CV' | 'Meta' | null;
  leads_est?: number;
  sql_est?: number;
  vendas_est?: number;
  sql_efetivo?: number;
  taxa_sql_efetiva?: number | null;
  leads_total?: number;
  sql: number;
  taxa_sql: number | null;
  custo_por_sql: number | null;
  vendas: number;
  taxa_venda: number | null;
  vgv: number;
}

export interface CriterioAnuncio {
  id: 'menor_cpl' | 'mais_leads' | 'mais_sql' | 'maior_conversao';
  titulo: string;
  metrica: 'cpl_real' | 'leads_cv' | 'sql' | 'taxa_venda' | 'taxa_sql';
  descricao: string;
  motivo_vazio: string;
  ranking: AnuncioRanking[];
}

export interface GrupoCriativo {
  resultados_meta?: number;
  custo_resultado_meta?: number | null;
  nome: string;
  criativos?: number;
  anuncios: number;
  investimento: number;
  leads_cv: number;
  sql: number;
  vendas: number;
  cpl: number | null;
  pct_sql: number | null;
  exemplo: { anuncio: string; leads_cv: number } | null;
}

export type CriativoQueFunciona = Omit<AnuncioRanking, 'investimento' | 'leads_cv' | 'sql' | 'cpl' | 'vendas'> & {
  formato: string;
  tema: string;
  copias: number;
  variacoes?: number;
  investimento: number;
  leads_cv: number;
  sql: number;
  cpl: number;
  vendas: number;
  pracas: string[];
};

export interface CampanhaGoogle {
  campanha: string;
  empreendimento: string;
  tipo: string;
  investimento: number;
  impressoes: number;
  cliques: number;
  leads_plataforma: number;
  cpl: number | null;
  ctr: number | null;
  cpc: number | null;
}

export interface TermoPesquisa {
  termo: string;
  impressoes: number;
  cliques: number;
  investimento: number;
  conversoes: number;
  ctr: number | null;
  cpc: number | null;
  custo_por_conversao: number | null;
  campanhas: string[];
  empreendimentos: string[];
}

export interface TermosGrupo {
  cliques: number;
  investimento: number;
  conversoes: number;
  termos_distintos: number;
  cobertura: number | null;
  mais_cliques: TermoPesquisa[];
  mais_conversoes: TermoPesquisa[];
}

export interface AnuncioGoogle {
  anuncio: string;
  tipo: string;
  campanha: string | null;
  grupo: string | null;
  forca: string | null;
  empreendimento: string;
  investimento: number;
  impressoes: number;
  cliques: number;
  conversoes: number;
  ctr: number | null;
  cpc: number | null;
  custo_por_conversao: number | null;
}

export interface CriterioGoogle {
  id: string;
  titulo: string;
  metrica: 'conversoes' | 'custo_por_conversao' | 'ctr';
  descricao: string;
  motivo_vazio: string;
  ranking: AnuncioGoogle[];
}

export interface DetalhesGoogle {
  acoes: { acao: string; categoria: string | null; conversoes: number; todas: number; pct: number | null }[];
  aparelhos: {
    dispositivo: string;
    impressoes: number;
    cliques: number;
    investimento: number;
    conversoes: number;
    pct_cliques: number | null;
    taxa_conversao: number | null;
    custo_por_conversao: number | null;
  }[];
  participacao: {
    campanha: string;
    impressoes: number;
    participacao: number | null;
    perdida_orcamento: number | null;
    perdida_ranking: number | null;
  }[];
  base: BaseInfo;
}

export interface PalavraChave {
  palavra: string;
  correspondencia: string | null;
  investimento: number;
  cliques: number;
  conversoes: number;
  custo_por_conversao: number | null;
  ctr: number | null;
  empreendimento: string;
}

export interface QuadroSite {
  sessoes: number;
  pct: number | null;
  usuarios: number;
  engajamento: number | null;
  conversoes: number;
  taxa_conversao: number | null;
  sessoes_antes: number;
  variacao: number | null;
  origem?: string;
  canal?: string;
  pagina?: string;
}

export interface SiteApresentacao {
  totais: {
    sessoes: number;
    usuarios: number;
    conversoes: number;
    taxa_conversao: number | null;
    anterior: { sessoes: number; usuarios: number; conversoes: number; taxa_conversao: number | null };
    variacao: Record<'sessoes' | 'usuarios' | 'conversoes', number | null>;
  };
  origens: QuadroSite[];
  canais: QuadroSite[];
  paginas: QuadroSite[];
  base: BaseInfo;
  dados_ate: string | null;
}

export interface Apresentacao {
  regra_leads?: 'bi' | 'cv';
  periodo: { inicio: string; fim: string; dias: number };
  comparacao: { inicio: string; fim: string };
  filtro: { empreendimentos: string[]; pracas: string[] };
  resumo: ResumoApresentacao;
  fontes: { chave: FonteChave; label: string }[];
  por_empreendimento: EmpreendimentoApresentacao[];
  organicos: OrganicosApresentacao;
  anuncios: {
    disponivel: boolean;
    total: number;
    cobertura: number | null;
    minimos: { leads_cpl: number; investimento_cpl: number; leads_conversao: number };
    criterios: CriterioAnuncio[];
  };
  anuncios_por_praca?: Record<
    string,
    {
      total: number;
      leads_da_plataforma: boolean;
      minimos: { leads_cpl: number; investimento_cpl: number; leads_conversao: number };
      criterios: CriterioAnuncio[];
      quadro?: AnuncioRanking[];
      google?: CampanhaGoogle[];
      novos?: AnunciosNovos;
      novos_por_produto?: Record<string, AnunciosNovos>;
    }
  >;
  concorrencia?: ConcorrenciaApresentacao;
  organicos_origem?: OrganicosOrigem | null;
  ctw_x_formulario?: CtwXFormulario | null;
  metas_leads?: MetasLeads | null;
  completude?: { ok: boolean; itens: { nivel: 'erro' | 'aviso'; texto: string }[] } | null;
  criativos: {
    por_formato: GrupoCriativo[];
    por_tema: GrupoCriativo[];
    melhores?: CriativoQueFunciona[];
    criativos_total?: number;
    anuncios_total?: number;
    cpl_mediana?: number | null;
    ocultos?: { criativos: number; investimento: number };
    observacao: string;
  };
  google: {
    campanhas: CampanhaGoogle[];
    termos: { pmax: TermosGrupo; pesquisa: TermosGrupo; base: BaseInfo; exato: boolean };
    anuncios: { total: number; criterios: CriterioGoogle[]; base: BaseInfo };
    detalhes: DetalhesGoogle;
    palavras_chave: PalavraChave[];
  };
  site: SiteApresentacao;
  bases: BaseInfo[];
  avisos: string[];
}

export interface MetricasPlataforma {
  investimento: number;
  impressoes: number;
  cliques: number;
  leads: number;
  cpm: number | null;
  ctr: number | null;
  cpc: number | null;
  conversao: number | null;
  cpl: number | null;
}

export interface BlocoCenario {
  plataforma: string;
  dias_antes?: number;
  dias_agora?: number;
  antes: MetricasPlataforma;
  agora: MetricasPlataforma;
  variacao: Record<'investimento' | 'cpm' | 'ctr' | 'cpc' | 'conversao' | 'cpl', number | null>;
  atribuicao: { sentido: 'alta' | 'queda' | 'estavel'; preco: number | null; clique: number | null; conversao: number | null } | null;
}

export interface PracaCenario {
  praca: string;
  investimento_agora: number;
  var_investimento: number | null;
  var_cpm: number | null;
  var_conversao: number | null;
  var_cpl: number | null;
  concorrencia: { maior_busca: number; novos_na_campanha: number; loteadoras: number; anunciantes: number } | null;
}

export interface CenarioPraca {
  praca: string;
  meta: BlocoCenario;
  google: BlocoCenario;
  serie: { meta: { semana: string; cpm: number | null; cpl: number | null }[] };
  contas: { conta: string; var_cpl: number | null; var_conversao: number | null }[];
  concorrencia: {
    maior_busca: number;
    anunciantes: number;
    loteadoras: number;
    corretores: number;
    novos_na_campanha: number;
    lista: { nome: string; anuncios: number; desde: string; tipo: string }[];
  } | null;
  leitura: { tipo: 'fato' | 'indicio' | 'atencao' | 'limite'; texto: string }[];
}

export interface Cenario {
  cenarios_por_praca: CenarioPraca[];
  periodo: { inicio: string; fim: string };
  janelas: { base: [string, string]; recente: [string, string] };
  mes_contra_mes: Record<'meta' | 'google', BlocoCenario>;
  antes_da_eleicao_contra_agora: Record<'meta' | 'google', BlocoCenario>;
  serie: {
    meta: { semana: string; investimento: number; cpm: number | null; cpc: number | null; conversao: number | null; cpl: number | null }[];
    google: { semana: string; investimento: number; cpm: number | null; cpc: number | null; conversao: number | null; cpl: number | null }[];
    meta_2025: { semana: string; cpm: number | null }[];
  };
  eleicao: {
    inicio_campanha: string;
    primeiro_turno: string;
    segundo_turno: string;
    pausas_meta: { de: string; ate: string }[];
    var_cpm_geral: number | null;
    contas_estaveis: number;
    contas_estaveis_cpm_subiu: number;
    mediana_cpm_contas_estaveis: number | null;
  };
  por_praca: PracaCenario[];
  concorrencia: {
    disponivel: boolean;
    coletado_em?: string;
    fonte?: string;
    limites?: string;
    pracas: {
      praca: string;
      maior_busca: number;
      anunciantes: number;
      loteadoras: number;
      novos_na_campanha: number;
      principais: { nome: string; anuncios: number; desde: string; tipo: string }[];
    }[];
  };
  leitura: { tipo: 'fato' | 'indicio' | 'atencao' | 'limite'; texto: string }[];
  avisos: string[];
}

export interface Anunciante {
  nome: string;
  tipo: 'loteadora' | 'corretor';
  anuncios: number;
  buscas: number;
  desde: string | null;
  novo: boolean;
  grande?: boolean;
  presenca: number;
}

export interface ParticipacaoGoogle {
  impressoes: number;
  apareceu: number;
  perdida_orcamento: number;
  perdida_ranking: number;
  campanhas: { campanha: string; impressoes: number; apareceu: number; perdida_ranking: number; perdida_orcamento: number }[];
}

export interface ConcorrenciaPraca {
  google: {
    agora: ParticipacaoGoogle | null;
    antes: ParticipacaoGoogle | null;
    cpc: { investimento: number; cliques: number; cpc: number } | null;
    cpc_antes: { investimento: number; cliques: number; cpc: number } | null;
    var_cpc: number | null;
  };
  meta: { cpm: number | null; cpm_antes: number | null; var_cpm: number | null };
  anunciantes: {
    praca: string;
    buscas: Record<string, number>;
    maior_busca: number;
    anunciantes: number;
    loteadoras: number;
    corretores: number;
    novos: number;
    descartados: number;
    lista: Anunciante[];
    principais: Anunciante[];
  } | null;
}

export interface ConcorrenciaApresentacao {
  disponivel: boolean;
  coletado_em: string | null;
  consultas: number;
  inicio_campanha: string;
  pracas: Record<string, ConcorrenciaPraca>;
  auction_insights: string;
}

export interface OrganicosOrigem {
  total: number;
  com_rastro_de_anuncio: number;
  cadastrados_antes_do_periodo?: number;
  reclassificados?: { total: number; meta: number; google: number; sql: number; com_rastro?: number; whatsapp_sem_rastro?: number; anuncios: { nome: string; leads: number }[] } | null;
  categorias: { categoria: string; leads: number; sql: number; vendas: number; pct: number | null; pct_sql: number | null; detalhes: { nome: string; leads: number }[] }[];
  indique_e_ganhe: { campanha: string; leads: number }[];
}

export interface BlocoCanalMeta {
  conversas?: number;
  formularios?: number;
  investimento: number;
  leads: number;
  leads_plataforma: number;
  sql: number;
  opps: number;
  vendas: number;
  cpl: number | null;
  pct_sql: number | null;
  pct_opps: number | null;
  custo_sql: number | null;
  custo_opps: number | null;
  custo_venda: number | null;
}

export interface CtwXFormulario {
  total: { ctw: BlocoCanalMeta; formulario: BlocoCanalMeta };
  pracas: { praca: string; ctw: BlocoCanalMeta; formulario: BlocoCanalMeta }[];
  outras_campanhas: number;
}

export interface MetaProduto {
  praca: string;
  produto: string;
  arquivo: string;
  mapeamento_assumido: boolean;
  sem_dados: boolean;
  mes: string;
  meta_base: number;
  saldo_anterior: number;
  meta_efetiva: number;
  atingido: number | null;
  falta: number;
  pct: number | null;
  projecao: number | null;
  pct_projecao: number | null;
  ritmo_necessario_dia: number | null;
  ritmo_atual_dia?: number | null;
  inicio_saldo?: string;
  investimento_mes?: number;
  leads_pagos?: number;
  cpl_pago?: number | null;
  cpl_usado?: number | null;
  cpl_historico?: number | null;
  cpl_base?: string;
  investir_a_mais?: number | null;
  falta_fim_projetada?: number | null;
  prox_meta_base?: number;
  prox_meta_efetiva?: number;
  prox_investimento?: number | null;
  investimento_ritmo_mes?: number | null;
  historico: { mes: string; meta_base: number; saldo_anterior: number; meta_efetiva: number; atingido: number | null; falta: number }[];
}

export interface MetasLeads {
  mes: string;
  ate: string;
  dias_decorridos: number;
  dias_no_mes: number;
  inicio_saldo: string;
  dados_do_cv_ate?: string | null;
  meta_usada: string;
  fonte?: string;
  pracas: {
    praca: string;
    meta_base: number;
    saldo_anterior: number;
    meta_efetiva: number;
    atingido: number;
    falta: number;
    projecao: number;
    pct: number | null;
    pct_projecao: number | null;
    ritmo_atual_dia?: number;
    ritmo_necessario_dia?: number;
    investimento_mes?: number;
    investir_a_mais?: number;
    falta_fim_projetada?: number;
    prox_meta_base?: number;
    prox_meta_efetiva?: number;
    prox_investimento?: number;
    investimento_ritmo_mes?: number;
    sem_dados?: boolean;
    produtos: MetaProduto[];
  }[];
  prox_mes?: string | null;
  peso_cpl_mes?: number;
  total: { meta_base: number; saldo_anterior: number; meta_efetiva: number; atingido: number; falta: number; projecao: number; ritmo_atual_dia?: number; ritmo_necessario_dia?: number; investimento_mes?: number; investir_a_mais?: number; falta_fim_projetada?: number; prox_meta_base?: number; prox_meta_efetiva?: number; prox_investimento?: number; investimento_ritmo_mes?: number };
}

export interface AnuncioNovo extends AnuncioRanking {
  primeiro_dia: string | null;
  dias_no_ar: number;
  leads_por_dia: number;
  cpl_vs_referencia: number | null;
  resultados_meta: number;
  custo_resultado_meta: number | null;
  custo_resultado_vs_referencia: number | null;
  ctr: number | null;
}

export interface AnunciosNovos {
  desde: string | null;
  total_novos?: number;
  sem_resultado_ainda?: number;
  anuncios: AnuncioNovo[];
  sem_resultado?: (AnuncioRanking & { primeiro_dia: string | null; dias_no_ar: number })[];
  referencia: { cpl: number | null; leads_por_dia: number | null; custo_resultado_meta: number | null; anuncios_veteranos: number } | null;
}
