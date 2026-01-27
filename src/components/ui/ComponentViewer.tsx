import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, Component } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ComponentInfo {
  name: string;
  category: string;
  path: string;
  description?: string;
}

const components: ComponentInfo[] = [
  // Layout Components
  { name: 'Header', category: 'Layout', path: '@/components/layout/Header' },
  
  // Tracking Components
  { name: 'CameraView', category: 'Tracking', path: '@/components/tracking/CameraView' },
  { name: 'KalmanDisplay', category: 'Tracking', path: '@/components/tracking/KalmanDisplay' },
  { name: 'LogViewer', category: 'Tracking', path: '@/components/tracking/LogViewer' },
  { name: 'PTUDisplay', category: 'Tracking', path: '@/components/tracking/PTUDisplay' },
  { name: 'ScenarioSelector', category: 'Tracking', path: '@/components/tracking/ScenarioSelector' },
  { name: 'TargetInfo', category: 'Tracking', path: '@/components/tracking/TargetInfo' },
  
  // UI Components
  { name: 'Accordion', category: 'UI', path: '@/components/ui/accordion' },
  { name: 'Alert', category: 'UI', path: '@/components/ui/alert' },
  { name: 'AlertDialog', category: 'UI', path: '@/components/ui/alert-dialog' },
  { name: 'AspectRatio', category: 'UI', path: '@/components/ui/aspect-ratio' },
  { name: 'Avatar', category: 'UI', path: '@/components/ui/avatar' },
  { name: 'Badge', category: 'UI', path: '@/components/ui/badge' },
  { name: 'Breadcrumb', category: 'UI', path: '@/components/ui/breadcrumb' },
  { name: 'Button', category: 'UI', path: '@/components/ui/button' },
  { name: 'Calendar', category: 'UI', path: '@/components/ui/calendar' },
  { name: 'Card', category: 'UI', path: '@/components/ui/card' },
  { name: 'Carousel', category: 'UI', path: '@/components/ui/carousel' },
  { name: 'Chart', category: 'UI', path: '@/components/ui/chart' },
  { name: 'Checkbox', category: 'UI', path: '@/components/ui/checkbox' },
  { name: 'Collapsible', category: 'UI', path: '@/components/ui/collapsible' },
  { name: 'Command', category: 'UI', path: '@/components/ui/command' },
  { name: 'ContextMenu', category: 'UI', path: '@/components/ui/context-menu' },
  { name: 'DataPanel', category: 'UI', path: '@/components/ui/DataPanel' },
  { name: 'Dialog', category: 'UI', path: '@/components/ui/dialog' },
  { name: 'Drawer', category: 'UI', path: '@/components/ui/drawer' },
  { name: 'DropdownMenu', category: 'UI', path: '@/components/ui/dropdown-menu' },
  { name: 'Form', category: 'UI', path: '@/components/ui/form' },
  { name: 'HoverCard', category: 'UI', path: '@/components/ui/hover-card' },
  { name: 'Input', category: 'UI', path: '@/components/ui/input' },
  { name: 'InputOTP', category: 'UI', path: '@/components/ui/input-otp' },
  { name: 'Label', category: 'UI', path: '@/components/ui/label' },
  { name: 'Menubar', category: 'UI', path: '@/components/ui/menubar' },
  { name: 'NavigationMenu', category: 'UI', path: '@/components/ui/navigation-menu' },
  { name: 'Pagination', category: 'UI', path: '@/components/ui/pagination' },
  { name: 'Popover', category: 'UI', path: '@/components/ui/popover' },
  { name: 'Progress', category: 'UI', path: '@/components/ui/progress' },
  { name: 'RadioGroup', category: 'UI', path: '@/components/ui/radio-group' },
  { name: 'Resizable', category: 'UI', path: '@/components/ui/resizable' },
  { name: 'ScrollArea', category: 'UI', path: '@/components/ui/scroll-area' },
  { name: 'Select', category: 'UI', path: '@/components/ui/select' },
  { name: 'Separator', category: 'UI', path: '@/components/ui/separator' },
  { name: 'Sheet', category: 'UI', path: '@/components/ui/sheet' },
  { name: 'Sidebar', category: 'UI', path: '@/components/ui/sidebar' },
  { name: 'Skeleton', category: 'UI', path: '@/components/ui/skeleton' },
  { name: 'Slider', category: 'UI', path: '@/components/ui/slider' },
  { name: 'Sonner', category: 'UI', path: '@/components/ui/sonner' },
  { name: 'StatusIndicator', category: 'UI', path: '@/components/ui/StatusIndicator' },
  { name: 'Switch', category: 'UI', path: '@/components/ui/switch' },
  { name: 'Table', category: 'UI', path: '@/components/ui/table' },
  { name: 'Tabs', category: 'UI', path: '@/components/ui/tabs' },
  { name: 'Textarea', category: 'UI', path: '@/components/ui/textarea' },
  { name: 'Toast', category: 'UI', path: '@/components/ui/toast' },
  { name: 'Toaster', category: 'UI', path: '@/components/ui/toaster' },
  { name: 'Toggle', category: 'UI', path: '@/components/ui/toggle' },
  { name: 'ToggleGroup', category: 'UI', path: '@/components/ui/toggle-group' },
  { name: 'Tooltip', category: 'UI', path: '@/components/ui/tooltip' },
  
  // Navigation
  { name: 'NavLink', category: 'Navigation', path: '@/components/NavLink' },
  
  // Pages
  { name: 'Index', category: 'Pages', path: '@/pages/Index' },
  { name: 'NotFound', category: 'Pages', path: '@/pages/NotFound' },
  { name: 'OperationalView', category: 'Pages', path: '@/pages/OperationalView' },
  { name: 'WaterfallView', category: 'Pages', path: '@/pages/WaterfallView' },
];

interface ComponentViewerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ComponentViewer({ open, onOpenChange }: ComponentViewerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const categories = Array.from(new Set(components.map(c => c.category)));

  const filteredComponents = components.filter(component => {
    const matchesSearch = component.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         component.path.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !selectedCategory || component.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const groupedComponents = filteredComponents.reduce((acc, component) => {
    if (!acc[component.category]) {
      acc[component.category] = [];
    }
    acc[component.category].push(component);
    return acc;
  }, {} as Record<string, ComponentInfo[]>);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] flex flex-col p-0">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-2xl">
              <Component className="w-6 h-6 text-primary" />
              Component Viewer
            </DialogTitle>
            <Badge variant="outline" className="font-mono text-xs">
              {filteredComponents.length} components
            </Badge>
          </div>
        </DialogHeader>

        <div className="flex-1 flex flex-col min-h-0">
          {/* Search and Filter */}
          <div className="px-6 py-4 border-b space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search components..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={cn(
                  'px-3 py-1 text-xs rounded-md border transition-colors',
                  !selectedCategory
                    ? 'bg-primary/20 border-primary text-primary'
                    : 'bg-background border-border text-muted-foreground hover:bg-muted'
                )}
              >
                All
              </button>
              {categories.map(category => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={cn(
                    'px-3 py-1 text-xs rounded-md border transition-colors',
                    selectedCategory === category
                      ? 'bg-primary/20 border-primary text-primary'
                      : 'bg-background border-border text-muted-foreground hover:bg-muted'
                  )}
                >
                  {category}
                </button>
              ))}
            </div>
          </div>

          {/* Component List */}
          <ScrollArea className="flex-1 px-6 py-4">
            <div className="space-y-6">
              {Object.entries(groupedComponents).map(([category, categoryComponents]) => (
                <div key={category}>
                  <h3 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wider">
                    {category}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {categoryComponents.map(component => (
                      <div
                        key={component.name}
                        className="group p-3 rounded-lg border border-border bg-card hover:bg-muted/50 hover:border-primary/50 transition-all cursor-pointer"
                        onClick={() => {
                          // Copy import path to clipboard
                          navigator.clipboard.writeText(`import { ${component.name} } from '${component.path}';`);
                        }}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Component className="w-4 h-4 text-primary" />
                              <span className="font-semibold text-sm">{component.name}</span>
                            </div>
                            <code className="text-xs text-muted-foreground font-mono">
                              {component.path}
                            </code>
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                          Click to copy import path
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              
              {filteredComponents.length === 0 && (
                <div className="text-center py-12 text-muted-foreground">
                  <Component className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>No components found matching your search.</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>

        <div className="px-6 py-3 border-t bg-muted/30">
          <p className="text-xs text-muted-foreground text-center">
            Press <kbd className="px-2 py-1 bg-background border border-border rounded text-xs font-mono">F11</kbd> to toggle this viewer • Click any component to copy its import path
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
