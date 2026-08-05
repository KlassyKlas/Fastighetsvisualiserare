import clsx from 'clsx';
import { ChevronLeft, ChevronRight, Info, Layers, Search, TrendingUp } from 'lucide-react';
import { useUiStore, type SidebarTab } from '@/store/uiStore';
import AnalysisPanel from './AnalysisPanel';
import DetailPlanDetails from './DetailPlanDetails';
import LayerPanel from './LayerPanel';
import ProjectDetails from './ProjectDetails';
import PropertyDetails from './PropertyDetails';
import SearchPanel from './SearchPanel';

const tabs: { id: SidebarTab; label: string; icon: typeof Search }[] = [
  { id: 'search', label: 'Sök', icon: Search },
  { id: 'layers', label: 'Lager', icon: Layers },
  { id: 'analysis', label: 'Analys', icon: TrendingUp },
  { id: 'details', label: 'Detaljer', icon: Info },
];

export default function Sidebar() {
  const sidebarOpen = useUiStore((s) => s.sidebarOpen);
  const sidebarTab = useUiStore((s) => s.sidebarTab);
  const selectedProject = useUiStore((s) => s.selectedProject);
  const selectedProperty = useUiStore((s) => s.selectedProperty);
  const selectedDetailPlan = useUiStore((s) => s.selectedDetailPlan);
  const setSidebarOpen = useUiStore((s) => s.setSidebarOpen);
  const setSidebarTab = useUiStore((s) => s.setSidebarTab);

  const renderContent = () => {
    switch (sidebarTab) {
      case 'search':
        return <SearchPanel />;
      case 'layers':
        return <LayerPanel />;
      case 'analysis':
        return <AnalysisPanel />;
      case 'details':
        if (selectedProject) return <ProjectDetails />;
        if (selectedProperty) return <PropertyDetails />;
        if (selectedDetailPlan) return <DetailPlanDetails />;
        return (
          <div className="p-4 text-slate-500 text-sm">
            Klicka på ett projekt, en fastighet eller en detaljplan på kartan för att se detaljer.
          </div>
        );
    }
  };

  return (
    <div
      className={clsx(
        'relative flex flex-col bg-slate-800 border-r border-slate-700 transition-all duration-300 overflow-hidden z-10',
        sidebarOpen ? 'w-80' : 'w-12',
      )}
    >
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute top-3 -right-0 z-20 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-l p-1 transition-colors"
        title={sidebarOpen ? 'Stäng sidopanel' : 'Öppna sidopanel'}
      >
        {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>

      <div
        className={clsx('flex border-b border-slate-700', sidebarOpen ? 'flex-row' : 'flex-col')}
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
              sidebarTab === tab.id ? 'text-blue-400' : 'text-slate-400 hover:text-slate-200',
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

      {sidebarOpen && <div className="flex-1 overflow-y-auto">{renderContent()}</div>}
    </div>
  );
}
