export interface DriveFileCapability {
  readable: boolean
  indexable: boolean
  reason: string
}

export function driveFileCapability(mimeType: string, fileName?: string): DriveFileCapability
