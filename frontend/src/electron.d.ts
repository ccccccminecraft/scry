interface ElectronAPI {
  selectDatFile: () => Promise<string | null>
  scanFolder: () => Promise<{ folderPath: string; files: string[] } | null>
  scanFolderQuick: (folderPath: string) => Promise<Array<{ path: string; mtime: number }>>
  readDatFile: (filePath: string) => Promise<Buffer>
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}

export {}
