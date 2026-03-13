import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  selectDatFile: (): Promise<string | null> =>
    ipcRenderer.invoke('select-dat-file'),

  scanFolder: (): Promise<{ folderPath: string; files: string[] } | null> =>
    ipcRenderer.invoke('scan-folder'),

  scanFolderQuick: (folderPath: string): Promise<Array<{ path: string; mtime: number }>> =>
    ipcRenderer.invoke('scan-folder-quick', folderPath),

  readDatFile: (filePath: string): Promise<Buffer> =>
    ipcRenderer.invoke('read-dat-file', filePath),
})
