import { useState, type FormEvent } from 'react'
import { ApiRequestError } from '../api'
import type { ApiFieldError, BankScenario, SimulationFormValues } from '../types'
import { moneyToCents, MAX_SAFE_INTEGER } from '../money'

interface Props {
  isSubmitting: boolean
  operationError: string | null
  onSubmit: (values: SimulationFormValues) => Promise<void>
}

const initialValues: SimulationFormValues = {
  name: '', email: '', cpf: '', monthlyIncome: '', employerCnpj: '',
  requestedAmount: '', termMonths: '', bankAScenario: 'normal', bankBScenario: 'normal',
}

function validate(values: SimulationFormValues): Record<string, string> {
  const errors: Record<string, string> = {}
  const name = values.name.trim()
  const email = values.email.trim()
  if (!name || name.length > 150) errors.name = name ? 'O nome deve ter no máximo 150 caracteres.' : 'Informe seu nome.'
  const at = email.indexOf('@')
  if (!email || email.length > 254 || /\s/.test(email) || at < 1 || at === email.length - 1) errors.email = 'Informe um e-mail válido.'
  if (!/^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$/.test(values.cpf)) errors.cpf = 'Informe um CPF com 11 dígitos.'
  const income = moneyToCents(values.monthlyIncome)
  if (income === null || income < 1) errors.monthlyIncome = 'Informe uma renda válida, em reais.'
  if (!/^\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}$/.test(values.employerCnpj)) errors.employerCnpj = 'Informe um CNPJ com 14 dígitos.'
  const amount = moneyToCents(values.requestedAmount)
  if (amount === null || amount < 100) errors.requestedAmount = 'Informe um valor de pelo menos R$ 1,00.'
  if (amount !== null && amount > MAX_SAFE_INTEGER) errors.requestedAmount = 'O valor excede o limite permitido.'
  const term = Number(values.termMonths)
  if (!/^\d+$/.test(values.termMonths) || !Number.isSafeInteger(term) || term < 1 || term > 120) {
    errors.termMonths = 'Informe um prazo entre 1 e 120 meses.'
  }
  if (income !== null && income > MAX_SAFE_INTEGER) errors.monthlyIncome = 'A renda excede o limite permitido.'
  return errors
}

function inputId(field: string) { return `field-${field}` }

export function SimulationForm({ isSubmitting, operationError, onSubmit }: Props) {
  const [values, setValues] = useState(initialValues)
  const [errors, setErrors] = useState<Record<string, string>>({})

  function update(field: keyof SimulationFormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return
    const nextErrors = validate(values)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      document.getElementById(inputId(Object.keys(nextErrors)[0]))?.focus()
      return
    }
    try {
      await onSubmit(values)
    } catch (error) {
      if (error instanceof ApiRequestError && error.fields.length > 0) {
        applyApiErrors(error.fields)
      }
    }
  }

  function applyApiErrors(fieldErrors: ApiFieldError[]) {
    const mapped = fieldErrors.reduce<Record<string, string>>((result, error) => {
      const field = {
        monthly_income_cents: 'monthlyIncome',
        requested_amount_cents: 'requestedAmount',
        employer_cnpj: 'employerCnpj',
        term_months: 'termMonths',
        name: 'name',
        email: 'email',
        cpf: 'cpf',
      }[error.field] || error.field
      result[field] = error.message
      return result
    }, {})
    setErrors(mapped)
  }

  return (
    <form className="simulation-form" onSubmit={submit} noValidate aria-busy={isSubmitting}>
      {operationError && (
        <div className="operation-error" role="alert">
          <strong>Não foi possível concluir a simulação.</strong>
          <p>{operationError}</p>
        </div>
      )}
      <fieldset>
        <legend>Seus dados</legend>
        <div className="form-grid">
          <Field label="Nome completo" name="name" value={values.name} error={errors.name} onChange={update} autoComplete="name" />
          <Field label="E-mail" name="email" type="email" value={values.email} error={errors.email} onChange={update} autoComplete="email" />
          <Field label="CPF" name="cpf" value={values.cpf} error={errors.cpf} onChange={update} inputMode="numeric" placeholder="000.000.000-00" />
          <Field label="Renda mensal" name="monthlyIncome" value={values.monthlyIncome} error={errors.monthlyIncome} onChange={update} inputMode="decimal" placeholder="R$ 0,00" hint="Valor em reais" />
          <Field label="CNPJ do empregador" name="employerCnpj" value={values.employerCnpj} error={errors.employerCnpj} onChange={update} inputMode="numeric" placeholder="00.000.000/0000-00" />
        </div>
      </fieldset>
      <fieldset>
        <legend>Dados do empréstimo</legend>
        <div className="form-grid loan-grid">
          <Field label="Valor solicitado" name="requestedAmount" value={values.requestedAmount} error={errors.requestedAmount} onChange={update} inputMode="decimal" placeholder="R$ 0,00" hint="Mínimo de R$ 1,00" />
          <Field label="Prazo" name="termMonths" value={values.termMonths} error={errors.termMonths} onChange={update} inputMode="numeric" placeholder="Ex.: 24" hint="De 1 a 120 meses" />
        </div>
      </fieldset>
      <details className="scenarios">
        <summary>Cenários de demonstração</summary>
        <p>Escolha como cada instituição responderá nesta solicitação.</p>
        <div className="scenario-grid">
          <ScenarioSelect bank="A" value={values.bankAScenario} onChange={(value) => update('bankAScenario', value)} />
          <ScenarioSelect bank="B" value={values.bankBScenario} onChange={(value) => update('bankBScenario', value)} />
        </div>
      </details>
      <p className="form-footnote">Ao continuar, você concorda com o envio destes dados fictícios para a simulação.</p>
      <button className="submit-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Enviando...' : 'Simular empréstimo'}
      </button>
    </form>
  )
}

interface FieldProps {
  label: string; name: string; value: string; error?: string; hint?: string; type?: string
  autoComplete?: string; inputMode?: 'text' | 'numeric' | 'decimal'; placeholder?: string
  onChange: (name: keyof SimulationFormValues, value: string) => void
}
function Field({ label, name, value, error, hint, onChange, ...props }: FieldProps) {
  const id = inputId(name)
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} name={name} value={value} onChange={(event) => onChange(name as keyof SimulationFormValues, event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined} {...props} />
      {hint && !error && <span id={`${id}-hint`} className="field-hint">{hint}</span>}
      {error && <span id={`${id}-error`} className="field-error">{error}</span>}
    </div>
  )
}

function ScenarioSelect({ bank, value, onChange }: { bank: 'A' | 'B'; value: BankScenario; onChange: (value: BankScenario) => void }) {
  return (
    <label className="scenario-field">
      <span>Banco {bank}</span>
      <select value={value} onChange={(event) => onChange(event.target.value as BankScenario)}>
        <option value="normal">Resposta normal</option>
        <option value="slow">Resposta lenta</option>
        <option value="unavailable">Indisponível</option>
      </select>
    </label>
  )
}
