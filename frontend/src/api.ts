import type {
  ApiFieldError,
  PublicApiError,
  SimulationFormValues,
  SimulationPayload,
  SimulationResponse,
} from './types'
import { moneyToCents } from './money'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiRequestError extends Error {
  readonly fields: ApiFieldError[]

  constructor(message: string, fields: ApiFieldError[] = []) {
    super(message)
    this.name = 'ApiRequestError'
    this.fields = fields
  }
}

function isPublicApiError(value: unknown): value is PublicApiError {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const error = value.error
  if (typeof error !== 'object' || error === null || !('code' in error) || !('message' in error)) return false
  const candidate = error as { code: unknown; message: unknown; fields?: unknown }
  if (typeof candidate.code !== 'string' || !candidate.code.trim() || typeof candidate.message !== 'string' || !candidate.message.trim()) return false
  if (!('fields' in candidate)) return true
  return Array.isArray(candidate.fields) && candidate.fields.every(isApiFieldError)
}

function isApiFieldError(value: unknown): boolean {
  if (typeof value !== 'object' || value === null || !('field' in value) || !('code' in value) || !('message' in value)) return false
  const field = value as { field: unknown; code: unknown; message: unknown }
  return [field.field, field.code, field.message].every((item) => typeof item === 'string' && item.trim().length > 0)
}

function toPayload(values: SimulationFormValues): SimulationPayload {
  return {
    name: values.name.trim(),
    email: values.email.trim(),
    cpf: values.cpf.replace(/\D/g, ''),
    monthly_income_cents: requireMoney(values.monthlyIncome),
    employer_cnpj: values.employerCnpj.replace(/\D/g, ''),
    requested_amount_cents: requireMoney(values.requestedAmount),
    term_months: Number(values.termMonths),
  }
}

function requireMoney(value: string): number {
  const cents = moneyToCents(value)
  if (cents === null) throw new Error('Informe valores monetários válidos em reais.')
  return cents
}

export async function createSimulation(values: SimulationFormValues): Promise<SimulationResponse> {
  const payload = toPayload(values)
  const query = new URLSearchParams({
    bank_a_scenario: values.bankAScenario,
    bank_b_scenario: values.bankBScenario,
  })
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/api/simulations?${query}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new Error('Não foi possível conectar à API. Verifique se o serviço está disponível.')
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    if (isPublicApiError(body)) {
      throw new ApiRequestError(body.error.message, body.error.fields)
    }
    throw new ApiRequestError('A API não conseguiu concluir a simulação. Revise os dados e tente novamente.')
  }
  if (
    !isPublicApiResponse(body)
  ) {
    throw new Error('A API retornou uma resposta inesperada. Tente novamente.')
  }
  return body
}

function isPublicApiResponse(value: unknown): value is SimulationResponse {
  if (typeof value !== 'object' || value === null || !('id' in value) || !('created_at' in value) || !('results' in value)) return false
  const response = value as { id: unknown; created_at: unknown; results: unknown }
  if (typeof response.id !== 'string' || !response.id.trim() || typeof response.created_at !== 'string' || !response.created_at.trim() || !Array.isArray(response.results) || response.results.length !== 2) return false
  const [first, second] = response.results
  return isBankResult(first, 'bank_a') && isBankResult(second, 'bank_b')
}

function isBankResult(value: unknown, expectedBank: 'bank_a' | 'bank_b'): boolean {
  if (typeof value !== 'object' || value === null || !('bank' in value) || !('status' in value)) return false
  const result = value as { bank: unknown; status: unknown; offer?: unknown; reasons?: unknown; error?: unknown }
  if (result.bank !== expectedBank) return false
  if (result.status === 'approved') {
    if (typeof result.offer !== 'object' || result.offer === null) return false
    const offer = result.offer as Record<string, unknown>
    return isSafeIntegerAtLeast(offer.amount_cents, 1)
      && isSafeIntegerAtLeast(offer.installment_cents, 1)
      && isSafeIntegerAtLeast(offer.term_months, 1) && offer.term_months <= 120
      && isSafeIntegerAtLeast(offer.monthly_interest_rate_bps, 0)
  }
  if (result.status === 'rejected') {
    return Array.isArray(result.reasons) && result.reasons.length > 0 && result.reasons.every((reason) => {
      if (typeof reason !== 'object' || reason === null) return false
      const item = reason as { code?: unknown; message?: unknown }
      return typeof item.code === 'string' && typeof item.message === 'string'
        && item.code.trim().length > 0 && item.message.trim().length > 0
    })
  }
  if (result.status === 'failed') {
    if (typeof result.error !== 'object' || result.error === null) return false
    const error = result.error as { code?: unknown; message?: unknown }
    return typeof error.code === 'string' && error.code.trim().length > 0
      && typeof error.message === 'string' && error.message.trim().length > 0
  }
  return false
}

function isSafeIntegerAtLeast(value: unknown, minimum: number): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum
}
