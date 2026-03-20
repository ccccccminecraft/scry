interface ElectronAPI {
  selectDatFile: () => Promise<string | null>
  selectJsonFile: () => Promise<string | null>
  scanFolder: () => Promise<{ folderPath: string; files: string[] } | null>
  scanFolderQuick: (folderPath: string) => Promise<Array<{ path: string; mtime: number }>>
  scanSurveilFolder: (folderPath: string) => Promise<Array<{ path: string; name: string; mtime: number; size: number }>>
  readDatFile: (filePath: string) => Promise<Buffer>
  selectFolder: () => Promise<string | null>
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}

export {}
