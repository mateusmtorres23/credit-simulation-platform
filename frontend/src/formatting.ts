const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export const formatMoney = (cents: number) => currency.format(cents / 100)
export const formatRate = (bps: number) => `${(bps / 100).toFixed(2).replace('.', ',')}% ao mês`
