import { app, BrowserWindow, Menu, ipcMain, dialog } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs'

// WSL2 環境で D-Bus / systemd 関連の無害なエラー出力を抑制する
if (process.platform === 'linux') {
  process.env.DBUS_SESSION_BUS_ADDRESS = 'disabled:'
}

const isDev = !app.isPackaged
let backendProcess: ChildProcess | null = null
let mainWindow: BrowserWindow | null = null

function startBackend(): void {
  if (isDev) return // 開発時は Docker が担当

  const backendPath = path.join(process.resourcesPath, 'backend.exe')
  backendProcess = spawn(backendPath, [], { detached: false })
}

async function waitForBackend(url: string, retries = 30, interval = 500): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      await new Promise(resolve => setTimeout(resolve, interval))
    }
  }
  throw new Error('Backend did not start in time')
}

async function createWindow(): Promise<void> {
  const iconPath = isDev
    ? path.join(__dirname, '../../assets/icon.ico')
    : path.join(process.resourcesPath, 'app.asar.unpacked/assets/icon.ico')

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    resizable: true,
    icon: iconPath,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    await waitForBackend('http://localhost:18432/api/health')
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  startBackend()
  await createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  backendProcess?.kill()
})

// IPC: 単体ファイル選択
ipcMain.handle('select-dat-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openFile'],
    filters: [{ name: 'MTGO Log', extensions: ['dat'] }],
  })
  return result.canceled ? null : result.filePaths[0]
})

// IPC: 単体JSONファイル選択 (MTGA / Surveil)
ipcMain.handle('select-json-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openFile'],
    filters: [{ name: 'Surveil JSON', extensions: ['json'] }],
  })
  return result.canceled ? null : result.filePaths[0]
})

// IPC: フォルダスキャン
ipcMain.handle('scan-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openDirectory'],
    defaultPath: `C:\\Users\\${process.env.USERNAME ?? ''}\\AppData\\Local\\Apps\\2.0`,
  })
  if (result.canceled) return null
  const folderPath = result.filePaths[0]
  const files = scanForDatFiles(folderPath)
  return { folderPath, files }
})

// IPC: ダイアログなしでフォルダをスキャンし mtime 付きで返す
ipcMain.handle('scan-folder-quick', (_event, folderPath: string) => {
  const files = scanForDatFiles(folderPath)
  return files.map(filePath => ({
    path: filePath,
    mtime: fs.statSync(filePath).mtimeMs,
  }))
})

// IPC: Surveil フォルダスキャン（.json ファイル一覧を mtime/size 付きで返す）
ipcMain.handle('scan-surveil-folder', (_event, folderPath: string) => {
  const results: Array<{ path: string; name: string; mtime: number; size: number }> = []
  try {
    const entries = fs.readdirSync(folderPath, { withFileTypes: true })
    for (const entry of entries) {
      if (entry.isFile() && entry.name.endsWith('.json')) {
        const fullPath = path.join(folderPath, entry.name)
        const stat = fs.statSync(fullPath)
        results.push({ path: fullPath, name: entry.name, mtime: stat.mtimeMs, size: stat.size })
      }
    }
  } catch {
    // アクセス権限エラー等は無視
  }
  return results
})

// IPC: フォルダ選択（パスのみ返す）
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openDirectory'],
  })
  return result.canceled ? null : result.filePaths[0]
})

// IPC: ファイル読み込み
ipcMain.handle('read-dat-file', (_event, filePath: string) => {
  return fs.readFileSync(filePath)
})

// IPC: MTGA CardDatabase ファイルの mtime を返す（自動同期チェック用）
ipcMain.handle('get-mtga-cards-mtime', (_event, installFolder: string) => {
  const rawFolder = path.join(installFolder, 'MTGA_Data', 'Downloads', 'Raw')
  let entries: string[]
  try {
    entries = fs.readdirSync(rawFolder)
  } catch {
    return null
  }
  const candidates = entries
    .filter(f => /^Raw_CardDatabase_.*\.mtga$/.test(f))
    .map(f => {
      const p = path.join(rawFolder, f)
      return { path: p, mtime: fs.statSync(p).mtimeMs }
    })
    .sort((a, b) => b.mtime - a.mtime)
  return candidates.length > 0 ? candidates[0].mtime : null
})

// IPC: MTGA CardDatabase を同期用パスにコピーして返す
// Dev:  ./database/mtga_sync.mtga にコピー → Docker は /database/mtga_sync.mtga で参照
// Prod: backend.exe は同一マシンなので元のパスをそのまま返す
ipcMain.handle('prepare-mtga-cards-db', (_event, installFolder: string) => {
  const rawFolder = path.join(installFolder, 'MTGA_Data', 'Downloads', 'Raw')
  let entries: string[]
  try {
    entries = fs.readdirSync(rawFolder)
  } catch {
    throw new Error(`フォルダが見つかりません: ${rawFolder}`)
  }
  const candidates = entries
    .filter(f => /^Raw_CardDatabase_.*\.mtga$/.test(f))
    .map(f => {
      const p = path.join(rawFolder, f)
      return { path: p, mtime: fs.statSync(p).mtimeMs }
    })
    .sort((a, b) => b.mtime - a.mtime)
  if (candidates.length === 0) {
    throw new Error('Raw_CardDatabase_*.mtga が見つかりません')
  }
  if (isDev) {
    // Docker の /database/ ボリュームにコピーする
    const destPath = path.join(__dirname, '../../database/mtga_sync.mtga')
    fs.copyFileSync(candidates[0].path, destPath)
    return '/database/mtga_sync.mtga'
  } else {
    // AppData\Roaming はフォルダリダイレクトでネットワーク上に置かれている場合があるため、
    // 必ずローカルな %TEMP% (AppData\Local\Temp) にコピーしてから backend.exe に渡す
    const destDir = app.getPath('temp')
    const destPath = path.join(destDir, 'mtga_sync.mtga')
    fs.copyFileSync(candidates[0].path, destPath)
    return destPath
  }
})

function scanForDatFiles(dir: string): string[] {
  const results: string[] = []
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true })
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        results.push(...scanForDatFiles(fullPath))
      } else if (entry.isFile() && /^Match_GameLog_.*\.dat$/.test(entry.name)) {
        results.push(fullPath)
      }
    }
  } catch {
    // アクセス権限エラー等は無視して続行
  }
  return results
}
