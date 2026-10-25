export const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER

const brazilianMoneyPattern = /^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/

export function moneyToCents(value: string): number | null {
  const normalized = value.trim()
  if (!normalized || /\s/.test(normalized) || !brazilianMoneyPattern.test(normalized)) {
    return null
  }

  const commaIndex = normalized.lastIndexOf(',')
  const integerPart = commaIndex >= 0 ? normalized.slice(0, commaIndex) : normalized
  const decimalPart = commaIndex >= 0 ? normalized.slice(commaIndex + 1) : ''
  const integerDigits = integerPart.replace(/\./g, '')
  const centsText = `${integerDigits}${decimalPart.padEnd(2, '0')}`

  if (centsText.length > 16) return null
  const cents = Number(centsText)
  return Number.isSafeInteger(cents) && cents <= MAX_SAFE_INTEGER ? cents : null
}
