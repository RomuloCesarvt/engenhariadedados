import { NextRequest } from 'next/server';
import { proxyGet } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Palavras mais buscadas de cada praça, segundo o Google Analytics. */
export function GET(request: NextRequest) {
  return proxyGet(request, '/api/anuncios/palavras');
}
