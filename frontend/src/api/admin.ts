import axios from 'axios'

const BASE = 'http://localhost:18432/api'

// ─── Scryfall Bulk Data ───────────────────────────────────────────────────────

export async function getSyncStatus(): Promise<{ last_synced_at: string | null }> {
  const res = await axios.get(`${BASE}/admin/sync-card-names/status`)
  return res.data
}

export async function syncCardNames(): Promise<{ synced: number }> {
  const res = await axios.post(`${BASE}/admin/sync-card-names`)
  return res.data
}

// ─── MTGA CardDatabase ────────────────────────────────────────────────────────

export async function getMtgaFolder(): Promise<{ folder: string | null }> {
  const res = await axios.get(`${BASE}/admin/mtga-cards-folder`)
  return res.data
}

export async function setMtgaFolder(folder: string): Promise<void> {
  await axios.put(`${BASE}/admin/mtga-cards-folder`, { folder })
}

export async function getMtgaSyncStatus(): Promise<{ folder: string | null; last_synced_at: string | null }> {
  const res = await axios.get(`${BASE}/admin/sync-mtga-cards/status`)
  return res.data
}

export async function syncMtgaCards(): Promise<{ synced: number; source: string }> {
  const res = await axios.post(`${BASE}/admin/sync-mtga-cards`)
  return res.data
}
