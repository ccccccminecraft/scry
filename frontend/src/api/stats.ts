import client from './client'

export interface WinRatePoint {
  date: string
  match_index: number
  won: boolean
}

export interface DeckStat {
  deck_name: string
  matches: number
  win_rate: number
}

export interface StatsResponse {
  total_matches: number
  win_rate: number
  avg_turns: number
  mulligan_rate: number
  first_play_win_rate: number
  second_play_win_rate: number
  win_rate_history: WinRatePoint[]
  deck_stats: DeckStat[]
}

export interface CardStat {
  card_name: string
  play_count: number
  game_count: number
  win_rate: number
}

export interface StatsFilters {
  player: string
  opponent?: string
  deck?: string
  opponent_deck?: string
  format?: string
  date_from?: string
  date_to?: string
  history_size?: number
}

export async function fetchStats(filters: StatsFilters): Promise<StatsResponse> {
  const res = await client.get<StatsResponse>('/api/stats', { params: filters })
  return res.data
}

export async function fetchCardStats(
  filters: StatsFilters,
  limit = 20,
  perspective: 'self' | 'opponent' = 'self',
): Promise<CardStat[]> {
  const res = await client.get<{ cards: CardStat[] }>('/api/stats/cards', {
    params: { ...filters, limit, perspective },
  })
  return res.data.cards
}

export async function fetchFormats(): Promise<string[]> {
  const res = await client.get<{ formats: string[] }>('/api/stats/formats')
  return res.data.formats
}

export async function fetchPlayers(): Promise<string[]> {
  const res = await client.get<{ players: string[] }>('/api/stats/players')
  return res.data.players
}

export async function fetchOpponents(player: string): Promise<string[]> {
  const res = await client.get<{ opponents: string[] }>('/api/stats/opponents', {
    params: { player },
  })
  return res.data.opponents
}

export async function fetchPlayerDecks(player: string): Promise<string[]> {
  const res = await client.get<{ player_decks: string[] }>('/api/stats/player-decks', {
    params: { player },
  })
  return res.data.player_decks
}

export async function fetchOpponentDecks(player: string, opponent?: string): Promise<string[]> {
  const res = await client.get<{ opponent_decks: string[] }>('/api/stats/opponent-decks', {
    params: { player, opponent },
  })
  return res.data.opponent_decks
}
