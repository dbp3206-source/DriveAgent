export function documentPreviewKey(storage: Pick<Storage, 'getItem'>, ownerId: string | undefined, messageId: string): string
export function renewDocumentPreviewKey(storage: Pick<Storage, 'getItem' | 'setItem'>, ownerId: string | undefined, messageId: string, operationId: string, readStatus: (id: string) => Promise<{state: string}>): Promise<string>
