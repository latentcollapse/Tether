import { BaseEdge, EdgeProps, getBezierPath } from '@xyflow/react';
import { memo } from 'react';

function MessageEdgeComponent({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  animated
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge 
        path={edgePath} 
        markerEnd={markerEnd} 
        style={{
          ...style,
          strokeWidth: 2,
          stroke: '#00f2ff',
          opacity: 0.6,
        }} 
      />
      {animated && (
        <circle r="4" fill="#7000ff" className="animate-[dash_3s_linear_infinite]">
          <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
    </>
  );
}

export const MessageEdge = memo(MessageEdgeComponent);
