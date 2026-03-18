import axios from 'axios'

const BASE = 'http://localhost:18432/api'

export async function deleteAllMatches(): Promise<number> {
  const res = await axios.delete(`${BASE}/matches`)
  return (res.data as { deleted: number }).deleted
}

export async function deleteMatchesByRange(dateFrom?: string, dateTo?: string): Promise<number> {
  const res = await axios.delete(`${BASE}/matches/range`, {
    data: { date_from: dateFrom ?? null, date_to: dateTo ?? null },
  })
  return (res.data as { deleted: number }).deleted
}

export async function resetDatabase(): Promise<void> {
  await axios.delete(`${BASE}/reset`)
}
