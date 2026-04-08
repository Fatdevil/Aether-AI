/**
 * Format an ISO date string as a relative "time ago" string in Swedish.
 */
export function timeAgo(isoDate: string | undefined): string {
  if (!isoDate) return '';
  const diff = Date.now() - new Date(isoDate).getTime();
  if (diff < 0) return 'just nu';
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'just nu';
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins} min sedan`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h sedan`;
  const days = Math.floor(hours / 24);
  return `${days}d sedan`;
}

/**
 * Format full provider string to a short, readable model name.
 * e.g. "openrouter/anthropic/claude-opus-4.6" → "Claude Opus 4.6"
 * e.g. "openrouter/deepseek/deepseek-chat" → "DeepSeek V3"
 * e.g. "rule_based" → "Regel"
 */
export function formatProvider(provider: string | undefined): string {
  if (!provider) return '';
  const p = provider.toLowerCase();
  if (p.includes('claude-opus-4.6')) return 'Claude Opus 4.6';
  if (p.includes('claude-sonnet-4.6')) return 'Claude Sonnet 4.6';
  if (p.includes('claude-opus')) return 'Claude Opus';
  if (p.includes('claude-sonnet')) return 'Claude Sonnet';
  if (p.includes('claude-3.7')) return 'Claude 3.7';
  if (p.includes('claude')) return 'Claude';
  if (p.includes('deepseek')) return 'DeepSeek V3';
  if (p.includes('gemini-2.0-flash')) return 'Gemini Flash';
  if (p.includes('gemini')) return 'Gemini';
  if (p.includes('gpt-4')) return 'GPT-4';
  if (p.includes('gpt-3')) return 'GPT-3.5';
  if (p === 'rule_based' || p === 'rule-based') return 'Regel';
  if (p.includes('marketaux')) return 'MarketAux';
  if (p.includes('error')) return 'Fel';
  // Fallback: return last segment cleaned up
  const parts = p.split('/');
  return parts[parts.length - 1].replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Format an ISO date to HH:mm Swedish time.
 */
export function formatTime(isoDate: string | undefined): string {
  if (!isoDate) return '';
  const d = new Date(isoDate);
  return d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
}
