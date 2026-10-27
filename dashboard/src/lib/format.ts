/** Formatação pt-BR usada em todo o BI. */

const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const umaCasa = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const moedaCentavos = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2 });

export const numero = (n: number | null | undefined) => (n === null || n === undefined ? '—' : inteiro.format(n));

export const pct = (n: number | null | undefined) => (n === null || n === undefined ? '—' : `${umaCasa.format(n)}%`);

export const reais = (n: number | null | undefined) => (n === null || n === undefined ? '—' : moeda.format(n));

export const reaisCentavos = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : moedaCentavos.format(n);

/** 1.284 · 12,9 mil · 4,2 mi — para cartões e rótulos curtos. */
export function compacto(n: number | null | undefined, prefixo = ''): string {
  if (n === null || n === undefined) return '—';
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return `${prefixo}${umaCasa.format(n / 1_000_000_000)} bi`;
  if (abs >= 1_000_000) return `${prefixo}${umaCasa.format(n / 1_000_000)} mi`;
  if (abs >= 10_000) return `${prefixo}${umaCasa.format(n / 1_000)} mil`;
  return `${prefixo}${inteiro.format(n)}`;
}

export const reaisCompacto = (n: number | null | undefined) => compacto(n, 'R$ ');

export function data(iso: string | null | undefined): string {
  if (!iso) return '—';
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${a.slice(2)}`;
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function idade(horas: number | null | undefined): string {
  if (horas === null || horas === undefined) return 'nunca atualizada';
  if (horas < 1) return `há ${Math.max(1, Math.round(horas * 60))} min`;
  if (horas < 48) return `há ${Math.round(horas)} h`;
  return `há ${Math.round(horas / 24)} dias`;
}

/** Nome curto do empreendimento: "Avaré - Central Parque II - 13900" → "Central Parque II (Avaré)". */
export function empreendimentoCurto(nome: string): string {
  const partes = nome.split(/\s+-\s+/);
  if (partes.length >= 3) return `${partes.slice(1, -1).join(' - ')} (${partes[0]})`;
  if (partes.length === 2 && /\d/.test(partes[1])) return partes[0];
  return nome;
}
