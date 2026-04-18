import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { IssuedKey } from '../../types/tier';
import { KeyCard } from './KeyCard';
import { Plus } from 'lucide-react';
import { LoadingSpinner } from '../shared/LoadingSpinner';

export function KeyManager() {
  const [keys, setKeys] = useState<IssuedKey[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchKeys() {
      try {
        const data = await api.getKeys();
        setKeys(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    fetchKeys();
  }, []);

  const handleRevoke = async (id: string) => {
    try {
      await api.revokeKey(id);
      setKeys(keys.map(k => k.id === id ? { ...k, isActive: false } : k));
    } catch (e) {
      console.error(e);
    }
  };

  const handleRotate = async (id: string) => {
    alert("Rotate functionality not implemented in mock.");
  };

  return (
    <div className="w-full max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold mb-1">API Keys</h1>
          <p className="text-[#8892b0] text-sm">Manage agent access keys and usage limits.</p>
        </div>
        
        <button className="flex items-center gap-2 bg-[#00f2ff] hover:bg-[#00d1d1] text-white px-4 py-2 rounded-lg font-medium transition-colors text-sm">
          <Plus className="w-4 h-4" />
          Issue New Key
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {keys.map((k) => (
            <KeyCard 
              key={k.id} 
              apiKey={k} 
              onRevoke={handleRevoke}
              onRotate={handleRotate}
            />
          ))}
          {keys.length === 0 && (
            <div className="col-span-full py-12 text-center text-[#8892b0] border border-dashed border-[#ffffff14] rounded-xl flex flex-col items-center">
              <p>No keys found. Issue one to get started.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
