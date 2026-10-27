import { NextRequest } from 'next/server';
import { proxyPost } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Salva o texto digitado do relatório (assessoria de imprensa e observações do mês). */
export function POST(request: NextRequest) {
  return proxyPost(request, '/api/qamar/manual', 30000);
}
