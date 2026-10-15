import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Input, MessageBar, MessageBarBody } from '@fluentui/react-components'

/** Title is selected before preparing the immutable operation, not after approval. */
export function DocumentExportTitleDialog({title, busy, error, onTitleChange, onCancel, onPrepare}: {
  title: string
  busy: boolean
  error: string
  onTitleChange: (value: string) => void
  onCancel: () => void
  onPrepare: () => void
}) {
  return (
    <Dialog open onOpenChange={(_, data) => { if (!data.open && !busy) onCancel() }}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Đặt tên Google Doc</DialogTitle>
          <DialogContent>
            <div className="dialog-form">
              <p>Kiểm lại tên trước khi chuẩn bị bản xem trước. Tài liệu chỉ được tạo sau bước bạn xác nhận.</p>
              <label htmlFor="document-export-title">Tên tài liệu</label>
              <Input id="document-export-title" value={title} maxLength={200} disabled={busy}
                onChange={(_, data) => onTitleChange(data.value)} />
              {error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : null}
            </div>
          </DialogContent>
          <DialogActions>
            <Button disabled={busy} onClick={onCancel}>Hủy</Button>
            <Button appearance="primary" disabled={busy || !title.trim()} onClick={onPrepare}>
              {busy ? 'Đang chuẩn bị…' : 'Chuẩn bị bản xem trước'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  )
}
