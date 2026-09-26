import { useMemo } from 'react'
import type { Analysis, ImpactEdge, ImpactNodeStatus } from './types'

type LayoutNode = {
  file: string
  x: number
  y: number
  status: ImpactNodeStatus
  layer: number
}

type LayoutEdge = {
  source: LayoutNode
  target: LayoutNode
  kind: string
}

type Layout = {
  nodes: LayoutNode[]
  edges: LayoutEdge[]
  width: number
  height: number
}

const nodeWidth = 192
const nodeHeight = 64
const columnStep = 222
const rowStep = 88

function fileFromSymbol(symbol: string) {
  return symbol.split('::', 1)[0]
}

function graphLayout(analysis: Analysis): Layout {
  const impacted = new Set(analysis.predicted_impact.files)
  const paths = [...impacted].sort()
  const adjacency = new Map(paths.map((path) => [path, new Set<string>()]))
  const relations = new Map<string, string>()
  const addImpactEdge = (changed: string, downstream: string, kind: string) => {
    if (!impacted.has(changed) || !impacted.has(downstream) || changed === downstream) return
    adjacency.get(changed)?.add(downstream)
    relations.set(`${changed}→${downstream}`, kind)
  }

  for (const edge of analysis.dependency_edges) {
    // The analyzer stores importer → dependency; the graph follows impact in the reverse direction.
    addImpactEdge(edge.target, edge.source, 'import')
  }
  for (const edge of analysis.function_edges) {
    // A changed callee can affect its caller, so reverse caller → callee for impact traversal.
    addImpactEdge(fileFromSymbol(edge.target), fileFromSymbol(edge.source), 'call')
  }

  const distance = new Map<string, number>()
  const queue: string[] = []
  for (const path of analysis.changed_files) {
    if (impacted.has(path)) {
      distance.set(path, 0)
      queue.push(path)
    }
  }
  for (let index = 0; index < queue.length; index += 1) {
    const current = queue[index]
    const nextDistance = (distance.get(current) ?? 0) + 1
    for (const downstream of [...(adjacency.get(current) ?? [])].sort()) {
      if (!distance.has(downstream)) {
        distance.set(downstream, nextDistance)
        queue.push(downstream)
      }
    }
  }
  const groups = new Map<number, string[]>()
  for (const path of paths) {
    const layer = distance.get(path) ?? 1
    groups.set(layer, [...(groups.get(layer) ?? []), path])
  }
  const maxLayer = Math.max(0, ...groups.keys())
  const groupedPaths = [...groups.entries()].sort(([left], [right]) => left - right)
  const bobAssessments = analysis.bob_review?.file_assessments ?? {}
  const nodes: LayoutNode[] = []

  for (const [layer, files] of groupedPaths) {
    files.sort()
    files.forEach((file, row) => {
      const bobStatus = bobAssessments[file]?.bob_assessment
      const status: ImpactNodeStatus = analysis.changed_files.includes(file)
        ? 'changed'
        : bobStatus === 'bob_confirmed_impact'
          ? 'confirmed'
          : bobStatus === 'possible_impact'
            ? 'possible'
            : bobStatus === 'not_affected'
              ? 'not_affected'
              : 'predicted'
      nodes.push({ file, x: 28 + layer * columnStep, y: 38 + row * rowStep, status, layer })
    })
  }

  const nodeByFile = new Map(nodes.map((node) => [node.file, node]))
  const edges: LayoutEdge[] = []
  for (const [key, kind] of relations) {
    const [sourceFile, targetFile] = key.split('→')
    const source = nodeByFile.get(sourceFile)
    const target = nodeByFile.get(targetFile)
    if (source && target) edges.push({ source, target, kind })
  }

  const maxRows = Math.max(1, ...groupedPaths.map(([, files]) => files.length))
  return {
    nodes,
    edges,
    width: Math.max(680, 56 + (maxLayer + 1) * columnStep),
    height: Math.max(342, 88 + maxRows * rowStep),
  }
}

const statusLabel: Record<ImpactNodeStatus, string> = {
  changed: 'Changed',
  predicted: 'Predicted',
  confirmed: 'Bob confirmed',
  possible: 'Possible',
  not_affected: 'Not affected',
}

type Props = {
  analysis: Analysis
  selectedFile: string | null
  onSelectFile: (file: string) => void
}

export default function ImpactGraph({ analysis, selectedFile, onSelectFile }: Props) {
  const layout = useMemo(() => graphLayout(analysis), [analysis])
  const markerId = `arrow-${analysis.analysis_id}`

  return (
    <div className="graph-scroll" aria-label="Scrollable impact graph">
      <svg
        className="impact-graph"
        width={layout.width}
        height={layout.height}
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="group"
        aria-label="File dependency graph with impact flowing from the changed payment service to its dependents"
      >
        <defs>
          <pattern id="graph-grid" width="22" height="22" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="#202a35" />
          </pattern>
          <marker id={markerId} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#4b6270" />
          </marker>
        </defs>
        <rect width={layout.width} height={layout.height} fill="url(#graph-grid)" />

        {layout.edges.map(({ source, target, kind }) => {
          const startX = source.x + nodeWidth
          const startY = source.y + nodeHeight / 2
          const endX = target.x - 8
          const endY = target.y + nodeHeight / 2
          const curve = Math.max(28, (endX - startX) * 0.46)
          return (
            <path
              key={`${source.file}-${target.file}-${kind}`}
              d={`M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX - curve} ${endY}, ${endX} ${endY}`}
              className={`graph-edge graph-edge-${kind}`}
              markerEnd={`url(#${markerId})`}
            />
          )
        })}

        {layout.nodes.map((node) => {
          const parts = node.file.split('/')
          const fileName = parts.pop() ?? node.file
          const folder = parts.slice(-2).join('/') || 'repository root'
          return (
            <g
              key={node.file}
              className={`graph-node graph-node-${node.status}${selectedFile === node.file ? ' is-selected' : ''}`}
              onClick={() => onSelectFile(node.file)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') onSelectFile(node.file)
              }}
              tabIndex={0}
              role="button"
              aria-label={`${node.file}: ${statusLabel[node.status]}`}
            >
              <rect x={node.x} y={node.y} width={nodeWidth} height={nodeHeight} rx="9" />
              <circle cx={node.x + 15} cy={node.y + 17} r="4" />
              <text x={node.x + 26} y={node.y + 21} className="graph-node-folder">{folder}</text>
              <text x={node.x + 13} y={node.y + 43} className="graph-node-file">{fileName}</text>
              <text x={node.x + nodeWidth - 11} y={node.y + 19} className="graph-node-status" textAnchor="end">{statusLabel[node.status]}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export function ImpactLegend({ bobReviewed }: { bobReviewed: boolean }) {
  const items: { status: ImpactNodeStatus; label: string }[] = [
    { status: 'changed', label: 'Changed' },
    { status: 'predicted', label: 'Predicted' },
    ...(bobReviewed ? [
      { status: 'confirmed' as const, label: 'Bob confirmed' },
      { status: 'possible' as const, label: 'Possible' },
      { status: 'not_affected' as const, label: 'Not affected' },
    ] : []),
  ]
  return (
    <div className="graph-legend">
      {items.map(({ status, label }) => <span key={status}><i className={`legend-dot legend-${status}`} />{label}</span>)}
    </div>
  )
}

export function GraphEdgeLegend({ edges }: { edges: ImpactEdge[] }) {
  const counts = edges.reduce((count, edge) => ({ ...count, [edge.kind]: (count[edge.kind] ?? 0) + 1 }), {} as Record<string, number>)
  const relations = [counts.imports ? 'imports' : '', counts.calls ? 'call references' : ''].filter(Boolean).join(' + ')
  return <span className="edge-note">Impact follows {relations || 'source'} downstream · {edges.length} relationships</span>
}
