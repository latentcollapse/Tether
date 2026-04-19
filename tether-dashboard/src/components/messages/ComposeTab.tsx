import React, { useState } from 'react';
import { Mail, CheckCircle2 } from 'lucide-react';
import { api } from '../../api/client';
import { useAgentStore } from '../../store/agentStore';
import { truncateHandle } from '../../utils/formatters';

export const ComposeTab: React.FC = () => {
  const [to, setTo] = useState('');
  const [subject, setSubject] = useState('');
  const [text, setText] = useState('');
  const [ticketId, setTicketId] = useState('');
  const [loading, setLoading] = useState(false);
  const [successHandle, setSuccessHandle] = useState('');

  const agents = useAgentStore(s => Object.values(s.agents));

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!to || !subject || !text) return;

    setLoading(true);
    try {
      const res = await api.sendMessage({
        to,
        subject,
        text,
        ticketId: ticketId || undefined
      });
      setSuccessHandle(res.handle);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (successHandle) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <CheckCircle2 className="w-16 h-16 text-[#00ff88] mb-4" />
        <h3 className="text-xl font-semibold mb-2">Message Routed</h3>
        <p className="text-[#8892b0] mb-6">Your message was successfully queued for delivery.</p>
        <div className="bg-[#05060a] border border-[#ffffff14] rounded-lg px-4 py-3 font-mono text-[#7000ff] text-sm">
          {truncateHandle(successHandle)}
        </div>
        <button 
          onClick={() => {
            setTo(''); setSubject(''); setText(''); setTicketId(''); setSuccessHandle('');
          }}
          className="mt-8 text-[#00f2ff] hover:underline cursor-pointer font-medium text-sm"
        >
          Compose another
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSend} className="h-full overflow-y-auto p-6 max-w-3xl flex flex-col gap-5">
      <div>
        <label className="block text-sm font-medium text-[#8892b0] mb-1.5">To</label>
        <select 
          value={to} 
          onChange={e => setTo(e.target.value)}
          className="w-full bg-[#05060a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg px-3 py-2 text-sm outline-none transition-colors text-[#e0e6ed]"
          required
        >
          <option value="" disabled>Select agent...</option>
          {agents.map(a => (
            <option key={a.id} value={a.id}>{a.name} ({a.id})</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-[#8892b0] mb-1.5">Subject</label>
        <input 
          type="text" 
          value={subject} 
          onChange={e => setSubject(e.target.value)}
          placeholder="Message subject"
          className="w-full bg-[#05060a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg px-3 py-2 text-sm outline-none transition-colors text-[#e0e6ed] placeholder:text-[#8892b0]/50"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-[#8892b0] mb-1.5">Ticket ID <span className="text-[#8892b0]/50 text-xs">(optional)</span></label>
        <input 
          type="text" 
          value={ticketId} 
          onChange={e => setTicketId(e.target.value)}
          placeholder="e.g. D-248"
          className="w-full bg-[#05060a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg px-3 py-2 text-sm outline-none transition-colors text-[#e0e6ed] placeholder:text-[#8892b0]/50"
        />
      </div>

      <div className="flex-1 min-h-[200px]">
        <label className="block text-sm font-medium text-[#8892b0] mb-1.5">Message</label>
        <textarea 
          value={text} 
          onChange={e => setText(e.target.value)}
          placeholder="Enter your message..."
          className="w-full h-48 bg-[#05060a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-lg px-3 py-3 text-sm outline-none transition-colors text-[#e0e6ed] placeholder:text-[#8892b0]/50 resize-none font-sans"
          required
        />
      </div>

      <div className="flex justify-end pt-2">
        <button
          type="submit"
          disabled={loading || !to || !subject || !text}
          className="bg-[#00f2ff] hover:bg-[#00d1d1] text-[#05060a] font-semibold py-2 px-6 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Mail className="w-4 h-4" />
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </form>
  );
};
