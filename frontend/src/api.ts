import { moneyToCents } from './money'
import type {
  ApiFieldError,
  BankResult,
  PublicApiError,
  SimulationDetailResponse,
  SimulationFormValues,
  SimulationHistoryResponse,
  SimulationPayload,
  SimulationSummary,
  SimulationResponse,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiRequestError extends Error {
  readonly code: string | null
  readonly fields: ApiFieldError[]

  constructor(message: string, fields: ApiFieldError[] = [], code: string | null = null) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = code
    this.fields = fields
  }
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
  } catch (error) {
    throw new Error('Não foi possível conectar à API. Verifique se o serviço está disponível.', { cause: error })
  }

  const body = await readJson(response)
  if (!response.ok) throw publicOrGenericError(body, 'A API não conseguiu concluir a simulação. Revise os dados e tente novamente.')
  if (!isPublicApiResponse(body)) throw unexpectedResponse()
  return body
}

export async function listSimulations(page: number, pageSize = 10, signal?: AbortSignal): Promise<SimulationHistoryResponse> {
  const body = await requestJson(`/api/simulations?page=${page}&page_size=${pageSize}`, { method: 'GET', signal })
  if (!isHistoryResponse(body)) throw unexpectedResponse()
  return body
}

export async function getSimulationDetail(id: string, signal?: AbortSignal): Promise<SimulationDetailResponse> {
  const body = await requestJson(`/api/simulations/${encodeURIComponent(id)}`, { method: 'GET', signal })
  if (!isDetailResponse(body)) throw unexpectedResponse()
  return body
}

export async function deleteSimulation(id: string, signal?: AbortSignal): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/api/simulations/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      credentials: 'include',
      signal,
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new Error('Não foi possível conectar à API. Verifique se o serviço está disponível.', { cause: error })
  }
  if (response.status === 204) return
  throw publicOrGenericError(await readJson(response), 'A API não conseguiu excluir a simulação. Tente novamente.')
}

async function requestJson(path: string, init: RequestInit): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, credentials: 'include' })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new Error('Não foi possível conectar à API. Verifique se o serviço está disponível.', { cause: error })
  }
  const body = await readJson(response)
  if (!response.ok) throw publicOrGenericError(body, 'A API não conseguiu consultar o histórico. Tente novamente.')
  return body
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

async function readJson(response: Response): Promise<unknown> {
  return response.json().catch(() => null)
}

function publicOrGenericError(body: unknown, fallback: string): ApiRequestError {
  if (isPublicApiError(body)) return new ApiRequestError(body.error.message, body.error.fields, body.error.code)
  return new ApiRequestError(fallback)
}

function isPublicApiError(value: unknown): value is PublicApiError {
  if (!isRecord(value) || !isRecord(value.error) || typeof value.error.code !== 'string'
    || !value.error.code.trim() || typeof value.error.message !== 'string' || !value.error.message.trim()) return false
  if (!('fields' in value.error)) return true
  return Array.isArray(value.error.fields) && value.error.fields.every(isApiFieldError)
}

function isApiFieldError(value: unknown): value is ApiFieldError {
  if (!isRecord(value) || typeof value.field !== 'string' || typeof value.code !== 'string' || typeof value.message !== 'string') return false
  return Boolean(value.field.trim() && value.code.trim() && value.message.trim())
}

function isPublicApiResponse(value: unknown): value is SimulationResponse {
  if (!isRecord(value) || !hasIdentity(value) || !Array.isArray(value.results) || value.results.length !== 2) return false
  const [first, second] = value.results
  return isBankResult(first, 'bank_a') && isBankResult(second, 'bank_b')
}

function isHistoryResponse(value: unknown): value is SimulationHistoryResponse {
  if (!isRecord(value) || !Array.isArray(value.items) || !isSafeIntegerAtLeast(value.total, 0)
    || !isSafeIntegerAtLeast(value.page, 1) || !isSafeIntegerAtLeast(value.page_size, 1)) return false
  return value.items.every(isSimulationSummary)
}

function isSimulationSummary(value: unknown): value is SimulationSummary {
  if (!isRecord(value) || !hasIdentity(value) || !isSafeIntegerAtLeast(value.requested_amount_cents, 100)
    || !isSafeIntegerAtLeast(value.term_months, 1) || value.term_months > 120) return false
  return isSummaryPair(value.results)
}

function isDetailResponse(value: unknown): value is SimulationDetailResponse {
  if (!isRecord(value) || !hasIdentity(value) || !isRecord(value.request)
    || !isSafeIntegerAtLeast(value.request.monthly_income_cents, 1)
    || !isSafeIntegerAtLeast(value.request.requested_amount_cents, 100)
    || !isSafeIntegerAtLeast(value.request.term_months, 1) || value.request.term_months > 120) return false
  return isBankResultPair(value.results)
}

function hasIdentity(value: Record<string, unknown>): boolean {
  return typeof value.id === 'string' && Boolean(value.id.trim())
    && typeof value.created_at === 'string' && Boolean(value.created_at.trim())
}

function isSummaryPair(value: unknown): value is SimulationSummary['results'] {
  if (!Array.isArray(value) || value.length !== 2) return false
  return isSummaryResult(value[0], 'bank_a') && isSummaryResult(value[1], 'bank_b')
}

function isSummaryResult(value: unknown, bank: 'bank_a' | 'bank_b'): boolean {
  return isRecord(value) && value.bank === bank
    && (value.status === 'approved' || value.status === 'rejected' || value.status === 'failed')
}

function isBankResultPair(value: unknown): value is [BankResult, BankResult] {
  if (!Array.isArray(value) || value.length !== 2) return false
  return isBankResult(value[0], 'bank_a') && isBankResult(value[1], 'bank_b')
}

function isBankResult(value: unknown, expectedBank: 'bank_a' | 'bank_b'): value is BankResult {
  if (!isRecord(value) || value.bank !== expectedBank || typeof value.status !== 'string') return false
  if (value.status === 'approved') {
    if (!isRecord(value.offer)) return false
    return isSafeIntegerAtLeast(value.offer.amount_cents, 1)
      && isSafeIntegerAtLeast(value.offer.installment_cents, 1)
      && isSafeIntegerAtLeast(value.offer.term_months, 1) && value.offer.term_months <= 120
      && isSafeIntegerAtLeast(value.offer.monthly_interest_rate_bps, 0)
  }
  if (value.status === 'rejected') {
    return Array.isArray(value.reasons) && value.reasons.length > 0 && value.reasons.every((reason) => {
      return isRecord(reason) && typeof reason.code === 'string' && Boolean(reason.code.trim())
        && typeof reason.message === 'string' && Boolean(reason.message.trim())
    })
  }
  if (value.status === 'failed') {
    return isRecord(value.error) && typeof value.error.code === 'string' && Boolean(value.error.code.trim())
      && typeof value.error.message === 'string' && Boolean(value.error.message.trim())
  }
  return false
}

function isSafeIntegerAtLeast(value: unknown, minimum: number): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function unexpectedResponse(): Error {
  return new Error('A API retornou uma resposta inesperada. Tente novamente.')
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}
