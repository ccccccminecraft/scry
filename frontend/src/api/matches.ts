import client from './client'

export interface MatchSummary {
  match_id: string
  date: string
  players: string[]
  decks: (string | null)[]
  match_winner: string
  game_count: number
  format: string | null
}

export interface MatchListResponse {
  total: number
  limit: number
  offset: number
  matches: MatchSummary[]
}

export interface PlayerInfo {
  player_name: string
  deck_name: string | null
  game_plan: string | null
  deck_version_id: number | null
  deck_version_label: string | null
}

export interface GameSummary {
  game_id: number
  game_number: number
  winner: string
  turns: number
  first_player: string
  mulligans: Record<string, number>
}

export interface MatchDetail {
  match_id: string
  date: string
  players: PlayerInfo[]
  match_winner: string
  format: string | null
  games: GameSummary[]
}

export interface ActionEntry {
  turn: number
  phase: string | null
  active_player: string
  player: string
  action_type: string
  card_name: string | null
  target_name: string | null
  sequence: number
}

export interface ActionLogResponse {
  game_id: number
  actions: ActionEntry[]
}

export interface MatchFilters {
  player?: string
  opponent?: string
  deck_ids?: number[]
  decks?: string[]
  version_id?: number
  opponent_decks?: string[]
  format?: string
  date_from?: string
  date_to?: string
}

export async function fetchMatches(limit = 50, offset = 0, filters: MatchFilters = {}): Promise<MatchListResponse> {
  const res = await client.get<MatchListResponse>('/api/matches', {
    params: { limit, offset, ...filters },
  })
  return res.data
}

export async function fetchMatchDetail(matchId: string): Promise<MatchDetail> {
  const res = await client.get<MatchDetail>(`/api/matches/${matchId}`)
  return res.data
}

export async function fetchActionLog(matchId: string, gameId: number): Promise<ActionLogResponse> {
  const res = await client.get<ActionLogResponse>(
    `/api/matches/${matchId}/games/${gameId}/actions`,
  )
  return res.data
}

export interface ExportParams extends MatchFilters {
  include_summary?: boolean
  include_deck_stats?: boolean
  include_card_stats?: boolean
  include_deck_list?: boolean
  include_matches?: boolean
  include_actions?: boolean
  limit: number
  no_limit?: boolean
}

export async function fetchExportCount(filters: MatchFilters): Promise<number> {
  const res = await client.get<{ count: number }>('/api/matches/export/count', { params: filters })
  return res.data.count
}

export interface CardDictionaryCount {
  total: number
  cached: number
  fetchable: number
  miss: number
}

export async function fetchCardDictionaryCount(filters: MatchFilters): Promise<CardDictionaryCount> {
  const res = await client.get<CardDictionaryCount>('/api/matches/export/card-dictionary/count', { params: filters })
  return res.data
}

export async function fetchCardDictionary(filters: MatchFilters): Promise<string> {
  const res = await client.get<string>('/api/matches/export/card-dictionary', {
    params: filters,
    responseType: 'text',
  })
  return res.data
}

export interface FetchMissingResult {
  fetched: number
  failed: number
  failed_names: string[]
}

function _buildSearchParams(filters: MatchFilters): URLSearchParams {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      for (const v of value) params.append(key, String(v))
    } else {
      params.append(key, String(value))
    }
  }
  return params
}

export function streamFetchMissingCardData(
  filters: MatchFilters,
  onProgress: (done: number, total: number, fetched: number, failed: number) => void,
): Promise<FetchMissingResult> {
  const params = _buildSearchParams(filters)
  const url = `http://localhost:18432/api/matches/export/card-dictionary/fetch-missing?${params}`

  return new Promise(async (resolve, reject) => {
    try {
      const response = await fetch(url, { method: 'POST' })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        reject(new Error(body.detail || `HTTP error ${response.status}`))
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE イベントは "\n\n" で区切られる
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue
            const data = JSON.parse(line.slice(6))
            onProgress(data.done, data.total, data.fetched, data.failed)
            if (data.complete) {
              resolve({ fetched: data.fetched, failed: data.failed, failed_names: data.failed_names })
            }
          }
        }
      }
    } catch (e) {
      reject(e instanceof Error ? e : new Error(String(e)))
    }
  })
}

export async function resetCardCacheMiss(filters: MatchFilters): Promise<{ deleted: number }> {
  const res = await client.post<{ deleted: number }>(
    '/api/matches/export/card-dictionary/reset-miss',
    {},
    { params: filters },
  )
  return res.data
}

export async function fetchExportMarkdown(params: ExportParams): Promise<string> {
  const res = await client.get<string>('/api/matches/export', {
    params,
    responseType: 'text',
  })
  return res.data
}

export interface BulkAssignParams {
  player: string
  format?: string
  deck_name?: string
  date_from?: string
  date_to?: string
  overwrite?: boolean
}

export async function fetchBulkAssignCount(params: BulkAssignParams): Promise<number> {
  const res = await client.get<{ count: number }>('/api/matches/bulk-assign-deck-version/count', { params })
  return res.data.count
}

export async function bulkAssignDeckVersion(deck_version_id: number, params: BulkAssignParams): Promise<number> {
  const res = await client.post<{ updated: number }>('/api/matches/bulk-assign-deck-version', {
    deck_version_id,
    ...params,
  })
  return res.data.updated
}

export async function fetchLatestMatchDate(source?: string): Promise<string | null> {
  const res = await client.get<{ latest_date: string | null }>('/api/matches/latest-date', {
    params: source ? { source } : {},
  })
  return res.data.latest_date
}

export async function putDeckVersion(
  matchId: string,
  playerName: string,
  deckVersionId: number,
): Promise<void> {
  await client.put(
    `/api/matches/${matchId}/players/${encodeURIComponent(playerName)}/deck-version`,
    { deck_version_id: deckVersionId },
  )
}

export async function deleteDeckVersion(
  matchId: string,
  playerName: string,
): Promise<void> {
  await client.delete(
    `/api/matches/${matchId}/players/${encodeURIComponent(playerName)}/deck-version`,
  )
}

export async function patchPlayer(
  matchId: string,
  playerName: string,
  body: { deck_name?: string | null; game_plan?: string | null },
): Promise<PlayerInfo> {
  const res = await client.patch<PlayerInfo>(
    `/api/matches/${matchId}/players/${encodeURIComponent(playerName)}`,
    body,
  )
  return res.data
}
