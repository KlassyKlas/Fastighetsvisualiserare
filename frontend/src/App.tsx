import MapContainer from './components/Map/MapContainer';
import Sidebar from './components/Sidebar/Sidebar';
import DemoBanner from './components/UI/DemoBanner';
import FilterBar from './components/UI/FilterBar';
import Legend from './components/UI/Legend';

function App() {
  return (
    <div className="h-screen w-screen flex overflow-hidden">
      <Sidebar />
      <div className="flex-1 relative">
        <FilterBar />
        <MapContainer />
        <Legend />
        <DemoBanner />
      </div>
    </div>
  );
}

export default App;
