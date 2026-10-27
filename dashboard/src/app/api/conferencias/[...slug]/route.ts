import { NextRequest } from 'next/server';
import { proxyGet } from '../../../../lib/engineProxy';

export const dynamic = 'force-dynamic';

/** /api/conferencias/beeviral · /api/conferencias/plataforma/meta · /api/conferencias/plataforma/google */
export function GET(request: NextRequest, { params }: { params: { slug: string[] } }) {
  const caminho = params.slug.map(encodeURIComponent).join('/');
  return proxyGet(request, `/api/conferencias/${caminho}`, 120000);
}
