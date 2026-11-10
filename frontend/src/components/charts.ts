// Shared Recharts styling for the dark theme.
export const PROVIDER_COLORS: Record<string, string> = {
  aws: '#f59e0b',
  azure: '#38bdf8',
  gcp: '#34d399',
};

export const SERIES_COLORS = ['#22d3ee', '#a78bfa', '#f59e0b', '#34d399', '#f472b6', '#60a5fa', '#facc15', '#fb7185'];

export const STATUS_COLORS: Record<string, string> = {
  running: '#34d399',
  available: '#22d3ee',
  stopped: '#f59e0b',
  provisioning: '#60a5fa',
  error: '#fb7185',
  terminated: '#64748b',
  deleted: '#475569',
  unknown: '#94a3b8',
};

export const AXIS_PROPS = {
  stroke: '#6b7799',
  tick: { fill: '#9aa6c4', fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: '#243050' },
} as const;

export const GRID_PROPS = { stroke: '#243050', strokeDasharray: '3 3', vertical: false } as const;

export const TOOLTIP_PROPS = {
  contentStyle: {
    background: '#172036',
    border: '1px solid #243050',
    borderRadius: 8,
    color: '#e7ebf6',
    fontSize: 12,
  },
  labelStyle: { color: '#9aa6c4' },
  itemStyle: { color: '#e7ebf6' },
  cursor: { fill: 'rgba(34,211,238,0.06)' },
} as const;

export const LEGEND_PROPS = { wrapperStyle: { fontSize: 12, color: '#9aa6c4' } } as const;
