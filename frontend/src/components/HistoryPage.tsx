import { useEffect, useRef, useState } from 'react'
import { deleteSimulation, getSimulationDetail, listSimulations, ApiRequestError } from '../api'
import { BankResultCard } from './BankResultCard'
import { formatMoney } from '../formatting'
import type { SimulationDetailResponse, SimulationHistoryResponse, SimulationSummary } from '../types'

interface Props {
  active: boolean
  refreshKey: number
}

const pageSize = 10
const dateFormatter = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

export function HistoryPage({ active, refreshKey }: Props) {
  const [page, setPage] = useState(1)
  const [history, setHistory] = useState<SimulationHistoryResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<SimulationDetailResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorTitle, setErrorTitle] = useState('Não foi possível carregar o histórico.')
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [refreshAfterDelete, setRefreshAfterDelete] = useState(0)
  const requestId = useRef(0)
  const deleteInProgress = useRef(false)
  const listController = useRef<AbortController | null>(null)
  const detailController = useRef<AbortController | null>(null)
  const deleteController = useRef<AbortController | null>(null)
  const deleteContext = useRef(0)

  useEffect(() => {
    if (!active) {
      listController.current?.abort()
      detailController.current?.abort()
      deleteController.current?.abort()
      deleteContext.current += 1
      deleteController.current = null
      deleteInProgress.current = false
      requestId.current += 1
      return
    }
    return () => {
      listController.current?.abort()
      detailController.current?.abort()
      deleteController.current?.abort()
      deleteContext.current += 1
      deleteController.current = null
      deleteInProgress.current = false
      requestId.current += 1
    }
  }, [active])

  useEffect(() => {
    if (!active || selectedId) return
    const controller = new AbortController()
    listController.current?.abort()
    listController.current = controller
    const currentRequest = ++requestId.current
    async function loadHistory() {
      setIsLoading(true)
      setError(null)
      setErrorTitle('Não foi possível carregar o histórico.')
      try {
        const response = await listSimulations(page, pageSize, controller.signal)
        if (currentRequest !== requestId.current) return
        const lastPage = Math.max(1, Math.ceil(response.total / pageSize))
        if (response.items.length === 0 && response.total > 0 && page > lastPage) {
          setPage(lastPage)
          return
        }
        setHistory(response)
      } catch (requestError) {
        if (!isAbort(requestError) && currentRequest === requestId.current) {
          setError(publicMessage(requestError, 'Não foi possível consultar o histórico. Tente novamente.'))
        }
      } finally {
        if (currentRequest === requestId.current) setIsLoading(false)
      }
    }
    void loadHistory()
    return () => controller.abort()
  }, [active, page, refreshKey, refreshAfterDelete, selectedId])

  function openDetail(id: string) {
    const controller = new AbortController()
    detailController.current?.abort()
    detailController.current = controller
    const currentRequest = ++requestId.current
    setSelectedId(id)
    setDetail(null)
    setIsLoading(true)
    setError(null)
    setErrorTitle('Não foi possível carregar a simulação.')
    void getSimulationDetail(id, controller.signal)
      .then((response) => {
        if (currentRequest === requestId.current) setDetail(response)
      })
      .catch((requestError: unknown) => {
        if (isAbort(requestError) || currentRequest !== requestId.current) return
        setError(publicMessage(requestError, 'Não foi possível consultar esta simulação.'))
      })
      .finally(() => {
        if (currentRequest === requestId.current) setIsLoading(false)
      })
  }

  function backToList() {
    detailController.current?.abort()
    deleteController.current?.abort()
    deleteContext.current += 1
    deleteController.current = null
    deleteInProgress.current = false
    requestId.current += 1
    setSelectedId(null)
    setDetail(null)
    setError(null)
    setErrorTitle('Não foi possível carregar o histórico.')
  }

  async function removeSimulation(id: string) {
    if (deleteInProgress.current) return
    if (!window.confirm('Deseja excluir esta simulação?')) return
    deleteInProgress.current = true
    const operationContext = ++deleteContext.current
    const controller = new AbortController()
    deleteController.current = controller
    setIsLoading(true)
    setError(null)
    setErrorTitle('Não foi possível excluir a simulação.')
    let deleted = false
    try {
      await deleteSimulation(id, controller.signal)
      if (operationContext !== deleteContext.current) return
      deleted = true
      setSuccessMessage('Simulação excluída com sucesso.')
      const totalAfterDelete = Math.max(0, (history?.total ?? 1) - 1)
      const lastPage = Math.max(1, Math.ceil(totalAfterDelete / pageSize))
      setPage((currentPage) => Math.min(currentPage, lastPage))
      setSelectedId(null)
      setDetail(null)
      setRefreshAfterDelete((key) => key + 1)
    } catch (requestError) {
      if (isAbort(requestError) || operationContext !== deleteContext.current) return
      setError(publicMessage(requestError, 'Não foi possível excluir a simulação. Tente novamente.'))
    } finally {
      if (operationContext === deleteContext.current) {
        deleteController.current = null
        deleteInProgress.current = false
        if (!deleted) setIsLoading(false)
      }
    }
  }

  if (selectedId) {
    return (
      <section className="history-page" aria-labelledby="history-title">
        <button className="back-link" type="button" onClick={backToList}>← Voltar ao histórico</button>
        <h1 id="history-title">Detalhe da simulação</h1>
        {isLoading && <p className="status-message" role="status">Carregando simulação...</p>}
        {error && <HistoryError
          title={errorTitle}
          message={error}
          onRetry={() => errorTitle === 'Não foi possível excluir a simulação.'
            ? void removeSimulation(selectedId)
            : openDetail(selectedId)}
        />}
        {detail && !isLoading && <SimulationDetail detail={detail} onDelete={() => void removeSimulation(detail.id)} disabled={isLoading} />}
      </section>
    )
  }

  const totalPages = history ? Math.max(1, Math.ceil(history.total / pageSize)) : 1
  return (
    <section className="history-page" aria-labelledby="history-title">
      <div className="section-heading history-heading">
        <div><p className="eyebrow">Sessão do navegador</p><h1 id="history-title">Histórico</h1></div>
        <p className="history-hint">Suas simulações ficam disponíveis por até sete dias.</p>
      </div>
      {successMessage && <p className="success-message" role="status">{successMessage}</p>}
      {isLoading && <p className="status-message" role="status">Carregando histórico...</p>}
      {error && <HistoryError title={errorTitle} message={error} onRetry={() => setRefreshAfterDelete((key) => key + 1)} />}
      {!isLoading && !error && history && history.items.length === 0 && <p className="empty-history">Você ainda não tem simulações salvas nesta sessão.</p>}
      {!isLoading && !error && history && history.items.length > 0 && (
        <>
          <div className="history-list">
            {history.items.map((item) => <HistoryItem key={item.id} item={item} onOpen={() => openDetail(item.id)} />)}
          </div>
          <div className="pagination" aria-label="Paginação do histórico">
            <button type="button" onClick={() => setPage((current) => current - 1)} disabled={page <= 1 || isLoading}>Anterior</button>
            <span>Página {page} de {totalPages} · {history.total} simulações</span>
            <button type="button" onClick={() => setPage((current) => current + 1)} disabled={page >= totalPages || isLoading}>Próxima</button>
          </div>
        </>
      )}
    </section>
  )
}

function HistoryItem({ item, onOpen }: { item: SimulationSummary; onOpen: () => void }) {
  return (
    <article className="history-item">
      <div><p className="history-date">{formatDate(item.created_at)}</p><h2>{formatMoney(item.requested_amount_cents)}</h2><p>{item.term_months} meses</p></div>
      <div className="status-summary"><span>Banco A: {statusLabel(item.results[0].status)}</span><span>Banco B: {statusLabel(item.results[1].status)}</span></div>
      <button className="secondary-button" type="button" onClick={onOpen}>Ver detalhe</button>
    </article>
  )
}

function SimulationDetail({ detail, onDelete, disabled }: { detail: SimulationDetailResponse; onDelete: () => void; disabled: boolean }) {
  return (
    <div className="detail-content">
      <p className="history-date">{formatDate(detail.created_at)}</p>
      <dl className="detail-summary">
        <div><dt>Renda mensal</dt><dd>{formatMoney(detail.request.monthly_income_cents)}</dd></div>
        <div><dt>Valor solicitado</dt><dd>{formatMoney(detail.request.requested_amount_cents)}</dd></div>
        <div><dt>Prazo</dt><dd>{detail.request.term_months} meses</dd></div>
      </dl>
      <div className="results-grid saved-results">{detail.results.map((result) => <BankResultCard key={result.bank} result={result} />)}</div>
      <button className="danger-button" type="button" onClick={onDelete} disabled={disabled}>Excluir simulação</button>
    </div>
  )
}

function HistoryError({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return <div className="operation-error" role="alert"><strong>{title}</strong><p>{message}</p><button className="secondary-button" type="button" onClick={onRetry}>Tentar novamente</button></div>
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : dateFormatter.format(date)
}

function statusLabel(status: SimulationSummary['results'][number]['status']) {
  return status === 'approved' ? 'aprovado' : status === 'rejected' ? 'não aprovado' : 'falha técnica'
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

function publicMessage(error: unknown, fallback: string) {
  if (error instanceof ApiRequestError && error.code === 'SIMULATION_NOT_FOUND') return 'Esta simulação não está disponível.'
  return error instanceof Error ? error.message : fallback
}
