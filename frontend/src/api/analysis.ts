import client from './client'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface SessionSummary {
  id: number
  player_name: string
  prompt_template_id: number | null
  title: string
  created_at: string
  updated_at: string
}

export interface SessionDetail extends SessionSummary {
  filter_opponent: string | null
  filter_deck: string | null
  filter_opponent_deck: string | null
  filter_format: string | null
  filter_date_from: string | null
  filter_date_to: string | null
  messages: Array<{
    id: number
    role: 'user' | 'assistant'
    content: string
    display_order: number
  }>
}

export interface PromptTemplate {
  id: number
  name: string
  content: string
  is_default: boolean
}

export interface QuestionItem {
  id: number
  text: string
  display_order: number
}

export interface QuestionSet {
  id: number
  name: string
  is_default: boolean
  items: QuestionItem[]
}

export interface StreamCallbacks {
  onDelta: (text: string) => void
  onDone: (sessionId: number) => void
  onError: (message: string) => void
}

export async function fetchSessions(player?: string): Promise<SessionSummary[]> {
  const res = await client.get<{ sessions: SessionSummary[] }>('/api/analysis/sessions', {
    params: player ? { player } : {},
  })
  return res.data.sessions
}

export async function fetchSessionDetail(id: number): Promise<SessionDetail> {
  const res = await client.get<SessionDetail>(`/api/analysis/sessions/${id}`)
  return res.data
}

export async function deleteSession(id: number): Promise<void> {
  await client.delete(`/api/analysis/sessions/${id}`)
}

export async function fetchPromptTemplates(): Promise<PromptTemplate[]> {
  const res = await client.get<{ templates: PromptTemplate[] }>('/api/prompt-templates')
  return res.data.templates
}

export async function fetchQuestionSets(): Promise<QuestionSet[]> {
  const res = await client.get<{ question_sets: QuestionSet[] }>('/api/question-sets')
  return res.data.question_sets
}

export async function streamChat(
  req: {
    player: string
    prompt_template_id?: number | null
    session_id?: number | null
    message: string
    history?: ChatMessage[]
    opponent?: string | null
    deck?: string | null
    opponent_deck?: string | null
    format?: string | null
    date_from?: string | null
    date_to?: string | null
  },
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch('http://localhost:8000/api/analysis/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    })
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    callbacks.onError('サーバーへの接続に失敗しました')
    return
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    callbacks.onError(data.detail ?? `HTTP ${response.status}`)
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  let receivedDone = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()!

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.delta !== undefined) {
            callbacks.onDelta(event.delta)
          } else if (event.done) {
            receivedDone = true
            callbacks.onDone(event.session_id)
          } else if (event.error) {
            receivedDone = true
            callbacks.onError(event.error)
          }
        } catch {}
      }
    }
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      callbacks.onError('ストリーミング中にエラーが発生しました')
    }
    return
  }
  if (!receivedDone) {
    callbacks.onError('接続が予期せず切断されました。バックエンドのログを確認してください。')
  }
}
