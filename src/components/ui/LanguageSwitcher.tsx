import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

const languages = [
  { code: 'en', label: 'EN' },
  { code: 'de', label: 'DE' },
];

export function LanguageSwitcher() {
  const { i18n } = useTranslation();

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    localStorage.setItem('language', lng);
  };

  return (
    <div className="flex items-center gap-1 bg-muted/30 rounded px-1 py-0.5">
      {languages.map((lang) => (
        <button
          key={lang.code}
          onClick={() => changeLanguage(lang.code)}
          className={cn(
            'px-2 py-1 text-xs font-mono rounded transition-all',
            i18n.language === lang.code
              ? 'bg-primary text-primary-foreground glow-green'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
          )}
        >
          {lang.label}
        </button>
      ))}
    </div>
  );
}
