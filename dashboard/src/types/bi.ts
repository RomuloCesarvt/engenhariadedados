/** Tipos das respostas de BI, bases e conferências da engine. */

import { SourceStatus } from './index';

export type Grupo = 'online_pago' | 'online_organico' | 'indicacao_digital' | 'offline' | 'nao_rastreado';
export type Confianca = 'alta' | 'media' | 'baixa' | 'nenhuma';

export interface Filtros {
  inicio: string;
  fim: string;
  empreendimentos: string[];
  pracas: string[];
}

export interface ResumoLeads {
  leads: number;
  online: number;
  pct_online: number | null;
  pago: number;
  organico: number;
  indicacao_digital: number;
  offline: number;
  nao_rastreado: number;
  pct_nao_rastreado: number | null;
}

export interface ResumoVendas {
  vendas: number;
  vgv: number;
  vendas_online: number;
  vgv_online: number;
  pct_vendas_online: number | null;
  vendas_nao_rastreadas: number;
}

export interface Kpis extends ResumoLeads, ResumoVendas {
  anterior: ResumoLeads & ResumoVendas;
  variacao: Record<'leads' | 'online' | 'vendas' | 'vgv' | 'vendas_online', number | null>;
  conversao_coorte_online: number | null;
  conversao_coorte_geral: number | null;
  /** reservas = vendas lidas das reservas do CV; leads = data de venda do lead (sem a base de reservas) */
  fonte_vendas: 'reservas' | 'leads';
  vendas_outro_empreendimento: number;
  unidades_vendidas: number;
  vgv_unidades: number;
  unidades_vendidas_online: number;
  vgv_unidades_online: number;
  unidades_sem_lead: number;
  /** Pessoas distintas entre os interesses cadastrados no período. */
  pessoas_unicas: number;
  /** Interesses que excedem a quantidade de pessoas distintas. */
  interesses_adicionais: number;
  /** Pessoas cuja última conversão registrada no CV ocorreu no período. Não é histórico de eventos. */
  ultima_conversao_pessoas: number;
}

export interface SeriePonto extends Record<Grupo, number> {
  periodo: string;
  rotulo: string;
  vendas: number;
  vendas_online: number;
  vgv: number;
}

export interface Agrupado {
  chave: string;
  label: string;
  grupo?: Grupo;
  grupo_label?: string;
  online: boolean;
  leads: number;
  pct_leads: number | null;
  vendas_coorte: number;
  conversao_coorte: number | null;
  confianca: Partial<Record<Confianca, number>>;
  vendas: number;
  vgv: number;
}

export interface EmpreendimentoBI {
  empreendimento: string;
  praca: string;
  leads: number;
  online: number;
  pago: number;
  organico: number;
  nao_rastreado: number;
  meta: number;
  google: number;
  vendas_coorte: number;
  vendas: number;
  vendas_online: number;
  vgv: number;
  vendas_outro_empreendimento: number;
  unidades_vendidas: number;
  unidades_vendidas_online: number;
  vgv_unidades: number;
  pct_online: number | null;
  pct_nao_rastreado: number | null;
  conversao_coorte: number | null;
  investimento_meta: number;
  investimento_google: number;
  leads_segundo_meta: number;
  leads_segundo_google: number;
  cpl_meta_crm: number | null;
  cpl_google_crm: number | null;
}

export interface ContaInvestimento {
  plataforma: string;
  conta: string;
  empreendimento: string;
  praca: string;
  investimento: number;
  leads_plataforma: number;
}

export interface FunilEtapa {
  etapa: string;
  label: string;
  leads: number;
  pct_do_topo: number | null;
  pct_da_etapa_anterior: number | null;
}

export interface CampanhaBI {
  campanha: string;
  canal: string;
  empreendimento: string;
  leads: number;
  vendas_coorte: number;
  conversao_coorte: number | null;
}

export interface QualidadeBI {
  leads: number;
  nao_rastreado: number;
  pct_nao_rastreado: number | null;
  whatsapp_sem_rastreio: number;
  sem_origem: number;
  sem_empreendimento: number;
  sem_email: number;
  com_utm: number;
  pct_com_utm: number | null;
  confianca: Partial<Record<Confianca, number>>;
  vendas_sem_origem: number;
  pct_vendas_sem_origem: number | null;
}

export interface EquivalenciasBI {
  /** Pessoas online cuja última conversão registrada no CV ocorreu no período. */
  mql_ultima_conversao: number;
  /** Estimativas pelo histórico disponível no lead; não substituem as fatos do modelo semântico. */
  sql_historico: number;
  opps_historico: number;
  atendimentos_historico: number;
  /** Vendas pela data da venda e pelo empreendimento da unidade comprada. */
  unidades_vendidas: number;
  vgv_unidades: number;
  /** Recortes que os Power BIs apresentam com o rótulo genérico "Vendas". */
  vendas_tipo_sdr: number;
  vendas_tipo_sdr_online: number;
  vgv_tipo_sdr_online: number;
  vendas_especialistas: number;
  vendas_sem_tipo: number;
  vgv_sem_tipo: number;
  cv_leads_atualizado_em: string | null;
  cv_reservas_atualizado_em: string | null;
  sql_certificado: boolean;
  novo_lead_mql_certificado: boolean;
  regra_novo_lead_mql: string;
  regra_sql: string;
}

export interface BaseInfo {
  base: string;
  label: string;
  descricao: string;
  essencial: boolean;
  atualizado_em: string | null;
  dados_de: string | null;
  total: number;
  idade_horas: number | null;
  periodo?: { inicio: string; fim: string } | null;
  status: SourceStatus;
}

export interface EstadoAtualizacao {
  em_andamento: boolean;
  base_atual: string | null;
  iniciado_em: string | null;
  concluido_em: string | null;
  fila: string[];
  aceito?: boolean;
}

export interface BIResponse {
  periodo: { inicio: string; fim: string; anterior_inicio: string; anterior_fim: string; granularidade: 'mes' | 'semana' };
  kpis: Kpis;
  serie: SeriePonto[];
  por_grupo: Agrupado[];
  por_canal: Agrupado[];
  por_empreendimento: EmpreendimentoBI[];
  funil: { todos: FunilEtapa[]; online: FunilEtapa[] };
  funil_movimentacao: FunilEtapa[];
  funil_anterior: FunilEtapa[];
  equivalencias_bi: EquivalenciasBI;
  campanhas: CampanhaBI[];
  motivos_perda_online: { motivo: string; leads: number; pct: number | null }[];
  qualidade: QualidadeBI;
  regra_leads?: string;
  investimento: {
    meta: number;
    google: number;
    leads_segundo_meta: number;
    leads_segundo_google: number;
    disponivel: boolean;
    por_conta?: ContaInvestimento[];
  };
  legenda: { grupos: { grupo: Grupo; label: string; online: boolean }[]; canais: { canal: string; label: string; grupo: Grupo }[] };
  bases: BaseInfo[];
  avisos: string[];
}

export interface OpcoesResponse {
  empreendimentos: string[];
  pracas: string[];
  canais: { canal: string; label: string }[];
  bases: BaseInfo[];
  atualizacao: EstadoAtualizacao;
}

export interface LeadDetalhe {
  /** Nas vendas sem lead no CV vem null */
  id: number | null;
  // Só nas vendas (reservas do CV)
  idreserva?: string;
  empreendimento_comprado?: string;
  unidade?: string | null;
  outro_empreendimento?: boolean;
  ligacao?: 'lead_associado' | 'email' | 'telefone' | 'sem_lead';
  midia_reserva?: string | null;
  data: string | null;
  empreendimento: string;
  praca: string;
  canal: string;
  canal_label: string;
  grupo: Grupo;
  online: boolean;
  confianca: Confianca;
  evidencia: string;
  campanha: string | null;
  etapa: number;
  etapa_label: string;
  vendido: boolean;
  data_venda: string | null;
  valor_venda: number;
  situacao: string | null;
  motivo_perda: string | null;
  link: string | null;
}

export type TipoAchado = 'alerta' | 'oportunidade' | 'destaque' | 'contexto';

export interface Achado {
  id: string;
  area: string;
  area_label: string;
  tipo: TipoAchado;
  tipo_label: string;
  prioridade: number;
  titulo: string;
  texto: string;
  recomendacao: string;
  evidencias: { rotulo: string; valor: string }[];
  /** Tela onde conferir o achado (ex.: /anuncios) */
  tela: string | null;
}

export interface AnaliseDigital {
  periodo: { inicio: string; fim: string; anterior_inicio: string; anterior_fim: string };
  manchetes: string[];
  contagem: Record<TipoAchado, number>;
  panorama: {
    leads: number;
    variacao_leads: number | null;
    vendas: number;
    variacao_vendas: number | null;
    vgv: number;
    investimento: number;
    cpl_meta: number | null;
  };
  achados: Achado[];
  areas: Record<string, string>;
  tipos: Record<TipoAchado, string>;
  falhas: string[];
  criterios: string[];
  calculado_em: string;
}

export type StatusVendaAuditada =
  | 'online'
  | 'online_nao_contabilizada'
  | 'online_sem_vinculo'
  | 'provavel_online'
  | 'possivel_online'
  | 'sem_sinal_online';
export type ForcaSinal = 'forte' | 'media' | 'fraco';

export interface SinalOnline {
  tipo:
    | 'lead_online_sem_vinculo'
    | 'outro_lead_online'
    | 'lead_online_antigo'
    | 'midia_reserva_online'
    | 'formulario_meta'
    | 'beeviral'
    | 'rd_station';
  label: string;
  forca: ForcaSinal;
  detalhe: string;
  data: string | null;
  link: string | null;
  link_label: string | null;
}

export interface VendaAuditada {
  idreserva: string;
  data_venda: string;
  empreendimento_comprado: string;
  praca_comprada: string;
  unidade: string | null;
  valor_venda: number;
  status: StatusVendaAuditada;
  status_label: string;
  canal_atual: string;
  grupo_atual: Grupo;
  ligacao: 'lead_associado' | 'email' | 'telefone' | 'sem_lead';
  lead_id: number | null;
  lead_link: string | null;
  empreendimento_interesse: string | null;
  midia_reserva: string | null;
  corretor: string | null;
  imobiliaria: string | null;
  sinais: SinalOnline[];
  sugestao: string;
}

export interface AuditoriaVendas {
  periodo: { inicio: string; fim: string };
  disponivel: boolean;
  resumo: {
    vendas: number;
    vgv: number;
    online: number;
    vgv_online: number;
    online_nao_contabilizada: number;
    vgv_online_nao_contabilizada: number;
    online_sem_vinculo: number;
    vgv_online_sem_vinculo: number;
    provavel_online: number;
    vgv_provavel_online: number;
    /** % das reservas com mídia online (ligadas a lead) em que o lead é mesmo online */
    confiabilidade_midia_reserva: number | null;
    possivel_online: number;
    vgv_possivel_online: number;
    sem_sinal_online: number;
    vgv_sem_sinal_online: number;
    pct_online_contada: number | null;
    pct_online_potencial: number | null;
  };
  leituras: string[];
  por_sinal: { tipo: SinalOnline['tipo']; label: string; forca: ForcaSinal; vendas: number; vgv: number }[];
  por_empreendimento: { empreendimento: string; vendas: number; fortes: number; vgv: number }[];
  por_canal_atual: { canal: string; vendas: number }[];
  midias_reserva: { midia: string; vendas: number }[];
  por_imobiliaria: { nome: string; vendas: number }[];
  itens: VendaAuditada[];
  truncado: boolean;
  cv_busca_url: string | null;
}

export interface LeadsDetalheResponse {
  total: number;
  itens: LeadDetalhe[];
  truncado: boolean;
}

export type StatusIndicacao = 'creditada' | 'sem_credito' | 'ja_era_lead' | 'nao_chegou';

export interface IndicacaoConferida {
  indicacao_id: string;
  data: string;
  campanha: string | null;
  empreendimento: string;
  status: StatusIndicacao;
  status_label: string;
  chave_encontrada: string | null;
  convertida_na_beeviral: boolean;
  cv_id: number | null;
  cv_link: string | null;
  cv_data: string | null;
  cv_canal: string | null;
  cv_evidencia: string | null;
  cv_situacao: string | null;
  cv_vendido: boolean;
  dias_ate_cv: number | null;
  cv_data_venda: string | null;
  cv_valor_venda: number | null;
  bee_link: string | null;
  rd_uuid: string | null;
  rd_link: string | null;
  nome?: string | null;
  email?: string | null;
  telefone?: string | null;
  confirmacao?: { estado: 'pendente' | 'confirmado'; verificado_em?: string };
  indicacoes_do_lead?: number;
  campanhas_do_lead?: string[];
  venda_antes_da_indicacao?: boolean;
}

export interface ConferenciaBeeviral {
  periodo: { inicio: string; fim: string };
  base: BaseInfo;
  resumo: Record<StatusIndicacao, number> & {
    indicacoes: number;
    pct_no_cv: number | null;
    pct_creditada: number | null;
    vendidas: number;
    vgv_vendidas: number;
    vendas_antes_da_indicacao: number;
  };
  status_labels: Record<StatusIndicacao, string>;
  credito_no_cv: { canal: string; indicacoes: number }[];
  por_empreendimento: (Record<StatusIndicacao, number> & { empreendimento: string; indicacoes: number; pct_no_cv: number | null; pct_creditada: number | null })[];
  por_campanha: (Record<StatusIndicacao, number> & { campanha: string; indicacoes: number; pct_no_cv: number | null; pct_creditada: number | null })[];
  itens: IndicacaoConferida[];
  vendas: IndicacaoConferida[];
  cv_busca_url: string | null;
  confirmacao: { pendentes: number; em_andamento: boolean; total: number; feitos: number };
}

export interface ConferenciaPlataforma {
  plataforma: 'meta' | 'google';
  label: string;
  disponivel: boolean;
  base: BaseInfo;
  periodo: { inicio: string; fim: string };
  resumo: {
    leads_plataforma: number;
    leads_crm: number;
    pct_chegou: number | null;
    investimento: number;
    cpl_plataforma: number | null;
    cpl_crm: number | null;
    conversas_whatsapp: number;
  };
  por_empreendimento: {
    empreendimento: string;
    leads_plataforma: number;
    conversas_whatsapp: number;
    leads_crm: number;
    diferenca: number;
    pct_chegou: number | null;
    investimento: number;
    cpl_plataforma: number | null;
    cpl_crm: number | null;
    vendas_coorte: number;
    custo_por_venda: number | null;
  }[];
  por_campanha: { campanha: string; leads_plataforma: number; investimento: number; leads_crm: number; pct_chegou: number | null }[];
  serie: { data: string; leads_plataforma: number; leads_crm: number }[];
  notas: string[];
  formularios?: ConferenciaFormulariosMeta | null;
}

export type StatusRD = 'no_cv' | 'inbound_fora' | 'importado' | 'disparo' | 'outro_fora' | 'pendente';

export interface ConferenciaRD {
  periodo: { inicio: string; fim: string };
  base: BaseInfo;
  base_conversoes: BaseInfo;
  status_labels: Record<StatusRD, string>;
  resumo: Record<StatusRD, number> & {
    contatos: number;
    pct_no_cv: number | null;
    pct_classificado: number | null;
    pct_inbound_perdido: number | null;
  };
  inbound_fora_por_conversao: { conversao: string; contatos: number }[];
  importados_por_lista: { conversao: string; contatos: number }[];
  por_mes: (Record<StatusRD, number> & { mes: string })[];
  itens_inbound_fora: {
    uuid: string;
    data: string;
    status: StatusRD;
    status_label: string;
    primeira_conversao: string | null;
    tipo_entrada: string | null;
    link_rd: string | null;
  }[];
}

export type StatusFormulario = 'no_cv' | 'provavel_no_cv' | 'ja_era_lead' | 'nao_chegou';

export interface LeadFormularioConferir {
  id: string;
  data: string;
  data_hora: string | null;
  nome?: string | null;
  email?: string | null;
  telefone?: string | null;
  campanha: string | null;
  conjunto: string | null;
  anuncio: string | null;
  formulario: string | null;
  pagina: string | null;
  plataforma: string | null;
  organico: boolean | null;
  respostas: Record<string, string | null>;
  empreendimento: string;
  status: StatusFormulario;
  provavel_link: string | null;
  provavel_motivo: string | null;
  provavel_situacao: string | null;
  rd: { no_rd: boolean; uuid: string | null; link: string | null; entrada: string | null; primeira_conversao: string | null; tipo: string | null };
  confirmacao?: { estado: 'pendente' | 'confirmado'; verificado_em?: string };
}

export interface ConferenciaFormulariosMeta {
  disponivel: boolean;
  base: BaseInfo;
  rd_disponivel: boolean;
  cv_busca_url: string | null;
  cobertura: { inicio: string | null; fim: string | null };
  status_labels: Record<StatusFormulario, string>;
  resumo: Record<StatusFormulario, number> & {
    leads: number;
    pct_nao_chegou: number | null;
    vendidos: number;
    nao_chegou_mas_no_rd: number;
    nao_chegou_nem_no_rd: number;
  };
  credito_errado_no_cv: { canal: string; leads: number }[];
  por_empreendimento: (Record<StatusFormulario, number> & { empreendimento: string; leads: number; pct_nao_chegou: number | null })[];
  por_formulario: (Record<StatusFormulario, number> & { formulario: string; leads: number; pct_nao_chegou: number | null })[];
  itens_nao_chegaram: LeadFormularioConferir[];
  itens_provaveis: LeadFormularioConferir[];
  indice_cv: { leads: number; cobre_todos_os_leads: boolean };
  confirmacao: { pendentes: number; confirmados: number; corrigidos: number; em_andamento: boolean; total: number; feitos: number };
}

export interface VerificacaoLead {
  verificado_em: string;
  cv: {
    consultado: boolean;
    encontrado: boolean;
    busca_url: string | null;
    consultas: { por: string; encontrados: number }[];
    leads: { idlead: number | string; link: string | null; data_cad: string | null; situacao: string | null; midia: string | null; empreendimentos: string[] }[];
    erros: string[];
  };
  rd: { consultado: boolean; encontrado: boolean; uuid?: string; link?: string | null; erro?: string };
}

export type SeveridadeDiagnostico = 'critico' | 'atencao' | 'info';

export interface Diagnostico {
  id: string;
  categoria: string;
  categoria_label: string;
  severidade: SeveridadeDiagnostico;
  situacao: 'pendente' | 'resolvido';
  titulo: string;
  o_que: string;
  por_que: string;
  como_resolver: string[];
  situacao_motivo: string;
  periodo: { inicio: string | null; fim: string | null } | null;
  evidencias: { rotulo: string; valor: string }[];
  links: { label: string; url: string; interno?: boolean }[];
  resolucao_manual: boolean;
  primeira_deteccao?: string | null;
  resolvido_em?: string | null;
  nota_resolucao?: string | null;
}

export interface CorrecaoSistema {
  id: string;
  data: string;
  titulo: string;
  o_que: string;
  por_que: string;
  como_foi_resolvido: string[];
  impacto: string;
}

export interface DiagnosticosResponse {
  calculado_em: string;
  periodo: { inicio: string; fim: string };
  resumo: { pendentes_criticos: number; pendentes_atencao: number; pendentes_info: number; resolvidos: number; total: number };
  itens: Diagnostico[];
  correcoes: CorrecaoSistema[];
}

export interface AnuncioAuditado {
  chave: string;
  anuncio: string;
  conjunto: string | null;
  campanha: string | null;
  conta: string | null;
  empreendimento: string;
  status: string | null;
  miniatura: string | null;
  anuncio_ids: string[];
  sem_dados_da_plataforma: boolean;
  dias_com_investimento: number;
  investimento: number;
  impressoes: number;
  cliques: number;
  ctr: number | null;
  cpc: number | null;
  leads_plataforma: number;
  conversas_whatsapp: number;
  cpl_plataforma: number | null;
  leads_cv: number;
  pct_chegou: number | null;
  cpl_real: number | null;
  sql: number;
  agendamentos: number;
  vendas: number;
  vgv: number;
  taxa_sql: number | null;
  taxa_venda: number | null;
  custo_por_sql: number | null;
  custo_por_venda: number | null;
  roas: number | null;
  eficiencia: number | null;
  fontes: Record<string, number>;
}

export interface CampeaoAnuncio {
  id: string;
  titulo: string;
  criterio: string;
  metrica: string;
  valor: number | null;
  anuncio: AnuncioAuditado | null;
  motivo_vazio: string | null;
}

export interface AuditoriaAnuncios {
  periodo: { inicio: string; fim: string };
  base: BaseInfo;
  disponivel: boolean;
  filtro_ativo: boolean;
  motivo_vazio: string | null;
  empreendimentos_com_anuncios: { empreendimento: string; anuncios: number; investimento: number }[];
  criterios: { min_leads_conversao: number; min_leads_cpl: number; min_investimento_cpl: number };
  resumo: {
    investimento: number;
    leads_plataforma: number;
    leads_meta_cv: number;
    leads_atribuidos: number;
    sem_anuncio: number;
    cobertura: number | null;
    cpl_real: number | null;
    vendas: number;
    vgv: number;
    roas: number | null;
    anuncios: number;
    anuncios_com_leads: number;
  };
  motivos_sem_anuncio: { motivo: string; leads: number }[];
  medianas: { leads_cv: number | null; cpl_real: number | null };
  campeoes: CampeaoAnuncio[];
  anuncios: AnuncioAuditado[];
  avisos: string[];
}

export interface LeadDoAnuncio {
  id: number | string;
  data: string | null;
  data_cadastro: string | null;
  empreendimento: string;
  situacao: string | null;
  etapa_label: string;
  vendido: boolean;
  valor_venda: number;
  data_venda: string | null;
  fonte: string;
  evidencia: string;
  link: string | null;
}

export interface LeadsDoAnuncioResponse {
  chave: string;
  total: number;
  itens: LeadDoAnuncio[];
}

export interface CriativoAnuncio {
  anuncio_id: string;
  nome?: string | null;
  status?: string | null;
  tipo?: string;
  previews: { formato: string; rotulo: string; src: string; largura: number | null; altura: number | null }[];
  imagens: { url: string; largura: number | null; altura: number | null; formato: string; onde: string | null }[];
  videos: {
    video_id: string;
    player: string | null;
    capa: string | null;
    duracao_s: number;
    largura: number | null;
    altura: number | null;
    formato: string;
    onde: string | null;
    link: string | null;
  }[];
  textos: { titulos: string[]; textos: string[]; descricoes: string[] };
  links: { label: string; url: string }[];
  erro: string | null;
}

export interface CapaAnuncio {
  anuncio_id: string;
  url: string | null;
  largura: number | null;
  altura: number | null;
  tipo: 'video' | 'imagem' | null;
  duracao_s: number | null;
  erro: string | null;
}

/** Vendas online do período: casos (online, mas não registrados no CV) e o que veio do online mas não virou venda online. */
export type LeituraConversa = 'online' | 'perda' | 'nao_nossa';

export interface CasoVendaOnline {
  idreserva: string;
  produto: string;
  cliente: string | null;
  data_venda: string;
  valor: number;
  situacao: string;
  data_distrato: string | null;
  corretor: string | null;
  imobiliaria: string | null;
  tipo_venda: string;
  canal: string;
  link_reserva: string | null;
  do_time: boolean;
  resultado: 'caso' | 'perda' | 'nao_nossa';
  resultado_label: string;
  leitura: {
    leitura: LeituraConversa | null;
    leitura_label: string | null;
    motivo: string | null;
    motivo_label: string | null;
    texto: string | null;
    destaques: string[];
    trechos: { data: string | null; lead: string; texto: string }[];
    revisada: boolean;
    revisado_em: string | null;
    leitura_automatica: LeituraConversa | null;
  };
  conversao: string | null;
  conv_ref: string;
  dias_conv_venda: number;
  janela: string;
  tratativa: string;
  registros_tratativa: string;
  lead: { id: string; nome: string | null; origem: string; detalhe_origem: string; link: string | null } | null;
}

export interface ProdutoVendaOnline {
  produto: string;
  vendas: number;
  vgv: number;
  online: number;
  pct_online: number;
  tirados_do_online: number;
  online_cv: number;
  pct_online_cv: number;
  com_conversao: number;
  outro_corretor: number;
  casos: number;
  vgv_casos: number;
  perdas: number;
}

/** Uma linha de qualquer quadro da audiência: canal, origem, aparelho, cidade, produto ou página. */
export interface LinhaAudiencia {
  sessoes: number;
  pct: number | null;
  usuarios: number;
  engajamento: number | null;
  conversoes: number;
  taxa_conversao: number | null;
  sessoes_antes: number;
  variacao: number | null;
  canal?: string;
  origem?: string;
  dispositivo?: string;
  cidade?: string;
  estado?: string[];
  praca?: string | null;
  empreendimento?: string;
  pagina?: string;
  tipo?: string;
}

export interface TotaisAudiencia {
  sessoes: number;
  usuarios: number;
  novos_usuarios: number;
  sessoes_engajadas: number;
  conversoes: number;
  tempo_engajamento: number;
  pct_novos: number | null;
  engajamento: number | null;
  taxa_conversao: number | null;
  tempo_medio: number | null;
}

export interface AnaliseAudiencia {
  chave: string;
  tipo: 'alerta' | 'destaque' | 'contexto';
  titulo: string;
  texto: string;
}

export interface AudienciaResposta {
  periodo: { inicio: string; fim: string; dias: number };
  anterior: { inicio: string; fim: string };
  totais: TotaisAudiencia & { anterior: TotaisAudiencia; variacao: Record<string, number | null> };
  canais: LinhaAudiencia[];
  origens: LinhaAudiencia[];
  dispositivos: LinhaAudiencia[];
  entradas: LinhaAudiencia[];
  produtos: LinhaAudiencia[];
  paginas: LinhaAudiencia[];
  cidades: {
    cidades: LinhaAudiencia[];
    sessoes: number;
    distintas: number;
    das_nossas_pracas: number;
    pct_das_nossas_pracas: number | null;
    base: BaseInfo | null;
  };
  analises: AnaliseAudiencia[];
  base: BaseInfo | null;
  observacao: string;
}

export interface ExecucaoAnalise {
  em_andamento: boolean;
  periodo: string | null;
  mensagem: string | null;
  iniciado_em: string | null;
  concluido_em: string | null;
  erro: string | null;
  aceito?: boolean;
}

export interface VendasOnlineResposta {
  disponivel: boolean;
  regra_desatualizada?: boolean;
  periodo: { inicio: string; fim: string };
  execucao: ExecucaoAnalise;
  gerado_em?: string;
  relatorio?: string;
  resumo?: {
    vendas: number;
    vgv: number;
    distratos: number;
    online: number;
    vgv_online: number;
    online_cv: number;
    online_cv_sdr: number;
    online_cv_lead: number;
    tirados_do_online: number;
    vgv_tirados_do_online: number;
    nao_online_cv: number;
    com_conversao: number;
    outro_corretor: number;
    ja_atendia: number;
    casos: number;
    vgv_casos: number;
    casos_distrato: number;
    perdas: number;
    vgv_perdas: number;
    nao_nossas: number;
    vgv_nao_nossas: number;
    fora_janela: number;
    sem_conversao: number;
    leituras_revisadas: number;
  };
  por_produto?: ProdutoVendaOnline[];
  casos?: CasoVendaOnline[];
  nao_viraram?: CasoVendaOnline[];
  produtos?: string[];
  time?: string[];
}

/** Palavras mais buscadas por praça (Google Analytics). */
export interface PalavraBuscada {
  palavra: string;
  tipo: string;
  sessoes: number;
  usuarios: number;
  conversoes: number;
  empreendimentos: string[];
  campanhas: string[];
}

export interface PracaPalavras {
  praca: string;
  sessoes: number;
  conversoes: number;
  palavras_distintas: number;
  palavras: PalavraBuscada[];
}

export interface PalavraChave {
  palavra: string;
  correspondencia: string | null;
  investimento: number;
  impressoes: number;
  cliques: number;
  conversoes: number;
  ctr: number | null;
  cpc: number | null;
  custo_por_conversao: number | null;
  campanhas: string[];
}

export interface TermoBuscado {
  termo: string;
  impressoes: number;
  cliques: number;
  conversoes: number;
  canais: string[];
}

export interface EmpreendimentoPalavras {
  empreendimento: string;
  praca: string;
  investimento: number;
  impressoes: number;
  cliques: number;
  conversoes: number;
  custo_por_conversao: number | null;
  palavras_distintas: number;
  palavras_com_conversao: number;
  palavras: PalavraChave[];
  sem_conversao: PalavraChave[];
  termos: TermoBuscado[];
  termos_distintos: number;
  termos_cliques: number;
  termos_conversoes: number;
  termos_canais: string[];
}

export interface PalavrasResposta {
  periodo: { inicio: string; fim: string };
  google: {
    periodo: { inicio: string; fim: string; por_mes: string[] };
    empreendimentos: EmpreendimentoPalavras[];
    base: BaseInfo;
    base_termos: BaseInfo;
    granularidade: { palavras: string; termos: string; meses_dos_termos: string[] };
    observacao: string;
    observacao_termos: string;
  };
  ga4: {
    periodo: { inicio: string; fim: string; por_mes: string[] };
    pracas: PracaPalavras[];
    base: BaseInfo;
    observacao: string;
  };
}
