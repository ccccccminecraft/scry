import client from './client'

export interface DeckDefinition {
  id: number
  player_name: string | null
  deck_name: string
  format: string | null
  threshold: number
  cards: string[]
  exclude_cards: string[]
}

export interface DeckDefinitionInput {
  player_name: string | null
  deck_name: string
  format: string | null
  threshold: number
  cards: string[]
  exclude_cards: string[]
}

export interface DeckBulkInput {
  player_name: string
  deck_name: string
  last_n?: number
  date_from?: string
  date_to?: string
}

export async function fetchDeckDefinitions(): Promise<DeckDefinition[]> {
  const res = await client.get<{ definitions: DeckDefinition[] }>('/api/deck-definitions')
  return res.data.definitions
}

export async function createDeckDefinition(body: DeckDefinitionInput): Promise<DeckDefinition> {
  const res = await client.post<DeckDefinition>('/api/deck-definitions', body)
  return res.data
}

export async function updateDeckDefinition(id: number, body: DeckDefinitionInput): Promise<DeckDefinition> {
  const res = await client.put<DeckDefinition>(`/api/deck-definitions/${id}`, body)
  return res.data
}

export async function deleteDeckDefinition(id: number): Promise<void> {
  await client.delete(`/api/deck-definitions/${id}`)
}

export async function deckBulkUpdate(body: DeckBulkInput): Promise<{ updated: number }> {
  const res = await client.patch<{ updated: number }>('/api/deck-bulk', body)
  return res.data
}

export async function importDeckDefinitions(
  file: File,
  playerName: string | null,
  onConflict: 'skip' | 'overwrite',
): Promise<{ imported: number; skipped: number; errors: number }> {
  const form = new FormData()
  form.append('file', file)
  const params: Record<string, string> = { on_conflict: onConflict }
  if (playerName) params.player_name = playerName
  const res = await client.post<{ imported: number; skipped: number; errors: number }>(
    '/api/deck-definitions/import',
    form,
    { params },
  )
  return res.data
}

export async function exportDeckDefinitions(): Promise<Blob> {
  const res = await client.get('/api/deck-definitions/export', { responseType: 'blob' })
  return res.data
}

export interface GeneratedDeckPayload {
  version: string
  generated_at: string
  source: string
  format: string | null
  definitions: { deck_name: string; threshold: number; cards: string[] }[]
}

export async function applyDeckDefinitions(overwrite: boolean): Promise<{ updated: number; skipped: number }> {
  const res = await client.post<{ updated: number; skipped: number }>(
    '/api/decks/apply-definitions',
    null,
    { params: { overwrite }, timeout: 120000 },
  )
  return res.data
}

export async function generateDeckDefinitions(
  format: string | null,
  notes: string | null,
): Promise<GeneratedDeckPayload> {
  const res = await client.post<GeneratedDeckPayload>(
    '/api/deck-definitions/generate',
    { format: format || null, notes: notes || null },
    { timeout: 120000 },
  )
  return res.data
}
