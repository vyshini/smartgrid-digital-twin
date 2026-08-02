export function formatMw(value: number | null | undefined): string {
  if (value == null) {
    return '—';
  }
  return `${Math.round(value).toLocaleString('en-IN')} MW`;
}

export function formatPct(value: number | null | undefined): string {
  if (value == null) {
    return '—';
  }
  return `${value.toFixed(1)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) {
    return '—';
  }
  return value.toLocaleString('en-IN');
}
