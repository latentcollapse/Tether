import { useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Node,
  Edge
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useAgentStore } from '../../store/agentStore';
import { useMessageStore } from '../../store/messageStore';
import { AgentNode } from './AgentNode';
import { MessageEdge } from './MessageEdge';

const nodeTypes = {
  agent: AgentNode,
};

const edgeTypes = {
  message: MessageEdge,
};

export function AgentGraph() {
  const agentsMap = useAgentStore(s => s.agents);
  const feed = useMessageStore(s => s.feed);
  
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Calculate layout simple circle for now
  useEffect(() => {
    const agentList = Object.values(agentsMap);
    if (agentList.length === 0) return;

    const radius = Math.max(150, agentList.length * 40);
    const centerX = 300;
    const centerY = 300;

    const newNodes = agentList.map((agent, i) => {
      const angle = (i / agentList.length) * 2 * Math.PI;
      const node: Node = {
        id: agent.id,
        type: 'agent',
        position: {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        },
        data: agent as unknown as Record<string, unknown>,
      };
      return node;
    });

    setNodes((nds) => {
      // Preserve positions if they already exist
      return newNodes.map(nn => {
        const existing = nds.find(n => n.id === nn.id);
        if (existing) {
          return { ...nn, position: existing.position };
        }
        return nn;
      });
    });
  }, [agentsMap, setNodes]);

  // Derive edges from recent feed
  useEffect(() => {
    // Only care about last 10 seconds of messages to show active links
    const recent = feed.filter(f => Date.now() - new Date(f.timestamp).getTime() < 10000);
    
    const edgeMap = new Map<string, Edge>();
    
    recent.forEach(msg => {
      if (!agentsMap[msg.from] || !agentsMap[msg.to]) return;
      const edgeId = `e-${msg.from}-${msg.to}`;
      edgeMap.set(edgeId, {
        id: edgeId,
        source: msg.from,
        target: msg.to,
        type: 'message',
        animated: true,
      });
    });

    setEdges(Array.from(edgeMap.values()));
  }, [feed, agentsMap, setEdges]);

  return (
    <div className="w-full h-full bg-[#05060a]" style={{ colorScheme: 'dark' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
      >
        <Background gap={16} color="#ffffff14" />
        <Controls showInteractive={false} className="bg-[#0f111a] border-[#ffffff14] fill-[#8892b0]" />
      </ReactFlow>
    </div>
  );
}
