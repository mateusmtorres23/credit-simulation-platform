export type BankScenario = 'normal' | 'slow' | 'unavailable'
export type Bank = 'bank_a' | 'bank_b'

export interface SimulationFormValues {
  name: string
  email: string
  cpf: string
  monthlyIncome: string
  employerCnpj: string
  requestedAmount: string
  termMonths: string
  bankAScenario: BankScenario
  bankBScenario: BankScenario
}

export interface SimulationPayload {
  name: string
  email: string
  cpf: string
  monthly_income_cents: number
  employer_cnpj: string
  requested_amount_cents: number
  term_months: number
}

interface ApprovedResult {
  bank: Bank
  status: 'approved'
  offer: {
    amount_cents: number
    term_months: number
    monthly_interest_rate_bps: number
    installment_cents: number
  }
}

interface RejectedResult {
  bank: Bank
  status: 'rejected'
  reasons: Array<{ code: string; message: string }>
}

interface FailedResult {
  bank: Bank
  status: 'failed'
  error: { code: string; message: string }
}

export type BankResult = ApprovedResult | RejectedResult | FailedResult

export interface SimulationResponse {
  id: string
  created_at: string
  results: [BankResult, BankResult]
}

export interface SimulationSummary {
  id: string
  created_at: string
  requested_amount_cents: number
  term_months: number
  results: [{ bank: Bank; status: BankResult['status'] }, { bank: Bank; status: BankResult['status'] }]
}

export interface SimulationHistoryResponse {
  items: SimulationSummary[]
  total: number
  page: number
  page_size: number
}

export interface SimulationDetailResponse {
  id: string
  created_at: string
  request: {
    monthly_income_cents: number
    requested_amount_cents: number
    term_months: number
  }
  results: [BankResult, BankResult]
}

export interface ApiFieldError {
  field: string
  code: string
  message: string
}

export interface PublicApiError {
  error: {
    code: string
    message: string
    fields?: ApiFieldError[]
  }
}
