import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ComponentViewer } from '@/components/ui/ComponentViewer';

interface ComponentViewerContextType {
  isOpen: boolean;
  openViewer: () => void;
  closeViewer: () => void;
  toggleViewer: () => void;
}

const ComponentViewerContext = createContext<ComponentViewerContextType | undefined>(undefined);

export function ComponentViewerProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  const openViewer = () => setIsOpen(true);
  const closeViewer = () => setIsOpen(false);
  const toggleViewer = () => setIsOpen(prev => !prev);

  // Global F11 key handler
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check for F11 key (keyCode 122 or key === 'F11')
      if (event.key === 'F11' || event.keyCode === 122) {
        // Prevent browser's default fullscreen behavior
        event.preventDefault();
        setIsOpen(prev => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <ComponentViewerContext.Provider value={{ isOpen, openViewer, closeViewer, toggleViewer }}>
      {children}
      <ComponentViewer open={isOpen} onOpenChange={setIsOpen} />
    </ComponentViewerContext.Provider>
  );
}

export function useComponentViewer() {
  const context = useContext(ComponentViewerContext);
  if (context === undefined) {
    throw new Error('useComponentViewer must be used within a ComponentViewerProvider');
  }
  return context;
}
