/** Cliente das rotas de BI, bases e conferências. */

import { Apresentacao, Cenario } from '../types/apresentacao';
import { QamarComparativo, QamarManual, QamarRelatorio } from '../types/qamar';
import {
  AudienciaResposta,
  BIResponse,
  ConferenciaBeeviral,
  ConferenciaPlataforma,
  ConferenciaRD,
  EstadoAtualizacao,
  Filtros,
  LeadsDetalheResponse,
  OpcoesResponse,
  BaseInfo,
  VerificacaoLead,
  DiagnosticosResponse,
  AuditoriaAnuncios,
  LeadsDoAnuncioResponse,
  CriativoAnuncio,
  CapaAnuncio,
  AuditoriaVendas,
  AnaliseDigital,
  PalavrasResposta,
  VendasOnlineResposta,
  ExecucaoAnalise,
  LeituraConversa,
} from '../types/bi';

/** Analista digital: alertas, oportunidades e destaques do período, com números e recomendação. */
export function fetchAnalise(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  return getJSON<AnaliseDigital>(`/api/analista?${q.toString()}`);
}

/** Vendas do período × leads online: a análise que vira a planilha da gestão. */
export function fetchVendasOnline(inicio: string, fim: string) {
  return getJSON<VendasOnlineResposta>(`/api/analista/vendas-online?inicio=${inicio}&fim=${fim}`);
}

/** Refaz a análise do período (lê o CV venda a venda) e gera a planilha, em segundo plano. */
export function analisarVendasOnline(inicio: string, fim: string) {
  return getJSON<ExecucaoAnalise>('/api/analista/vendas-online', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inicio, fim }),
  });
}

export const urlRelatorioVendasOnline = (inicio: string, fim: string) =>
  `/api/analista/vendas-online/relatorio?inicio=${inicio}&fim=${fim}`;

/** Corrige a leitura da conversa de uma venda; vale para a tela e para a planilha. */
export function revisarLeituraConversa(idreserva: string, leitura: LeituraConversa, texto?: string) {
  return getJSON('/api/analista/vendas-online/leitura', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idreserva, leitura, texto: texto || null }),
  });
}

/** Volta a valer a leitura automática da conversa. */
export function desfazerRevisaoLeitura(idreserva: string) {
  return getJSON(`/api/analista/vendas-online/leitura?idreserva=${encodeURIComponent(idreserva)}`, { method: 'DELETE' });
}

/** Vendas × leads: cada venda do período cruzada com os sinais de origem online de todas as bases. */
export function fetchAuditoriaVendas(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  if (f.empreendimentos.length === 1) q.set('empreendimento', f.empreendimentos[0]);
  if (f.pracas.length === 1) q.set('praca', f.pracas[0]);
  return getJSON<AuditoriaVendas>(`/api/vendas/auditoria?${q.toString()}`);
}

async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || body.detail || `Erro ${res.status}`);
  return body as T;
}

export function queryDosFiltros(f: Filtros, extra: Record<string, string | number | boolean | undefined | null> = {}) {
  const q = new URLSearchParams();
  q.set('inicio', f.inicio);
  q.set('fim', f.fim);
  // O painel é sempre do online (mesmo recorte do BI gerencial SDR Online)
  q.set('escopo', 'online');
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  Object.entries(extra).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
  });
  return q.toString();
}

export const fetchBI = (f: Filtros) => getJSON<BIResponse>(`/api/bi?${queryDosFiltros(f)}`);

export const fetchOpcoes = () => getJSON<OpcoesResponse>('/api/bi/opcoes');

export function fetchLeadsDetalhe(
  f: Filtros,
  extra: {
    empreendimento?: string;
    canal?: string;
    grupo?: string;
    etapa_minima?: number;
    vendidos?: boolean;
    limite?: number;
    /** Vendas: interesse = empreendimento de interesse do lead (regra do BI); comprado = unidade vendida */
    criterio?: 'interesse' | 'comprado';
    so_outro_empreendimento?: boolean;
  }
) {
  // O detalhe aceita um empreendimento por vez; o filtro global entra quando só há um selecionado
  const empreendimento = extra.empreendimento ?? (f.empreendimentos.length === 1 ? f.empreendimentos[0] : undefined);
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim, escopo: 'online' });
  Object.entries({ ...extra, empreendimento }).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
  });
  return getJSON<LeadsDetalheResponse>(`/api/bi/leads?${q.toString()}`);
}

export const fetchBases = () => getJSON<{ bases: BaseInfo[]; atualizacao: EstadoAtualizacao }>('/api/bases');

export const atualizarBases = (bases?: string[]) =>
  getJSON<EstadoAtualizacao>('/api/bases', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bases ? { bases } : {}),
  });

export function fetchConferenciaBeeviral(f: Filtros) {
  const empreendimento = f.empreendimentos.length === 1 ? f.empreendimentos[0] : undefined;
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim, ...(empreendimento ? { empreendimento } : {}) });
  return getJSON<ConferenciaBeeviral>(`/api/conferencias/beeviral?${q.toString()}`);
}

export function fetchConferenciaPlataforma(plataforma: 'meta' | 'google', f: Filtros) {
  const empreendimento = f.empreendimentos.length === 1 ? f.empreendimentos[0] : undefined;
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim, ...(empreendimento ? { empreendimento } : {}) });
  return getJSON<ConferenciaPlataforma>(`/api/conferencias/plataforma/${plataforma}?${q.toString()}`);
}

export function fetchConferenciaRD(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  return getJSON<ConferenciaRD>(`/api/conferencias/rd?${q.toString()}`);
}

/** Procura o lead ao vivo no CV (todos os leads) e no RD Station. */
export const verificarLead = (email?: string | null, telefone?: string | null) =>
  getJSON<VerificacaoLead>('/api/verificar-lead', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, telefone }),
  });

/** Problemas de dados do período: o quê, por quê, situação e como resolver. */
export function fetchDiagnosticos(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  return getJSON<DiagnosticosResponse>(`/api/diagnosticos?${q.toString()}`);
}

export const resolverDiagnostico = (id: string, nota?: string) =>
  getJSON<unknown>('/api/diagnosticos/resolver', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, nota }),
  });

/** Auditoria de anúncios: plataforma × CV por anúncio e campeões. */
export function fetchAnuncios(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  return getJSON<AuditoriaAnuncios>(`/api/anuncios?${q.toString()}`);
}

/** Apresentação de segunda: o período escolhido comparado com o mesmo intervalo do mês anterior. */
export function fetchApresentacao(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  return getJSON<Apresentacao>(`/api/apresentacao?${q.toString()}`);
}

/** Cenário do CPL: o que mudou, eleição e concorrência por praça. */
export function fetchCenario(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  return getJSON<Cenario>(`/api/cenario?${q.toString()}`);
}

/** Endereço da imagem do anúncio repassado pelo sistema (necessário para gerar o PNG do slide). */
export const urlImagemAnuncio = (url: string) => `/api/anuncios/imagem?${new URLSearchParams({ url }).toString()}`;

/** Audiência do site no Google Analytics, comparada com o período anterior de mesmo tamanho. */
export function fetchAudiencia(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  return getJSON<AudienciaResposta>(`/api/site/audiencia?${q.toString()}`);
}

/** Palavras-chave do Google Ads por empreendimento e palavras buscadas por praça (GA4). */
export function fetchPalavras(f: Filtros) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim });
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  return getJSON<PalavrasResposta>(`/api/anuncios/palavras?${q.toString()}`);
}

export function fetchLeadsDoAnuncio(f: Filtros, chave: string) {
  const q = new URLSearchParams({ inicio: f.inicio, fim: f.fim, chave });
  f.empreendimentos.forEach((e) => q.append('empreendimento', e));
  f.pracas.forEach((p) => q.append('praca', p));
  return getJSON<LeadsDoAnuncioResponse>(`/api/anuncios/leads?${q.toString()}`);
}

/** Criativo do anúncio buscado na hora na Meta: pré-visualização por formato, imagens, vídeos e textos. */
export const fetchCriativo = (anuncioId: string) =>
  getJSON<CriativoAnuncio>(`/api/anuncios/criativo?${new URLSearchParams({ anuncio_id: anuncioId }).toString()}`);

/** Capa grande do anúncio (capa do vídeo ou imagem original) para os cards. */
export const fetchCapa = (anuncioId: string) =>
  getJSON<CapaAnuncio>(`/api/anuncios/capa?${new URLSearchParams({ anuncio_id: anuncioId }).toString()}`);

/** Relatório mensal da Qamar (agência de comunicação), mês contra mês anterior. */
export function fetchQamar(mes: string, atualizar = false, comparar = false) {
  const q = new URLSearchParams({ mes });
  if (atualizar) q.set('atualizar', 'true');
  if (comparar) q.set('comparar', 'true');
  return getJSON<QamarRelatorio>(`/api/qamar?${q.toString()}`);
}

/** Salva o texto digitado do relatório (assessoria de imprensa e observações). */
export function salvarQamarManual(mes: string, dados: QamarManual) {
  return getJSON<QamarManual>('/api/qamar/manual', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mes, ...dados }),
  });
}

/** Comparativo entre os meses escolhidos (só números). */
export function fetchQamarComparativo(meses: string[], atualizar = false) {
  const q = new URLSearchParams();
  meses.forEach((m) => q.append('meses', m));
  if (atualizar) q.set('atualizar', 'true');
  return getJSON<QamarComparativo>(`/api/qamar/comparativo?${q.toString()}`);
}
