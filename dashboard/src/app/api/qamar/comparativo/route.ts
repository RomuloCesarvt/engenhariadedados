import { NextRequest } from 'next/server';
import { proxyGet } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Comparativo entre os meses escolhidos (só insights). */
export function GET(request: NextRequest) {
  return proxyGet(request, '/api/qamar/comparativo', 600000);
}
