import { NextRequest, NextResponse } from 'next/server';
import { createHash } from 'crypto';
import { mkdir, readFile, writeFile } from 'fs/promises';
import path from 'path';

export const dynamic = 'force-dynamic';

// A URL da miniatura que a Meta devolve expira em poucos dias e o CDN pode ficar fora do ar (ou bloqueado na rede). Toda imagem lida é guardada em
// disco; se a Meta não responder depois, a Apresentação usa a cópia guardada. A chave é o caminho da imagem (o que não muda), sem os parâmetros assinados.
const PASTA = path.join(process.cwd(), '.cache', 'imagens');
const chave = (u: URL) => createHash('sha1').update(u.hostname.split('.').slice(-2).join('.') + u.pathname).digest('hex');
async function doCache(u: URL) {
  try {
    const base = path.join(PASTA, chave(u));
    return { corpo: await readFile(base + '.bin'), tipo: (await readFile(base + '.tipo', 'utf-8')) || 'image/jpeg' };
  } catch {
    return null;
  }
}
async function guardar(u: URL, corpo: Buffer, tipo: string) {
  try {
    await mkdir(PASTA, { recursive: true });
    const base = path.join(PASTA, chave(u));
    await writeFile(base + '.bin', corpo);
    await writeFile(base + '.tipo', tipo);
  } catch {
    /* o cache é um reforço: falhar em gravar não pode derrubar a imagem */
  }
}

// A imagem do criativo vem do CDN da Meta, que não libera leitura para outro site (CORS). Para gerar o
// PNG do slide a imagem precisa ser do mesmo endereço do sistema: este repasse busca e devolve.
const HOSTS = /(^|\.)(fbcdn\.net|facebook\.com|fbsbx\.com|cdninstagram\.com|mouraleite\.com\.br|mziq\.com|ytimg\.com)$/i;

export async function GET(request: NextRequest) {
  const alvo = request.nextUrl.searchParams.get('url');
  let url: URL;
  try {
    url = new URL(alvo || '');
  } catch {
    return NextResponse.json({ error: 'Endereço da imagem inválido.' }, { status: 400 });
  }
  if (url.protocol !== 'https:' || !HOSTS.test(url.hostname)) {
    return NextResponse.json({ error: 'Só imagens da Meta, do YouTube e do site da Moura Leite podem ser repassadas.' }, { status: 400 });
  }
  try {
    const resposta = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(20000) });
    const tipo = resposta.headers.get('content-type') || '';
    if (!resposta.ok || !tipo.startsWith('image/')) throw new Error(`A Meta não devolveu a imagem (${resposta.status}).`);
    const corpo = Buffer.from(await resposta.arrayBuffer());
    await guardar(url, corpo, tipo);
    return new NextResponse(corpo, { headers: { 'Content-Type': tipo, 'Cache-Control': 'public, max-age=3600' } });
  } catch (e: any) {
    const copia = await doCache(url);
    if (copia) return new NextResponse(copia.corpo, { headers: { 'Content-Type': copia.tipo, 'Cache-Control': 'public, max-age=300', 'X-Imagem-Do-Cache': '1' } });
    return NextResponse.json({ error: `Não foi possível buscar a imagem: ${e?.message}` }, { status: 502 });
  }
}
