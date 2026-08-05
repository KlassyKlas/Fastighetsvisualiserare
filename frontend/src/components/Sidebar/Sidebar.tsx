import { Search, Layers, Info, ChevronLeft, ChevronRight } from 'lucide-react';
import clsx from 'clsx';
import { useStore } from '@/store/useStore';
import SearchPanel from './SearchPanel';
import LayerPanel from './LayerPanel';
import ProjectDetails from './ProjectDetails';
import PropertyDetails from './PropertyDetails';

const tabs = [
  { id: 'search' as const, label: 'Sok', icon: Search },
  { id: 'layers' as const, label: 'Lager', icon: Layers },
  { id: 'details' as const, label: 'Detaljer', icon: Info },
];

export default function Sidebar() {
  const {
    sidebarOpen,
    sidebarTab,
    selectedProject,
    selectedProperty,
    setSidebarOpen,
    setSidebarTab,
  } = useStore();

  const renderContent = () => {
    switch (sidebarTab) {
      case 'search':
        return <SearchPanel />;
      case 'layers':
        return <LayerPanel />;
      case 'details':
        if (selectedProject) return <ProjectDetails />;
        if (selectedProperty) return <PropertyDetails />;
        return (
          <div className="p-4 text-slate-500 text-sm">
            Klicka pa ett projekt eller en fastighet pa kartan for att se detaljer.
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div
      className={clsx(
        'relative flex flex-col bg-slate-800 border-r border-slate-700 transition-all duration-300 overflow-hidden z-10',
        sidebarOpen ? 'w-80' : 'w-12',
      )}
    >
      {/* Toggle button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute top-3 -right-0 z-20 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-l p-1 transition-colors"
        title={sidebarOpen ? 'Stang sidopanel' : 'Oppna sidopanel'}
      >
        {sidebarOpen ? (
          <ChevronLeft className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
      </button>

      {/* Tab buttons */}
      <div
        className={clsx(
          'flex border-b border-slate-700',
          sidebarOpen ? 'flex-row' : 'flex-col',
        )}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              if (!sidebarOpen) setSidebarOpen(true);
              setSidebarTab(tab.id);
            }}
            className={clsx(
              'flex items-center justify-center gap-2 px-3 py-3 transition-colors relative text-sm',
              sidebarTab === tab.id
                ? 'text-blue-400'
                : 'text-slate-400 hover:text-slate-200',
              sidebarOpen ? 'flex-1' : 'w-12',
            )}
            title={tab.label}
          >
            <tab.icon className="w-4 h-4 flex-shrink-0" />
            {sidebarOpen && <span>{tab.label}</span>}
            {sidebarTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500" />
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {sidebarOpen && (
        <div className="flex-1 overflow-y-auto">{renderContent()}</div>
      )}
    </div>
  );
}
