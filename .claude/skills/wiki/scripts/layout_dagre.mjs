#!/usr/bin/env node
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
let dagre;
try {
  dagre = require('dagre');
} catch (err) {
  const skillRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
  dagre = createRequire(path.join(skillRoot, 'package.json'))('dagre');
}

function parseArgs(argv) {
  const args = { input: null, output: null };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--input') args.input = argv[++i];
    else if (a === '--output') args.output = argv[++i];
    else if (a === '--help' || a === '-h') {
      console.log('usage: layout_dagre.mjs --input request.json --output layout.json');
      process.exit(0);
    }
  }
  if (!args.input || !args.output) {
    console.error('layout_dagre.mjs requires --input and --output');
    process.exit(2);
  }
  return args;
}

const args = parseArgs(process.argv);
const req = JSON.parse(fs.readFileSync(args.input, 'utf8'));

const g = new dagre.graphlib.Graph({ multigraph: true });
g.setGraph({
  rankdir: req.direction || 'LR',
  ranksep: req.ranksep ?? 130,
  nodesep: req.nodesep ?? 70,
  edgesep: req.edgesep ?? 20,
  marginx: req.marginx ?? 20,
  marginy: req.marginy ?? 20,
  acyclicer: req.acyclicer || 'greedy',
  ranker: req.ranker || 'network-simplex',
});
g.setDefaultEdgeLabel(() => ({}));

for (const n of req.nodes || []) {
  g.setNode(n.id, {
    label: n.label ?? n.id,
    width: n.width ?? 180,
    height: n.height ?? 70,
  });
}

let edgeIndex = 0;
for (const e of req.edges || []) {
  const name = e.id ?? `e${edgeIndex++}`;
  g.setEdge(e.source, e.target, { weight: e.weight ?? 1, label: e.label ?? '' }, name);
}

dagre.layout(g);

const nodes = {};
for (const id of g.nodes()) {
  const n = g.node(id);
  nodes[id] = { x: n.x, y: n.y, width: n.width, height: n.height };
}

const edges = [];
for (const edgeObj of g.edges()) {
  const e = g.edge(edgeObj);
  edges.push({
    source: edgeObj.v,
    target: edgeObj.w,
    name: edgeObj.name,
    points: (e.points || []).map(p => ({ x: p.x, y: p.y })),
    label: e.label ?? '',
  });
}

const out = {
  width: g.graph().width,
  height: g.graph().height,
  nodes,
  edges,
};
fs.writeFileSync(args.output, JSON.stringify(out, null, 2) + '\n');
