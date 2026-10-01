/** One decorative canvas, independent from component surfaces and route content. */
export function WorkspaceCanvas({ animate }: { animate: boolean }) {
  return <div className={`workspace-canvas${animate ? ' workspace-canvas--motion' : ''}`} aria-hidden="true" />
}
