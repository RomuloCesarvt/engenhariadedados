/**
 * Protege todo o dashboard com senha (HTTP Basic). Os dados exibidos incluem e-mails
 * e telefones de leads, então o site não pode ficar público.
 * Defina DASHBOARD_PASSWORD no projeto da Vercel. Qualquer nome de usuário é aceito.
 */

import { NextRequest, NextResponse } from 'next/server';

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function middleware(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;

  if (!password) {
    if (process.env.NODE_ENV === 'production') {
      return new NextResponse('DASHBOARD_PASSWORD não está configurada no projeto.', { status: 503 });
    }
    return NextResponse.next(); // desenvolvimento local
  }

  const [scheme, encoded] = (request.headers.get('authorization') ?? '').split(' ');
  if (scheme === 'Basic' && encoded) {
    try {
      const decoded = atob(encoded);
      const provided = decoded.slice(decoded.indexOf(':') + 1);
      if (safeEqual(provided, password)) return NextResponse.next();
    } catch {}
  }

  return new NextResponse('Autenticação necessária.', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="Lead Recon", charset="UTF-8"' },
  });
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
