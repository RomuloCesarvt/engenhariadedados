/**
 * Cores dos gráficos — paleta categórica escura validada (scripts/validate_palette.js)
 * contra o fundo real dos cartões (#111827). A ordem dos slots é o mecanismo de
 * segurança para daltonismo: não reordenar sem validar de novo.
 */

import { Grupo } from '../types/bi';

export const SERIES = {
  s1: '#3987e5', // azul
  s2: '#d95926', // laranja
  s3: '#199e70', // verde-água
  s4: '#c98500', // amarelo
};

export const NEUTRO = '#64748b'; // "Não rastreado" e contexto: cinza de menor ênfase

export const GRUPO_COR: Record<Grupo, string> = {
  online_pago: SERIES.s1,
  online_organico: SERIES.s2,
  indicacao_digital: SERIES.s3,
  offline: SERIES.s4,
  nao_rastreado: NEUTRO,
};

export const GRUPO_ORDEM: Grupo[] = ['online_pago', 'online_organico', 'indicacao_digital', 'offline', 'nao_rastreado'];

export const GRUPO_LABEL: Record<Grupo, string> = {
  online_pago: 'Online — mídia paga',
  online_organico: 'Online — orgânico',
  indicacao_digital: 'Indicação (Indique e Ganhe)',
  offline: 'Offline / comercial',
  nao_rastreado: 'Não rastreado',
};

/** Tinta do gráfico (texto nunca usa a cor da série). */
export const TINTA = {
  superficie: '#111827',
  primaria: '#f1f5f9',
  secundaria: '#cbd5e1',
  apagada: '#94a3b8',
  grade: '#1f2937',
  eixo: '#334155',
};

export const STATUS = {
  bom: '#0ca30c',
  atencao: '#fab219',
  serio: '#ec835a',
  critico: '#d03b3b',
};

export const CONFIANCA_LABEL: Record<string, string> = {
  alta: 'Alta (UTM)',
  media: 'Média (mídia do CV)',
  baixa: 'Baixa (tag/origem)',
  nenhuma: 'Sem evidência',
};
