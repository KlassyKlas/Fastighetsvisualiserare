import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { startUrlSync } from './lib/urlSync';
import { useUiStore } from './store/uiStore';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Ett omförsök räcker — misslyckas det går appen till demo-läge
      // (nätverksfel) eller visar felet (HTTP-fel).
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// När backend kommer tillbaka efter demo-läge: ogiltigförklara HELA
// cachen. Annars ligger demo-svar kvar som "färska" under inaktiva
// filternycklar och serveras som riktig data när användaren byter
// tillbaka filter — utan banner, eftersom demoMode redan är false.
useUiStore.subscribe((state, prevState) => {
  if (prevState.demoMode && !state.demoMode) {
    queryClient.invalidateQueries();
  }
});

// Delbara länkar: URL:en tillämpas SYNKRONT före första renderingen —
// gjordes det i en effekt skulle varje query först köras med standard-
// filtren och sedan en gång till med länkens. Därefter speglas storen
// tillbaka till adressfältet (replaceState, debouncat).
startUrlSync();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
