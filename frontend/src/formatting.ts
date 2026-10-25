const integerCurrency = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

export const formatMoney = (cents: number) => {
  const integerPart = Math.floor(cents / 100)
  const centsPart = cents % 100
  const formattedInteger = integerCurrency.format(integerPart)
  return `${formattedInteger},${centsPart.toString().padStart(2, '0')}`
}
export const formatRate = (bps: number) => `${(bps / 100).toFixed(2).replace('.', ',')}% ao mês`
