import { useMemo } from 'react';
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import type { AnalysisReport, FileAssessment } from './types';

interface ImpactNodeData extends Record<string, unknown> {
  path: string;
  kind: string;
  changed: boolean;
  assessment?: FileAssessment;
}

type ImpactFlowNode = Node<ImpactNodeData, 'impact'>;

const statusText = (data: ImpactNodeData) => {
  if (data.changed) return 'Changed';
  if (data.assessment?.bob_assessment === 'bob_confirmed_impact') return 'Bob confirmed';
  if (data.assessment?.bob_assessment === 'possible_impact') return 'Possible impact';
  return 'Predicted';
};

function ImpactNode({ data }: NodeProps<ImpactFlowNode>) {
  const badgeClass = data.changed
    ? 'changed'
    : data.assessment?.bob_assessment === 'bob_confirmed_impact'
      ? 'confirmed'
      : data.assessment?.bob_assessment === 'possible_impact'
        ? 'possible'
        : 'predicted';

  return (
    <div className={`impact-node ${badgeClass}`} title={data.path}>
      <div className="impact-node-topline">
        <span className="node-kind">{data.kind}</span>
        <span className={`node-status ${badgeClass}`}>{statusText(data)}</span>
      </div>
      <strong>{data.path.split('/').at(-1)}</strong>
      <span className="node-path">{data.path}</span>
      <span className="node-port-label">impact travels →</span>
      <Handle type="target" position={Position.Left} isConnectable={false} className="node-handle" />
      <Handle type="source" position={Position.Right} isConnectable={false} className="node-handle" />
    </div>
  );
}

const nodeTypes = { impact: ImpactNode };

function calculateDepths(report: AnalysisReport): Map<string, number> {
  const impacted = new Set(report.predicted_impact.files);
  const downstream = new Map<string, Set<string>>();
  for (const edge of report.dependency_edges) {
    if (!impacted.has(edge.source) || !impacted.has(edge.target)) continue;
    const dependents = downstream.get(edge.target) ?? new Set<string>();
    dependents.add(edge.source);
    downstream.set(edge.target, dependents);
  }

  const depths = new Map<string, number>();
  const queue: string[] = [];
  for (const changed of report.changed_files) {
    if (!impacted.has(changed)) continue;
    depths.set(changed, 0);
    queue.push(changed);
  }
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const dependent of downstream.get(current) ?? []) {
      if (depths.has(dependent)) continue;
      depths.set(dependent, (depths.get(current) ?? 0) + 1);
      queue.push(dependent);
    }
  }
  for (const file of impacted) {
    if (!depths.has(file)) depths.set(file, 0);
  }
  return depths;
}

function fileKind(path: string, report: AnalysisReport): string {
  if (report.predicted_impact.tests.includes(path)) return 'Test';
  if (report.predicted_impact.api_files.includes(path)) return 'API';
  const parts = path.split('/');
  return parts.at(-2)?.replaceAll('_', ' ') ?? 'Source';
}

export function ImpactGraph({ report }: { report: AnalysisReport }) {
  const { nodes, edges } = useMemo(() => {
    const depths = calculateDepths(report);
    const columns = new Map<number, string[]>();
    for (const [path, depth] of depths) {
      const column = columns.get(depth) ?? [];
      column.push(path);
      columns.set(depth, column);
    }
    for (const paths of columns.values()) paths.sort();

    const nextNodes: ImpactFlowNode[] = [...depths.entries()].map(([path, depth]) => {
      const row = columns.get(depth)?.indexOf(path) ?? 0;
      const assessment = report.bob_review?.file_assessments[path];
      return {
        id: path,
        type: 'impact',
        position: { x: depth * 300 + 30, y: row * 140 + 38 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: {
          path,
          kind: fileKind(path, report),
          changed: report.changed_files.includes(path),
          assessment,
        },
      };
    });

    const knownEdges = new Set<string>();
    const nextEdges: Edge[] = report.dependency_edges.flatMap((dependency) => {
      if (!depths.has(dependency.source) || !depths.has(dependency.target)) return [];
      const id = `${dependency.target}->${dependency.source}`;
      if (knownEdges.has(id)) return [];
      knownEdges.add(id);
      return [{
        id,
        source: dependency.target,
        target: dependency.source,
        type: 'smoothstep',
        markerEnd: { type: MarkerType.ArrowClosed, color: '#8391aa' },
        style: { stroke: '#aab4c5', strokeWidth: 1.7 },
      }];
    });
    return { nodes: nextNodes, edges: nextEdges };
  }, [report]);

  return (
    <div className="impact-graph">
      <div className="graph-flow-caption">
        <span className="caption-dot" />
        Change dependency flow
        <span className="caption-spacer" />
        <span className="graph-hint">Drag to explore · scroll to zoom</span>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.24, minZoom: 0.35, maxZoom: 1 }}
        minZoom={0.25}
        maxZoom={1.4}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: false }}
      >
        <Background color="#dbe2ed" gap={20} size={1.25} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) => {
            const data = node.data as ImpactNodeData;
            if (data.changed) return '#df8342';
            if (data.assessment?.bob_assessment === 'bob_confirmed_impact') return '#40a883';
            if (data.assessment?.bob_assessment === 'possible_impact') return '#d39b3e';
            return '#7588aa';
          }}
          maskColor="rgba(248, 250, 253, 0.74)"
          className="graph-minimap"
        />
        <Controls showInteractive={false} position="bottom-left" />
      </ReactFlow>
    </div>
  );
}
