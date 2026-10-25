import type { BankResult } from '../types'

const bankNames = { bank_a: 'Banco A', bank_b: 'Banco B' }
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const formatMoney = (cents: number) => currency.format(cents / 100)
const formatRate = (bps: number) => `${(bps / 100).toFixed(2).replace('.', ',')}% ao mês`

export function BankResultCard({ result }: { result: BankResult }) {
  if (result.status === 'approved') {
    return (
      <article className="result-card approved">
        <ResultHeader bank={result.bank} label="Aprovado" icon="✓" />
        <dl className="offer-details">
          <div><dt>Valor aprovado</dt><dd>{formatMoney(result.offer.amount_cents)}</dd></div>
          <div><dt>Parcela mensal</dt><dd>{formatMoney(result.offer.installment_cents)}</dd></div>
          <div><dt>Prazo</dt><dd>{result.offer.term_months} meses</dd></div>
          <div><dt>Taxa mensal</dt><dd>{formatRate(result.offer.monthly_interest_rate_bps)}</dd></div>
        </dl>
      </article>
    )
  }
  if (result.status === 'rejected') {
    return (
      <article className="result-card rejected">
        <ResultHeader bank={result.bank} label="Crédito não aprovado" icon="!" />
        <p className="result-description">A instituição não aprovou esta solicitação pelos seguintes motivos:</p>
        <ul className="reason-list">
          {result.reasons.map((reason) => <li key={reason.code}>{reason.message}</li>)}
        </ul>
      </article>
    )
  }
  return (
    <article className="result-card failed">
      <ResultHeader bank={result.bank} label="Falha técnica" icon="×" />
      <p className="result-description">{result.error.message || 'Não foi possível obter uma avaliação desta instituição.'}</p>
      <p className="technical-note">Isso não representa uma reprovação de crédito.</p>
    </article>
  )
}

function ResultHeader({ bank, label, icon }: { bank: 'bank_a' | 'bank_b'; label: string; icon: string }) {
  return (
    <header className="result-header">
      <div className="bank-icon" aria-hidden="true">{icon}</div>
      <div><h3>{bankNames[bank]}</h3><p>{label}</p></div>
    </header>
  )
}
