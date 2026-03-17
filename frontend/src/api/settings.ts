import client from './client'

export interface SettingsResponse {
  llm_provider: string
  api_key_configured: boolean
  quick_import_folder: string | null
  default_player: string | null
  min_player_matches: number
  min_deck_matches: number
}

export async function fetchSettings(): Promise<SettingsResponse> {
  const res = await client.get<SettingsResponse>('/api/settings')
  return res.data
}

export async function updateSettings(body: {
  llm_provider?: string
  api_key?: string
  quick_import_folder?: string | null
  default_player?: string | null
  min_player_matches?: number | null
  min_deck_matches?: number | null
}): Promise<void> {
  await client.put('/api/settings', body)
}

export async function deleteApiKey(): Promise<void> {
  await client.delete('/api/settings/api-key')
}
