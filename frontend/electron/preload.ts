import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  selectDatFile: (): Promise<string | null> =>
    ipcRenderer.invoke('select-dat-file'),

  selectJsonFile: (): Promise<string | null> =>
    ipcRenderer.invoke('select-json-file'),

  scanFolder: (): Promise<{ folderPath: string; files: string[] } | null> =>
    ipcRenderer.invoke('scan-folder'),

  scanFolderQuick: (folderPath: string): Promise<Array<{ path: string; mtime: number }>> =>
    ipcRenderer.invoke('scan-folder-quick', folderPath),

  scanSurveilFolder: (folderPath: string): Promise<Array<{ path: string; name: string; mtime: number; size: number }>> =>
    ipcRenderer.invoke('scan-surveil-folder', folderPath),

  readDatFile: (filePath: string): Promise<Buffer> =>
    ipcRenderer.invoke('read-dat-file', filePath),

  selectFolder: (): Promise<string | null> =>
    ipcRenderer.invoke('select-folder'),

  prepareMtgaCardsDb: (installFolder: string): Promise<string> =>
    ipcRenderer.invoke('prepare-mtga-cards-db', installFolder),
})
