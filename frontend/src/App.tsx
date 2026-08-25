import MapContainer from './components/Map/MapContainer';
import PropertyReport from './components/Report/PropertyReport';
import Sidebar from './components/Sidebar/Sidebar';
import DemoBanner from './components/UI/DemoBanner';
import ErrorBanner from './components/UI/ErrorBanner';
import FilterBar from './components/UI/FilterBar';
import Legend from './components/UI/Legend';
import TimelineBar from './components/UI/TimelineBar';

function App() {
  return (
    <div className="h-screen w-screen flex overflow-hidden">
      <Sidebar />
      <div className="flex-1 relative">
        <FilterBar />
        <TimelineBar />
        <MapContainer />
        <Legend />
        <DemoBanner />
        <ErrorBanner />
      </div>
      <PropertyReport />
    </div>
  );
}

export default App;
