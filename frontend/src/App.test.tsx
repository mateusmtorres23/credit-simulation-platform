import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const approved = (bank: 'bank_a' | 'bank_b') => ({
  bank, status: 'approved', offer: {
    amount_cents: 100000, term_months: 12, monthly_interest_rate_bps: 199,
    installment_cents: 9500,
  },
})

const baseResponse = {
  id: 'id-1', created_at: '2026-10-25T15:00:00Z',
  results: [approved('bank_a'), approved('bank_b')],
}
const historyItem = {
  id: 'id-1', created_at: '2026-10-25T15:00:00Z', requested_amount_cents: 100000,
  term_months: 12, results: [{ bank: 'bank_a', status: 'approved' }, { bank: 'bank_b', status: 'failed' }],
}
const historyResponse = { items: [historyItem], total: 1, page: 1, page_size: 10 }
const detailResponse = {
  ...baseResponse, request: { monthly_income_cents: 300000, requested_amount_cents: 100000, term_months: 12 },
}

afterEach(() => vi.restoreAllMocks())

async function fillForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Nome completo'), 'Pessoa Fictícia')
  await user.type(screen.getByLabelText('E-mail'), 'pessoa@exemplo.com')
  await user.type(screen.getByLabelText('CPF'), '12345678901')
  await user.type(screen.getByLabelText('Renda mensal'), '3.000,00')
  await user.type(screen.getByLabelText('CNPJ do empregador'), '12345678000190')
  await user.type(screen.getByLabelText('Valor solicitado'), '1.000,00')
  await user.type(screen.getByLabelText('Prazo'), '12')
}

describe('simulação', () => {
  it('impede chamada para entrada inválida', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('Informe seu nome.')).toBeInTheDocument()
  })

  describe('histórico', () => {
    it('navega sem perder o formulário e atualiza após uma simulação', async () => {
      const user = userEvent.setup()
      const fetchMock = vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(new Response(JSON.stringify(historyResponse), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify(baseResponse), { status: 201 }))
        .mockResolvedValueOnce(new Response(JSON.stringify(historyResponse), { status: 200 }))
      render(<App />)
      await user.type(screen.getByLabelText('Nome completo'), 'Pessoa Fictícia')
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findByRole('heading', { name: 'Histórico' })).toBeInTheDocument()
      expect(screen.queryByText('Você ainda não tem simulações salvas nesta sessão.')).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Simular' }))
      expect(screen.getByLabelText('Nome completo')).toHaveValue('Pessoa Fictícia')
      await user.type(screen.getByLabelText('E-mail'), 'pessoa@exemplo.com')
      await user.type(screen.getByLabelText('CPF'), '12345678901')
      await user.type(screen.getByLabelText('Renda mensal'), '3.000,00')
      await user.type(screen.getByLabelText('CNPJ do empregador'), '12345678000190')
      await user.type(screen.getByLabelText('Valor solicitado'), '1.000,00')
      await user.type(screen.getByLabelText('Prazo'), '12')
      await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
      expect(await screen.findByText('Resultado da sua simulação')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findAllByText('R$ 1.000,00')).not.toHaveLength(0)
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/simulations?page=1&page_size=10'), expect.anything())
    })

    it('mostra vazio, carregamento e erro com tentativa novamente', async () => {
      const user = userEvent.setup()
      let resolveRequest: (response: Response) => void = () => undefined
      const pending = new Promise<Response>((resolve) => { resolveRequest = resolve })
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValueOnce(pending)
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(screen.getByRole('status')).toHaveTextContent('Carregando histórico')
      resolveRequest(new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 10 }), { status: 200 }))
      expect(await screen.findByText('Você ainda não tem simulações salvas nesta sessão.')).toBeInTheDocument()
      fetchMock.mockRejectedValueOnce(new Error('network'))
      await user.click(screen.getByRole('button', { name: 'Simular' }))
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar o histórico')
      await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar o histórico')
      expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument()
    })

    it('lista, pagina, abre detalhe e não executa POST', async () => {
      const user = userEvent.setup()
      const secondPage = { ...historyResponse, page: 2, total: 11 }
      const fetchMock = vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(new Response(JSON.stringify({ ...historyResponse, total: 11 }), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify(secondPage), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify(detailResponse), { status: 200 }))
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled()
      await user.click(screen.getByRole('button', { name: 'Próxima' }))
      expect(await screen.findByText(/Página 2 de 2/)).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Ver detalhe' }))
      expect(await screen.findByRole('heading', { name: 'Detalhe da simulação' })).toBeInTheDocument()
      expect(screen.getAllByText('Renda mensal')).not.toHaveLength(0)
      expect(screen.getByText('Excluir simulação')).toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([url, init]) => typeof url === 'string' && url.includes('/api/simulations?') && (init as RequestInit).method === 'POST')).toBe(false)
    })

    it('confirma/cancela exclusão, trata erro e impede duplicação', async () => {
      const user = userEvent.setup()
      let resolveDelete: (response: Response) => void = () => undefined
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
        const url = String(input)
        if (init?.method === 'DELETE') return new Promise<Response>((resolve) => { resolveDelete = resolve })
        if (url.includes('?page=')) return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }))
        if (url.endsWith('/id-1')) return Promise.resolve(new Response(JSON.stringify(detailResponse), { status: 200 }))
        return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }))
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      await screen.findByRole('button', { name: 'Excluir simulação' })
      const confirmMock = vi.spyOn(window, 'confirm').mockReturnValue(false)
      await user.click(screen.getByRole('button', { name: 'Excluir simulação' }))
      expect(confirmMock).toHaveBeenCalled()
      expect(fetchMock).toHaveBeenCalledTimes(2)
      confirmMock.mockReturnValue(true)
      const deleteButton = screen.getByRole('button', { name: 'Excluir simulação' })
      await user.click(deleteButton)
      await user.click(deleteButton)
      expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'DELETE')).toHaveLength(1)
      resolveDelete(new Response(null, { status: 204 }))
      expect(await screen.findByText('Simulação excluída com sucesso.')).toBeInTheDocument()
    })

    it('informa registro inacessível no detalhe', async () => {
      const user = userEvent.setup()
      vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(new Response(JSON.stringify(historyResponse), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'SIMULATION_NOT_FOUND', message: 'interno' } }), { status: 404 }))
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Esta simulação não está disponível.')
      expect(screen.getByRole('button', { name: '← Voltar ao histórico' })).toBeInTheDocument()
    })

    it('ignora erro tardio do detalhe depois de voltar à lista', async () => {
      const user = userEvent.setup()
      let rejectDetail: (error: Error) => void = () => undefined
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
        const url = String(input)
        if (url.includes('?page=')) return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }))
        return new Promise<Response>((_, reject) => {
          rejectDetail = reject
        })
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      await user.click(screen.getByRole('button', { name: '← Voltar ao histórico' }))
      expect(await screen.findByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      rejectDetail(new Error('late detail failure'))
      await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('?page=1&page_size=10'))).toBe(true)
    })

    it('ignora sucesso tardio do detalhe depois de voltar à lista', async () => {
      const user = userEvent.setup()
      let resolveDetail: (response: Response) => void = () => undefined
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
        const url = String(input)
        if (url.includes('?page=')) return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }))
        return new Promise<Response>((resolve) => { resolveDetail = resolve })
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      await user.click(screen.getByRole('button', { name: '← Voltar ao histórico' }))
      expect(await screen.findByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      resolveDetail(new Response(JSON.stringify(detailResponse), { status: 200 }))
      await waitFor(() => expect(screen.queryByRole('heading', { name: 'Detalhe da simulação' })).not.toBeInTheDocument())
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('?page=1&page_size=10'))).toBe(true)
    })

    it('reentra no histórico como listagem após alternar durante detalhe pendente', async () => {
      const user = userEvent.setup()
      let resolveDetail: (response: Response) => void = () => undefined
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
        const url = String(input)
        if (url.includes('?page=')) return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }))
        return new Promise<Response>((resolve) => { resolveDetail = resolve })
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      await user.click(screen.getByRole('button', { name: 'Simular' }))
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      resolveDetail(new Response(JSON.stringify(detailResponse), { status: 200 }))
      await new Promise<void>((resolve) => queueMicrotask(resolve))
      expect(screen.queryByRole('heading', { name: 'Detalhe da simulação' })).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('?page=1&page_size=10')).length).toBeGreaterThanOrEqual(2)
    })

    it('não deixa a resposta antiga de uma página sobrescrever uma reentrada mais recente', async () => {
      const user = userEvent.setup()
      let resolveOldPage: (response: Response) => void = () => undefined
      const newer = { ...historyResponse, items: [{ ...historyItem, id: 'newer-id', requested_amount_cents: 200000 }] }
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
        const url = String(input)
        if (url.includes('page=2')) return new Promise<Response>((resolve) => { resolveOldPage = resolve })
        return Promise.resolve(new Response(JSON.stringify({ ...historyResponse, total: 11 }), { status: 200 }))
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await screen.findByRole('button', { name: 'Próxima' })
      await user.click(screen.getByRole('button', { name: 'Próxima' }))
      await user.click(screen.getByRole('button', { name: 'Simular' }))
      fetchMock.mockImplementation(() => Promise.resolve(new Response(JSON.stringify(newer), { status: 200 })))
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findByText('R$ 2.000,00')).toBeInTheDocument()
      resolveOldPage(new Response(JSON.stringify({ ...historyResponse, page: 2, total: 11 }), { status: 200 }))
      await new Promise<void>((resolve) => queueMicrotask(resolve))
      expect(screen.getByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      expect(screen.queryByText('Página 2 de 2')).not.toBeInTheDocument()
    })

    it('corrige uma página esvaziada enquanto o total ainda é positivo', async () => {
      const user = userEvent.setup()
      const pageOne = { ...historyResponse, total: 11 }
      const fetchMock = vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(new Response(JSON.stringify(pageOne), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ items: [], total: 10, page: 2, page_size: 10 }), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ ...historyResponse, total: 10 }), { status: 200 }))
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Próxima' }))
      expect(await screen.findByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      expect(screen.queryByText('Você ainda não tem simulações salvas nesta sessão.')).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('page=1&page_size=10'))).toBe(true)
    })

    it('volta à página anterior ao excluir o único item da última página', async () => {
      const user = userEvent.setup()
      const pageOne = { ...historyResponse, total: 11, page: 1 }
      const pageTwoItem = { ...historyItem, id: 'page-two-id' }
      const pageTwo = { items: [pageTwoItem], total: 11, page: 2, page_size: 10 }
      const pageTwoDetail = { ...detailResponse, id: 'page-two-id' }
      let pageOneCalls = 0
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
        const url = String(input)
        if (init?.method === 'DELETE') {
          expect(url).toContain('/api/simulations/page-two-id')
          return Promise.resolve(new Response(null, { status: 204 }))
        }
        if (url.includes('page=2')) return Promise.resolve(new Response(JSON.stringify(pageTwo), { status: 200 }))
        if (url.includes('page=1')) {
          pageOneCalls += 1
          const response = pageOneCalls === 1 ? pageOne : { ...historyResponse, total: 10 }
          return Promise.resolve(new Response(JSON.stringify(response), { status: 200 }))
        }
        if (url.endsWith('/page-two-id')) return Promise.resolve(new Response(JSON.stringify(pageTwoDetail), { status: 200 }))
        return Promise.resolve(new Response(JSON.stringify(pageOne), { status: 200 }))
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findByText('Página 1 de 2 · 11 simulações')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próxima' })).toBeEnabled()
      await user.click(await screen.findByRole('button', { name: 'Próxima' }))
      expect(await screen.findByText('Página 2 de 2 · 11 simulações')).toBeInTheDocument()
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      await user.click(await screen.findByRole('button', { name: 'Excluir simulação' }))
      expect(await screen.findByText('Simulação excluída com sucesso.')).toBeInTheDocument()
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('page=2&page_size=10'))).toBe(true)
      expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('page=1&page_size=10')).length).toBeGreaterThanOrEqual(2)
      expect(await screen.findByText('Página 1 de 1 · 10 simulações')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      expect(screen.queryByText('page-two-id')).not.toBeInTheDocument()
    })

    it('preserva o detalhe após erro de DELETE e permite tentar novamente', async () => {
      const user = userEvent.setup()
      const fetchMock = vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(new Response(JSON.stringify(historyResponse), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify(detailResponse), { status: 200 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'SIMULATION_DELETE_FAILED', message: 'Falha de armazenamento.' } }), { status: 503 }))
        .mockResolvedValueOnce(new Response(null, { status: 204 }))
        .mockResolvedValueOnce(new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 10 }), { status: 200 }))
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      await user.click(await screen.findByRole('button', { name: 'Excluir simulação' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível excluir a simulação')
      expect(screen.getByRole('heading', { name: 'Detalhe da simulação' })).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))
      expect(await screen.findByText('Simulação excluída com sucesso.')).toBeInTheDocument()
      expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'DELETE')).toHaveLength(2)
    })

    it('ignora sucesso tardio de DELETE depois de abrir outro detalhe', async () => {
      const user = userEvent.setup()
      const secondItem = { ...historyItem, id: 'id-2' }
      const twoItems = { items: [historyItem, secondItem], total: 2, page: 1, page_size: 10 }
      let resolveDelete: (response: Response) => void = () => undefined
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
        const url = String(input)
        if (init?.method === 'DELETE') return new Promise<Response>((resolve) => { resolveDelete = resolve })
        if (url.includes('?page=')) return Promise.resolve(new Response(JSON.stringify(twoItems), { status: 200 }))
        if (url.endsWith('/id-2')) return Promise.resolve(new Response(JSON.stringify({ ...detailResponse, id: 'id-2' }), { status: 200 }))
        return Promise.resolve(new Response(JSON.stringify(detailResponse), { status: 200 }))
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      const items = await screen.findAllByRole('button', { name: 'Ver detalhe' })
      await user.click(items[0])
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      await user.click(await screen.findByRole('button', { name: 'Excluir simulação' }))
      await user.click(screen.getByRole('button', { name: '← Voltar ao histórico' }))
      await user.click((await screen.findAllByRole('button', { name: 'Ver detalhe' }))[1])
      expect(await screen.findByRole('heading', { name: 'Detalhe da simulação' })).toBeInTheDocument()
      resolveDelete(new Response(null, { status: 204 }))
      await waitFor(() => expect(screen.getByRole('heading', { name: 'Detalhe da simulação' })).toBeInTheDocument())
      expect(screen.queryByText('Simulação excluída com sucesso.')).not.toBeInTheDocument()
      expect(screen.queryByText('Não foi possível excluir a simulação.')).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.filter(([, request]) => (request as RequestInit | undefined)?.method === 'DELETE')).toHaveLength(1)
    })

    it('ignora falha tardia de DELETE depois de abrir outro detalhe', async () => {
      const user = userEvent.setup()
      const secondItem = { ...historyItem, id: 'id-2' }
      const twoItems = { items: [historyItem, secondItem], total: 2, page: 1, page_size: 10 }
      let rejectDelete: (error: Error) => void = () => undefined
      vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
        const url = String(input)
        if (init?.method === 'DELETE') return new Promise<Response>((_, reject) => { rejectDelete = reject })
        if (url.includes('?page=')) return Promise.resolve(new Response(JSON.stringify(twoItems), { status: 200 }))
        if (url.endsWith('/id-2')) return Promise.resolve(new Response(JSON.stringify({ ...detailResponse, id: 'id-2' }), { status: 200 }))
        return Promise.resolve(new Response(JSON.stringify(detailResponse), { status: 200 }))
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      const items = await screen.findAllByRole('button', { name: 'Ver detalhe' })
      await user.click(items[0])
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      await user.click(await screen.findByRole('button', { name: 'Excluir simulação' }))
      await user.click(screen.getByRole('button', { name: '← Voltar ao histórico' }))
      await user.click((await screen.findAllByRole('button', { name: 'Ver detalhe' }))[1])
      expect(await screen.findByRole('heading', { name: 'Detalhe da simulação' })).toBeInTheDocument()
      rejectDelete(new Error('late delete failure'))
      await waitFor(() => expect(screen.getByRole('heading', { name: 'Detalhe da simulação' })).toBeInTheDocument())
      expect(screen.queryByText('Não foi possível excluir a simulação.')).not.toBeInTheDocument()
      expect(screen.queryByText('late delete failure')).not.toBeInTheDocument()
    })

    it('cancela DELETE ao sair durante a exclusão pendente sem restaurar o detalhe', async () => {
      const user = userEvent.setup()
      let rejectDelete: (error: DOMException) => void = () => undefined
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
        const url = String(input)
        if (init?.method === 'DELETE') return new Promise<Response>((_, reject) => { rejectDelete = reject })
        if (url.includes('?page=')) return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }))
        return Promise.resolve(new Response(JSON.stringify(detailResponse), { status: 200 }))
      })
      render(<App />)
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      await user.click(await screen.findByRole('button', { name: 'Ver detalhe' }))
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      await user.click(await screen.findByRole('button', { name: 'Excluir simulação' }))
      await user.click(screen.getByRole('button', { name: 'Simular' }))
      rejectDelete(new DOMException('Aborted', 'AbortError'))
      await user.click(screen.getByRole('button', { name: 'Histórico' }))
      expect(await screen.findByRole('button', { name: 'Ver detalhe' })).toBeInTheDocument()
      expect(screen.queryByText('Simulação excluída com sucesso.')).not.toBeInTheDocument()
      expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'DELETE')).toHaveLength(1)
    })
  })

  it('valida os limites de nome e e-mail sem restringir caracteres internacionais', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    await user.type(screen.getByLabelText('Nome completo'), 'a'.repeat(151))
    await user.type(screen.getByLabelText('E-mail'), 'usuário@exemplo.рф')
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByText('O nome deve ter no máximo 150 caracteres.')).toBeInTheDocument()
    expect(screen.queryByText('Informe um e-mail válido.')).not.toBeInTheDocument()
  })

  it('envia e apresenta aprovação na ordem Banco A e Banco B', async () => {
    const user = userEvent.setup()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(baseResponse), { status: 201 }))
    render(<App />)
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findByRole('heading', { name: 'Resultado da sua simulação' })).toBeInTheDocument()
    const headings = screen.getAllByRole('heading', { level: 3 })
    expect(headings.map((heading) => heading.textContent)).toEqual(['Banco A', 'Banco B'])
    expect(screen.getAllByText('R$ 1.000,00')).toHaveLength(2)
    expect(screen.getAllByText('1,99% ao mês')).toHaveLength(2)
  })

  it('apresenta reprovação com mensagem da API, falha parcial e falha total', async () => {
    const user = userEvent.setup()
    const rejected = { bank: 'bank_a', status: 'rejected', reasons: [{ code: 'CUSTOM', message: 'Mensagem normalizada do banco.' }] }
    const failed = { bank: 'bank_b', status: 'failed', error: { code: 'TIMEOUT', message: 'A instituição demorou para responder.' } }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      ...baseResponse, results: [rejected, failed],
    }), { status: 201 }))
    render(<App />)
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findByText('Mensagem normalizada do banco.')).toBeInTheDocument()
    expect(screen.getByText('Falha técnica')).toBeInTheDocument()
    expect(screen.getByText('Isso não representa uma reprovação de crédito.')).toBeInTheDocument()
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      ...baseResponse, results: [
        { ...failed, bank: 'bank_a' },
        { ...failed, bank: 'bank_b' },
      ],
    }), { status: 201 }))
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findAllByText('Falha técnica')).toHaveLength(2)
  })

  it('impede duplicação por clique e teclado durante o carregamento', async () => {
    const user = userEvent.setup()
    let resolveRequest: (response: Response) => void = () => undefined
    const pending = new Promise<Response>((resolve) => { resolveRequest = resolve })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(pending)
    render(<App />)
    await fillForm(user)
    const button = screen.getByRole('button', { name: 'Simular empréstimo' })
    await user.click(button)
    expect(screen.getByRole('status')).toHaveTextContent('Consultando')
    await user.click(button)
    await user.click(screen.getByLabelText('Prazo'))
    await user.keyboard('{Enter}')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    resolveRequest(new Response(JSON.stringify(baseResponse), { status: 201 }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Resultado da sua simulação' })).toBeInTheDocument())
  })

  it('remove resultados na nova tentativa e preserva valores e erros de campo', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(baseResponse), { status: 201 }))
    render(<App />)
    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(await screen.findByText('Resultado da sua simulação')).toBeInTheDocument()
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
      error: {
        code: 'VALIDATION_ERROR', message: 'Revise os campos informados.',
        fields: [{ field: 'email', code: 'INVALID_VALUE', message: 'E-mail inválido.' }],
      },
    }), { status: 422 }))
    await user.click(screen.getByRole('button', { name: 'Simular empréstimo' }))
    expect(screen.queryByText('Resultado da sua simulação')).not.toBeInTheDocument()
    expect(await screen.findByText('E-mail inválido.')).toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toHaveValue('pessoa@exemplo.com')
  })
})
