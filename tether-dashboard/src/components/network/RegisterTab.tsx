import React, { useState } from 'react';
import { api } from '../../api/client';
import { CopyButton } from '../shared/CopyButton';
import { CheckCircle2, User, Cpu, Server } from 'lucide-react';
import { cn } from '../../utils/cn';

export const RegisterTab: React.FC = () => {
  const [name, setName] = useState('');
  const [type, setType] = useState<'AI Agent' | 'Human'>('AI Agent');
  const [machineLabel, setMachineLabel] = useState('');
  const [description, setDescription] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [successKey, setSuccessKey] = useState('');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    
    setLoading(true);
    try {
      const res = await api.registerAgent({ name, type, machineLabel, description });
      setSuccessKey(res.key);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (successKey) {
    return (
      <div className="h-full flex flex-col items-center pt-12 pb-12 w-full max-w-3xl mx-auto animation-fade-in">
        <CheckCircle2 className="w-16 h-16 text-[#00f2ff] mb-6 shadow-[0_0_20px_rgba(0,242,255,0.2)] rounded-full" />
        <h3 className="text-2xl font-bold mb-2">Registration Complete</h3>
        <p className="text-[#8892b0] mb-12">Agent successfully added to the Tether network.</p>
        
        <div className="w-full bg-[#0f111a] border border-[#ffffff14] rounded-2xl p-8 stat-card-gradient relative overflow-hidden shadow-2xl mb-8">
          <div className="w-full text-left mb-3">
            <span className="text-sm font-semibold tracking-wide text-[#00f2ff] uppercase">Save this — shown once</span>
          </div>
          
          <div className="w-full bg-[#05060a] border border-[#00f2ff]/30 rounded-xl p-6 font-mono text-[#00f2ff] text-lg break-all mb-8 relative group shadow-[inset_0_0_20px_rgba(0,242,255,0.05)]">
            {successKey}
            <div className="absolute top-4 right-4">
              <CopyButton text={successKey} iconOnly className="bg-[#0f111a] border border-[#ffffff14] hover:border-[#00f2ff]/50 w-10 h-10" />
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 bg-[#05060a]/50 rounded-xl border border-[#ffffff14]">
              <h4 className="font-semibold text-sm mb-3 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#8892b0]" /> For AI Agents
              </h4>
              <div className="bg-[#000000] rounded p-3 font-mono text-xs text-[#e0e6ed] border border-[#ffffff14] flex flex-col gap-2">
                <div className="flex justify-between items-center group/code">
                  <span className="truncate mr-2"><span className="text-[#7000ff]">TETHER_API_KEY</span>={successKey}</span>
                  <CopyButton text={`TETHER_API_KEY=${successKey}`} iconOnly className="opacity-0 group-hover/code:opacity-100 transition-opacity w-6 h-6 bg-transparent border-0" />
                </div>
                <div className="flex justify-between items-center group/code">
                  <span className="truncate mr-2"><span className="text-[#7000ff]">TETHER_RELAY_URL</span>=http://localhost:8000</span>
                  <CopyButton text="TETHER_RELAY_URL=http://localhost:8000" iconOnly className="opacity-0 group-hover/code:opacity-100 transition-opacity w-6 h-6 bg-transparent border-0" />
                </div>
              </div>
            </div>
            
            <div className="p-5 bg-[#05060a]/50 rounded-xl border border-[#ffffff14]">
              <h4 className="font-semibold text-sm mb-3 flex items-center gap-2">
                <User className="w-4 h-4 text-[#8892b0]" /> For Humans
              </h4>
              <p className="text-sm text-[#8892b0] leading-relaxed">
                Use this key to log in to this network. You can save it in your password manager for easy access to the dashboard.
              </p>
            </div>
          </div>
        </div>
        
        <button 
          onClick={() => {
            setName(''); setType('AI Agent'); setMachineLabel(''); setDescription(''); setSuccessKey('');
          }}
          className="text-[#8892b0] hover:text-[#e0e6ed] cursor-pointer font-medium text-sm transition-colors border-b border-transparent hover:border-[#e0e6ed] pb-0.5"
        >
          Register Another Agent
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col items-center pt-8 pb-12 w-full max-w-2xl mx-auto">
      <div className="w-full mb-8">
        <h2 className="text-2xl font-bold mb-2 flex items-center gap-3">
          <Server className="w-6 h-6 text-[#00f2ff]" />
          Agent Registration
        </h2>
        <p className="text-[#8892b0] leading-relaxed">
          Create a new identity on the Tether network. The protocol treats AI and humans symmetrically — both authenticate via bearer tokens and receive full routing capabilities.
        </p>
      </div>

      <form onSubmit={handleRegister} className="w-full bg-[#0f111a] border border-[#ffffff14] rounded-2xl p-8 shadow-xl stat-card-gradient relative">
        <div className="space-y-6 mb-8">
          
          {/* Segmented Control for Type */}
          <div>
            <label className="block text-sm font-medium text-[#8892b0] mb-3">Identity Type</label>
            <div className="flex bg-[#05060a] p-1 rounded-xl border border-[#ffffff14]">
              <button
                type="button"
                className={cn(
                  "flex-1 flex justify-center items-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                  type === 'AI Agent' ? "bg-[#0f111a] text-[#00f2ff] shadow-[0_0_10px_rgba(0,242,255,0.1)] border border-[#00f2ff]/20" : "text-[#8892b0] hover:text-[#e0e6ed]"
                )}
                onClick={() => setType('AI Agent')}
              >
                <Cpu className="w-4 h-4" /> AI Agent
              </button>
              <button
                type="button"
                className={cn(
                  "flex-1 flex justify-center items-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                  type === 'Human' ? "bg-[#0f111a] text-[#00f2ff] shadow-[0_0_10px_rgba(0,242,255,0.1)] border border-[#00f2ff]/20" : "text-[#8892b0] hover:text-[#e0e6ed]"
                )}
                onClick={() => setType('Human')}
              >
                <User className="w-4 h-4" /> Human
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#8892b0] mb-1.5">Name <span className="text-[#ef4444]">*</span></label>
            <input 
              type="text" 
              value={name} 
              onChange={e => setName(e.target.value)}
              placeholder="e.g. claude, codex, matt"
              className="w-full bg-[#05060a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg px-4 py-3 text-sm outline-none transition-colors text-[#e0e6ed] placeholder:text-[#8892b0]/50"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#8892b0] mb-1.5">Machine Label <span className="text-[#8892b0]/50 text-xs font-normal">(optional)</span></label>
            <input 
              type="text" 
              value={machineLabel} 
              onChange={e => setMachineLabel(e.target.value)}
              placeholder="e.g. my-laptop, cloud-box"
              className="w-full bg-[#05060a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg px-4 py-3 text-sm outline-none transition-colors text-[#e0e6ed] placeholder:text-[#8892b0]/50 font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#8892b0] mb-1.5">Description <span className="text-[#8892b0]/50 text-xs font-normal">(optional)</span></label>
            <input 
              type="text" 
              value={description} 
              onChange={e => setDescription(e.target.value)}
              placeholder="e.g. Master control node"
              className="w-full bg-[#05060a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg px-4 py-3 text-sm outline-none transition-colors text-[#e0e6ed] placeholder:text-[#8892b0]/50"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !name.trim()}
          className="w-full bg-[#00f2ff] hover:bg-[#00d1d1] text-[#05060a] font-bold py-3.5 rounded-xl transition-all shadow-[0_0_15px_rgba(0,242,255,0.3)] hover:shadow-[0_0_25px_rgba(0,242,255,0.5)] flex items-center justify-center gap-2 disabled:opacity-50 disabled:shadow-none disabled:cursor-not-allowed text-[15px]"
        >
          {loading ? 'Registering...' : 'Register Agent'}
        </button>
      </form>
    </div>
  );
};
