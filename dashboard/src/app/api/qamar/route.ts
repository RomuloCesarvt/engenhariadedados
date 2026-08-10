import { NextRequest } from 'next/server';
import { proxyGet } from '../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** Relatório mensal da agência de comunicação (Qamar): redes sociais, site, blog, imprensa e tráfego pago. */
export function GET(request: NextRequest) {
  return proxyGet(request, '/api/qamar', 300000);
}
