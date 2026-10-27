import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

// Imagens dos stories que a coleta diária guardou (o Instagram só deixa o story no ar por 24 horas).
const PASTA = process.env.QAMAR_MIDIA_DIR || path.join(process.cwd(), '..', 'output', 'qamar_midia');
const TIPOS: Record<string, string> = { '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp' };

export async function GET(_: NextRequest, { params }: { params: { nome: string } }) {
  const nome = path.basename(params.nome);
  const tipo = TIPOS[path.extname(nome).toLowerCase()];
  if (!tipo || !/^[\w.-]+$/.test(nome)) {
    return NextResponse.json({ error: 'Arquivo inválido.' }, { status: 400 });
  }
  try {
    const arquivo = await fs.readFile(path.join(PASTA, nome));
    return new NextResponse(arquivo, { headers: { 'Content-Type': tipo, 'Cache-Control': 'public, max-age=86400' } });
  } catch {
    return NextResponse.json({ error: 'Imagem não encontrada.' }, { status: 404 });
  }
}
