'use client';

import { useState, useEffect } from 'react';
import { Sun, Moon } from 'lucide-react';

export function ThemeToggle() {
  const [isLight, setIsLight] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem('moura-leite-theme-v2');
    const shouldUseLight = saved !== 'dark';

    setIsLight(shouldUseLight);
    document.body.classList.toggle('moura-leite-light', shouldUseLight);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (isLight) {
      document.body.classList.add('moura-leite-light');
      localStorage.setItem('moura-leite-theme-v2', 'light');
    } else {
      document.body.classList.remove('moura-leite-light');
      localStorage.setItem('moura-leite-theme-v2', 'dark');
    }
  }, [isLight, mounted]);

  if (!mounted) return null;

  return (
    <button
      onClick={() => setIsLight(!isLight)}
      aria-label={isLight ? 'Ativar modo escuro' : 'Ativar modo claro Moura Leite'}
      title={isLight ? 'Modo escuro' : 'Modo claro Moura Leite'}
      className="shrink-0 flex items-center justify-center w-9 h-9 rounded-full shadow-md transition-all duration-300 hover:scale-105 active:scale-95"
      style={{
        background: isLight
          ? 'linear-gradient(135deg, #1a7a10, #1b4f38)'
          : 'linear-gradient(135deg, #1e293b, #334155)',
        color: '#ffffff',
        border: isLight ? '2px solid #ff7f00' : '2px solid #475569',
        boxShadow: isLight
          ? '0 4px 20px -4px rgba(27, 79, 56, 0.5)'
          : '0 4px 20px -4px rgba(0, 0, 0, 0.5)',
      }}
    >
      {isLight ? (
        <Moon className="w-5 h-5" />
      ) : (
        <Sun className="w-5 h-5" />
      )}
    </button>
  );
}
