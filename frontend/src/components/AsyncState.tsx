import { Button, MessageBar, MessageBarBody, Spinner } from '@fluentui/react-components'

export function LoadingState({ label = 'Đang tải dữ liệu' }: { label?: string }) {
  return (
    <div className="center-state" role="status" aria-live="polite">
      <Spinner size="medium" label={label} />
    </div>
  )
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <MessageBar intent="error" layout="multiline">
      <MessageBarBody>
        <span>{message}</span>
        {retry ? (
          <Button appearance="transparent" onClick={retry}>
            Thử lại
          </Button>
        ) : null}
      </MessageBarBody>
    </MessageBar>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-state__mark" aria-hidden="true" />
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  )
}
