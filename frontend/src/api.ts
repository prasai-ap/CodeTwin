import type { Analysis } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')
export const apiConfigured = Boolean(apiBaseUrl)

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!apiBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not configured for this frontend build.')
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new Error('Could not reach the CodeTwin API. Check the configured API origin and service health.')
  }

  const payload = await response.json().catch(() => ({})) as { detail?: string }
  if (!response.ok) {
    throw new Error(payload.detail || `CodeTwin API returned HTTP ${response.status}.`)
  }
  return payload as T
}

export const api = {
  startPaymentDemo: () => request<Analysis>('/demo/payment-regression', { method: 'POST' }),
  getAnalysis: (analysisId: string) => request<Analysis>(`/analyses/${encodeURIComponent(analysisId)}`),
  applyPaymentFix: (analysisId: string) => request<Analysis>(`/analyses/${encodeURIComponent(analysisId)}/demo-fix`, { method: 'POST' }),
  runTargetedTests: (analysisId: string) => request<Analysis>(`/analyses/${encodeURIComponent(analysisId)}/run-tests`, { method: 'POST' }),
}
