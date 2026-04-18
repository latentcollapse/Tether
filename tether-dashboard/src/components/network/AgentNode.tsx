import { Handle, Position, NodeProps } from '@xyflow/react';
import { Agent } from '../../types/agent';
import { Badge } from '../shared/Badge';
import { memo } from 'react';

function AgentNodeComponent({ data }: NodeProps) {
  const agentData = data as unknown as Agent;
  return (
    <div className="bg-[#0f111a] border border-[#ffffff14] rounded-2xl shadow-lg min-w-[180px] p-4 transition-colors hover:border-[#00f2ff] group relative cursor-pointer stat-card-gradient overflow-hidden">
      <Handle type="target" position={Position.Top} className="opacity-0 group-hover:opacity-100 transition-opacity !bg-[#00f2ff] !w-3 !h-3" />
      
      <div className="flex items-center gap-3 mb-3">
        {agentData.isAdmin ? (
          <div className="w-5 h-5 bg-[#7000ff]/20 text-[#7000ff] rounded flex items-center justify-center font-bold text-[10px] leading-none border border-[#7000ff]/30 shadow-[0_0_8px_rgba(112,0,255,0.4)]" title="Senior Node / Admin">
            <span className="mb-[1.5px] ml-[0.5px]">★</span>
          </div>
        ) : (
          <Badge status={agentData.status} pulse={agentData.status === 'online'} />
        )}
        <div className="font-semibold text-[15px] text-white truncate" title={agentData.name}>
          {agentData.name}
        </div>
      </div>
      
      <div className="text-xs font-mono text-[#7000ff] truncate mb-3" title={agentData.id}>
        {agentData.id}
      </div>
      
      <div className="flex justify-between items-end text-xs text-[#8892b0]">
        <div>{agentData.messagesSentToday + agentData.messagesReceivedToday} msgs today</div>
      </div>

      <Handle type="source" position={Position.Bottom} className="opacity-0 group-hover:opacity-100 transition-opacity !bg-[#00f2ff] !w-3 !h-3" />
    </div>
  );
}

export const AgentNode = memo(AgentNodeComponent);
