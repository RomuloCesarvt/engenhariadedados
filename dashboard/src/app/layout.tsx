import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Lead Recon Engine - Monitoramento e Reconciliação de Leads por Origem vs CV CRM',
  description: 'Solução de alto nível e dashboard interativo para validação e auditoria de volume de leads por origem vs CRM Construtor de Vendas.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="antialiased selection:bg-sky-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
