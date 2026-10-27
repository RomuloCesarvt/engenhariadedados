import { NextRequest } from 'next/server';
import { proxyDelete, proxyPost } from '../../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** O analista corrige a leitura da conversa de uma venda (POST) ou volta à leitura automática (DELETE). */
export function POST(request: NextRequest) {
  return proxyPost(request, '/api/analista/vendas-online/leitura');
}

export function DELETE(request: NextRequest) {
  return proxyDelete(request, '/api/analista/vendas-online/leitura');
}
