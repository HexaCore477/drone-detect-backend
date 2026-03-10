import { useTranslation } from 'react-i18next';

export function SkyLANXBranding() {
  const { t } = useTranslation();
  
  return (
    <div className="flex items-center justify-center px-2 py-2">
      <img
        src="/logo.png"
        alt={t('header.branding', 'SkyLANX - Laserbased C-UAS System SKL 2KW')}
        className="h-10 w-auto object-contain"
      />
    </div>
  );
}
