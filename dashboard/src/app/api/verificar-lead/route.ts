import { NextRequest } from 'next/server';
import { proxyPost } from '../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Verificação ao vivo no CV e no RD. POST: e-mail e telefone não vão para a URL. */
export function POST(request: NextRequest) {
  return proxyPost(request, '/api/verificar-lead', 90000);
}
