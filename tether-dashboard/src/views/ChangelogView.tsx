import React, { useState, useEffect } from 'react';
import { History, Search, Calendar, User, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../api/client';
import { CopyButton } from '../components/shared/CopyButton';
import { timeAgo } from '../utils/formatters';

type Category = 'B' | 'F' | 'D' | 'G' | 'M' | 'R' | 'S';
type Tier = 'blue' | 'yellow' | 'orange' | 'red' | 'purple';

interface ChangelogEntry {
  id: string;
  category: Category;
  tier: Tier;
  title: string;
  description: string;
  work_done: string;
  handle: string;
  summary: string;
  completed_by: string;
  completed_at: string;
}

export function ChangelogView() {
  const [changelog, setChangelog] = useState<ChangelogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  const fetchChangelog = () => {
    setLoading(true);
    api.getChangelog(searchQuery)
      .then(res => {
        setChangelog(res.changelog as ChangelogEntry[]);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchChangelog();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const getTierColor = (tier: Tier) => {
    const colors = {
      blue: '#3b82f6',
      yellow: '#eab308',
      orange: '#f97316',
      red: '#ef4444',
      purple: '#a855f7'
    };
    return colors[tier] || '#3b82f6';
  };

  const getCategoryName = (cat: Category) => {
    const names = {
      B: 'Build',
      F: 'Fix',
      D: 'Debt',
      G: 'Gate',
      M: 'Migration',
      R: 'Research',
      S: 'Standing Order'
    };
    return names[cat] || cat;
  };

  const getCategoryBadgeClass = (cat: Category) => {
    const classes = {
      B: 'bg-[#3b82f6]/10 text-[#3b82f6] border-[#3b82f6]/20',
      F: 'bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/20',
      D: 'bg-[#eab308]/10 text-[#eab308] border-[#eab308]/20',
      G: 'bg-[#10b981]/10 text-[#10b981] border-[#10b981]/20',
      M: 'bg-[#a855f7]/10 text-[#a855f7] border-[#a855f7]/20',
      R: 'bg-[#f97316]/10 text-[#f97316] border-[#f97316]/20',
      S: 'bg-[#10b981]/10 text-[#10b981] border-[#10b981]/20'
    };
    return classes[cat] || 'bg-gray-500/10 text-gray-500 border-gray-500/20';
  };

  const filteredChangelog = changelog.filter(entry => {
    if (filterCategory && entry.category !== filterCategory) return false;
    return true;
  });

  return (
    <div className="w-full max-w-5xl mx-auto p-6 pb-12 flex flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2 mb-2">
          <History className="w-6 h-6 text-[#00f2ff]" />
          Changelog
        </h1>
        <p className="text-[#8892b0] text-sm">Historical archive of completed tickets and verified work artifacts.</p>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex flex-col md:flex-row gap-4 items-center">
        {/* Search */}
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8892b0]" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search completed tickets by ID, title, or description..."
            className="w-full bg-[#0f111a] border border-[#ffffff14] focus:border-[#00f2ff] rounded-xl pl-10 pr-4 py-2 text-sm outline-none transition-colors placeholder:text-[#8892b0] text-[#e0e6ed]"
          />
        </div>

        {/* Category Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          <button
            onClick={() => setFilterCategory('')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer whitespace-nowrap ${
              filterCategory === ''
                ? 'bg-[#00f2ff]/10 text-[#00f2ff] border-[#00f2ff]/20 shadow-[0_0_10px_rgba(0,242,255,0.05)]'
                : 'bg-[#0f111a] text-[#8892b0] border-[#ffffff14] hover:border-[#ffffff20]'
            }`}
          >
            All Categories
          </button>
          {(['B', 'F', 'D', 'G', 'M', 'R', 'S'] as Category[]).map(cat => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer whitespace-nowrap ${
                filterCategory === cat
                  ? 'bg-[#00f2ff]/10 text-[#00f2ff] border-[#00f2ff]/20'
                  : 'bg-[#0f111a] text-[#8892b0] border-[#ffffff14] hover:border-[#ffffff20]'
              }`}
            >
              {getCategoryName(cat)}
            </button>
          ))}
        </div>
      </div>

      {/* Main List */}
      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-[#00f2ff] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filteredChangelog.length === 0 ? (
        <div className="h-48 flex flex-col items-center justify-center border border-[#ffffff14] border-dashed rounded-2xl text-[#8892b0] text-sm gap-2">
          <span>No completed tickets found matching filters.</span>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {filteredChangelog.map(entry => {
            const isExpanded = !!expandedIds[entry.id];
            return (
              <div
                key={entry.id}
                className="bg-[#0f111a] border border-[#ffffff14] hover:border-[#ffffff20] rounded-2xl overflow-hidden transition-all shadow-lg"
              >
                {/* Entry Header/Trigger */}
                <div
                  onClick={() => toggleExpand(entry.id)}
                  className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer select-none"
                >
                  <div className="flex flex-col gap-2 min-w-0">
                    <div className="flex items-center flex-wrap gap-2.5">
                      <span className="font-mono font-bold text-[#00f2ff] text-sm">{entry.id}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-md border font-semibold uppercase ${getCategoryBadgeClass(entry.category)}`}>
                        {getCategoryName(entry.category)}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded border uppercase font-medium" style={{ color: getTierColor(entry.tier), borderColor: `${getTierColor(entry.tier)}30`, backgroundColor: `${getTierColor(entry.tier)}08` }}>
                        {entry.tier}
                      </span>
                    </div>
                    <h3 className="text-white font-semibold text-base truncate">{entry.title}</h3>
                  </div>

                  <div className="flex items-center justify-between md:justify-end gap-6 shrink-0">
                    <div className="flex flex-col items-end text-right text-xs text-[#8892b0] gap-1">
                      <div className="flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5" />
                        <span>@{entry.completed_by}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>{timeAgo(entry.completed_at)}</span>
                      </div>
                    </div>
                    <div>
                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-[#8892b0]" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-[#8892b0]" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Entry Content (Expanded) */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-[#ffffff08] bg-[#05060a]/40 flex flex-col gap-4 text-sm">
                    {/* Handle Info */}
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 bg-[#0a0c14] border border-[#ffffff08] rounded-xl font-mono text-xs mt-4">
                      <div className="flex items-center gap-2">
                        <span className="text-[#8892b0]">Handle:</span>
                        <span className="text-[#7000ff] truncate max-w-[200px] md:max-w-md">{entry.handle}</span>
                      </div>
                      <CopyButton text={entry.handle} />
                    </div>

                    {/* Description */}
                    {entry.description && (
                      <div className="flex flex-col gap-1.5 mt-2">
                        <h4 className="text-xs font-semibold text-[#8892b0] uppercase tracking-wider">Ticket Description</h4>
                        <p className="text-[#e0e6ed] leading-relaxed whitespace-pre-wrap bg-[#0f111a]/40 p-3 rounded-xl border border-[#ffffff08]">{entry.description}</p>
                      </div>
                    )}

                    {/* Work Done */}
                    {entry.work_done && (
                      <div className="flex flex-col gap-2 p-4 bg-[#0a1c12]/30 border border-[#10b981]/10 rounded-xl">
                        <h4 className="text-xs font-semibold text-[#00ff88] uppercase tracking-wider flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 bg-[#00ff88] rounded-full shadow-[0_0_6px_#00ff88]" />
                          Work Done / Verification
                        </h4>
                        <p className="text-[#e0e6ed] leading-relaxed whitespace-pre-wrap">{entry.work_done}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
