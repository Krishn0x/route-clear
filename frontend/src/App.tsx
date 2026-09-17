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
    <div className="min-h-screen">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <span className="text-xl font-bold text-indigo-600">Route-Clear</span>
              <span className="ml-2 text-sm text-gray-500 font-medium px-2 py-1 bg-gray-100 rounded-md">Prototype</span>
            </div>
            <div className="flex items-center">
              <div className="relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Key className="h-4 w-4 text-gray-400" />
                </div>
                <input
                  type="password"
                  value={token}
                  onChange={handleTokenChange}
                  className="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-9 sm:text-sm border-gray-300 rounded-md py-1.5 border"
                  placeholder="Demo Access Token"
                />
              </div>
            </div>
          </div>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Dashboard />
      </main>
    </div>
  );
}

export default App;
