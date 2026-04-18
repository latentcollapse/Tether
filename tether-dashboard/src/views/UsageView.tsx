import { LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const mockDailyData = Array.from({ length: 7 }).map((_, i) => ({
  name: i === 6 ? 'Today' : `${6 - i}d ago`,
  sent: Math.floor(Math.random() * 5000) + 1000,
  received: Math.floor(Math.random() * 5000) + 800,
}));

const mockLatencyData = Array.from({ length: 12 }).map((_, i) => {
  const base = 30 + Math.random() * 20;
  return {
    time: `${i * 2}:00`,
    p50: base,
    p95: base + 15 + Math.random() * 10,
    p99: base + 40 + Math.random() * 20,
  };
});

export function UsageView() {
  return (
    <div className="w-full max-w-6xl mx-auto p-6 flex flex-col gap-8 pb-12">
      <div>
        <h1 className="text-2xl font-semibold mb-1">Usage & Metrics</h1>
        <p className="text-[#8892b0] text-sm">Network volume, latency, and tier limits.</p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Messages', value: '4,821', sub: 'today', trend: true },
          { label: 'Agents', value: '3', sub: 'online', trend: true },
          { label: 'Avg Latency', value: '42ms', sub: 'delivery', trend: true },
          { label: 'Tier', value: 'Indie', sub: '84% used', trend: false }
        ].map((stat) => (
          <div key={stat.label} className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl p-6 stat-card-gradient overflow-hidden">
            <div className="text-[12px] uppercase tracking-[1px] text-[#8892b0] mb-2">{stat.label}</div>
            <div className="text-[32px] font-bold text-white leading-tight">{stat.value}</div>
            <div className={`text-[12px] mt-1 ${stat.trend ? 'text-[#00ff88]' : 'text-[#8892b0]'}`}>{stat.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Messages Chart */}
        <div className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-6">Message Volume (7d)</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockDailyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff14" vertical={false} />
                <XAxis dataKey="name" stroke="#8892b0" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#8892b0" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f111a', border: '1px solid #ffffff14', borderRadius: '8px' }}
                  itemStyle={{ color: '#e0e6ed' }}
                />
                <Line type="monotone" dataKey="sent" stroke="#00f2ff" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                <Line type="monotone" dataKey="received" stroke="#7000ff" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-4 mt-4 justify-center text-xs">
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#00f2ff]"></span> Sent</div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#7000ff]"></span> Received</div>
          </div>
        </div>

        {/* Latency Chart */}
        <div className="bg-[#0f111a] border border-[#ffffff14] rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-6">Delivery Latency (24h)</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockLatencyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff14" vertical={false} />
                <XAxis dataKey="time" stroke="#8892b0" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#8892b0" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `${val}ms`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f111a', border: '1px solid #ffffff14', borderRadius: '8px' }}
                />
                <Area type="monotone" dataKey="p99" stackId="1" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} />
                <Area type="monotone" dataKey="p95" stackId="2" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.1} />
                <Area type="monotone" dataKey="p50" stackId="3" stroke="#22c55e" fill="#22c55e" fillOpacity={0.1} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-4 mt-4 justify-center text-xs text-[#8892b0]">
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-[#22c55e]"></span> P50</div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-[#f59e0b]"></span> P95</div>
            <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-[#ef4444]"></span> P99</div>
          </div>
        </div>
      </div>
    </div>
  );
}
