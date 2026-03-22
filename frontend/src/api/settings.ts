import client from './client'

export interface SettingsResponse {
  llm_provider: string
  api_key_configured: boolean
  quick_import_folder: string | null
  default_player: string | null
  min_player_matches: number
  min_deck_matches: number
  auto_import_enabled: boolean
  auto_import_interval_sec: number
  onboarding_completed: boolean
}

export interface AutoImportStatus {
  enabled: boolean
  interval_sec: number
  last_run_at: string | null
  last_result: {
    mtgo: { imported: number; skipped: number; errors: number }
    mtga: { imported: number; skipped: number; errors: number }
  } | null
}

export async function fetchAutoImportStatus(): Promise<AutoImportStatus> {
  const res = await client.get<AutoImportStatus>('/api/import/auto-import/status')
  return res.data
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
  auto_import_enabled?: boolean
  auto_import_interval_sec?: number
  onboarding_completed?: boolean
}): Promise<void> {
  await client.put('/api/settings', body)
}

export async function deleteApiKey(): Promise<void> {
  await client.delete('/api/settings/api-key')
}
