import { LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useSubscriptionStore } from '../store/subscriptionStore';
import { getTierUsageSnapshot, getUpgradeTarget, isNearLimit } from '../utils/subscription';

const mockDailyData = [
  { name: '6d ago', sent: 1800, received: 1400 },
  { name: '5d ago', sent: 2100, received: 1700 },
  { name: '4d ago', sent: 2600, received: 1900 },
  { name: '3d ago', sent: 3100, received: 2400 },
  { name: '2d ago', sent: 3700, received: 2800 },
  { name: '1d ago', sent: 4200, received: 3200 },
  { name: 'Today', sent: 4821, received: 3610 },
];

const mockLatencyData = [
  { time: '0:00', p50: 32, p95: 48, p99: 73 },
  { time: '2:00', p50: 30, p95: 46, p99: 68 },
  { time: '4:00', p50: 34, p95: 52, p99: 77 },
  { time: '6:00', p50: 36, p95: 54, p99: 82 },
  { time: '8:00', p50: 40, p95: 58, p99: 88 },
  { time: '10:00', p50: 42, p95: 61, p99: 91 },
  { time: '12:00', p50: 39, p95: 56, p99: 84 },
  { time: '14:00', p50: 41, p95: 60, p99: 89 },
  { time: '16:00', p50: 38, p95: 55, p99: 83 },
  { time: '18:00', p50: 35, p95: 53, p99: 79 },
  { time: '20:00', p50: 33, p95: 50, p99: 75 },
  { time: '22:00', p50: 31, p95: 47, p99: 71 },
];

export function UsageView() {
  const currentTier = useSubscriptionStore((state) => state.currentTier);
  const openUpgradeModal = useSubscriptionStore((state) => state.openUpgradeModal);
  const usage = getTierUsageSnapshot(currentTier);
  const upgradeTarget = getUpgradeTarget(currentTier);
  const showNearLimitBanner = currentTier !== 'Free' && isNearLimit(usage) && upgradeTarget;

  return (
    <div className="w-full max-w-6xl mx-auto p-6 flex flex-col gap-8 pb-12">
      <div>
        <h1 className="text-2xl font-semibold mb-1">Usage & Metrics</h1>
        <p className="text-[#8892b0] text-sm">Network volume, latency, and tier limits.</p>
      </div>

      {showNearLimitBanner ? (
        <div className="flex flex-col gap-3 rounded-xl border border-[#00f2ff]/25 bg-[#00f2ff]/8 p-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-white">
              You&apos;re at {usage.agentsRegistered}/{usage.agentsLimit} nodes. Upgrade to {upgradeTarget.tier} for {upgradeTarget.nodes} nodes.
            </div>
            <div className="mt-1 text-sm text-[#b8c2d6]">
              Current tier usage is near its cap. Move up before new nodes or message spikes get throttled.
            </div>
          </div>
          <button
            type="button"
            onClick={openUpgradeModal}
            className="inline-flex items-center justify-center rounded-lg bg-[#00f2ff] px-4 py-2 text-sm font-semibold text-[#05060a] transition-colors hover:bg-[#6cf7ff]"
          >
            Upgrade
          </button>
        </div>
      ) : null}

      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: 'Messages', value: usage.messagesUsedToday.toLocaleString(), sub: `${usage.messageLimitToday.toLocaleString()} daily cap`, trend: true },
          { label: 'Agents', value: usage.agentsRegistered.toString(), sub: `${usage.agentsLimit} registered`, trend: true },
          { label: 'Avg Latency', value: '42ms', sub: 'delivery', trend: true },
          { label: 'Tier', value: currentTier, sub: currentTier === 'Free' ? 'upgrade available' : 'managed in Stripe', trend: false }
        ].map((stat) => (
          <div key={stat.label} className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl p-6 stat-card-gradient overflow-hidden">
            <div className="text-[12px] uppercase tracking-[1px] text-[#8892b0] mb-2">{stat.label}</div>
            <div className="text-[32px] font-bold text-white leading-tight">{stat.value}</div>
            <div className={`text-[12px] mt-1 ${stat.trend ? 'text-[#00ff88]' : 'text-[#8892b0]'}`}>{stat.sub}</div>
          </div>
        ))}
      </div>

      {currentTier === 'Free' ? (
        <div className="rounded-xl border border-[#ffffff14] bg-[#0f111a] p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="text-base font-semibold text-white">Need more than a local node?</div>
              <div className="mt-1 text-sm text-[#8892b0]">
                Move to Duo for direct encrypted machine-to-machine links, or Basic for hosted relay delivery.
              </div>
            </div>
            <button
              type="button"
              onClick={openUpgradeModal}
              className="inline-flex items-center justify-center rounded-lg border border-[#00f2ff]/30 bg-[#00f2ff]/10 px-4 py-2 text-sm font-semibold text-[#8ffcff] transition-colors hover:bg-[#00f2ff]/15"
            >
              Upgrade
            </button>
          </div>
        </div>
      ) : null}

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
