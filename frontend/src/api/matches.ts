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
  deck?: string
  opponent_deck?: string
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

export type ExportDetailLevel = 'summary' | 'matches' | 'actions'

export interface ExportParams extends MatchFilters {
  detail_level: ExportDetailLevel
  limit: number
}

export async function fetchExportCount(filters: MatchFilters): Promise<number> {
  const res = await client.get<{ count: number }>('/api/matches/export/count', { params: filters })
  return res.data.count
}

export async function fetchExportMarkdown(params: ExportParams): Promise<string> {
  const res = await client.get<string>('/api/matches/export', {
    params,
    responseType: 'text',
  })
  return res.data
}

export async function fetchLatestMatchDate(): Promise<string | null> {
  const res = await client.get<{ latest_date: string | null }>('/api/matches/latest-date')
  return res.data.latest_date
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
