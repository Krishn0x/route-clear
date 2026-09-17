import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import { Key } from 'lucide-react';

function App() {
  const [token, setToken] = useState('');

  useEffect(() => {
    setToken(localStorage.getItem('demo_token') || '');
  }, []);

  const handleTokenChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setToken(val);
    localStorage.setItem('demo_token', val);
  };

  return (
    <div className="min-h-screen bg-bg-base text-text-primary font-sans flex flex-col">
      <header className="bg-bg-surface border-b border-border-default">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <div className="flex flex-col">
                <span className="text-xl font-bold tracking-tight text-text-primary flex items-center">
                  ROUTE-CLEAR
                </span>
                <span className="text-[10px] uppercase tracking-widest text-text-secondary mt-0.5">
                  AI Evidence-to-Settlement Controller
                </span>
              </div>
              <div className="h-8 w-px bg-border-default mx-2"></div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono font-medium px-2 py-1 bg-bg-elevated border border-border-default text-text-secondary rounded-sm flex items-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent mr-2"></div>
                  ROUTE_MODE: SIMULATED
                </span>
              </div>
            </div>
            
            <div className="flex items-center">
              <div className="relative rounded-sm flex items-center bg-bg-elevated border border-border-default">
                <div className="pl-3 pr-2 flex items-center pointer-events-none text-text-secondary">
                  <Key className="h-3.5 w-3.5" />
                </div>
                <input
                  type="password"
                  value={token}
                  onChange={handleTokenChange}
                  className="bg-transparent focus:outline-none focus:ring-1 focus:ring-accent block w-48 sm:text-xs text-text-primary py-1.5 pr-3 font-mono placeholder-text-secondary/50"
                  placeholder="DEMO_ACCESS_TOKEN"
                />
              </div>
            </div>
          </div>
        </div>
      </header>
      
      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col">
        <Dashboard />
      </main>
    </div>
  );
}

export default App;
