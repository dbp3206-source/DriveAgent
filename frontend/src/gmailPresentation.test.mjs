import assert from 'node:assert/strict'
import test from 'node:test'
import { attachmentUrl, canRenderGmailThread, inlineImageFetchPlan, normalizeContentId, rewriteEmailCssImageUrls } from './gmailPresentation.mjs'

test('plain text and safe HTML emails can render in the same conversation', () => {
  assert.equal(canRenderGmailThread([
    { presentation_mode: 'faithful_text', body: 'Plain text body' },
    { presentation_mode: 'safe_html', body: 'Readable fallback', html_body: '<table><tr><td>Original</td></tr></table>' },
  ]), true)
})

test('image-only HTML and downloadable MIME attachments remain visible', () => {
  assert.equal(canRenderGmailThread([
    { presentation_mode: 'safe_html', body: '', html_body: '<img src="cid:hero">' },
  ]), true)
  assert.equal(canRenderGmailThread([
    { presentation_mode: 'unsupported', body: '', attachments: [{ filename: 'invite.ics' }] },
  ]), true)
})

test('empty threads or unsupported messages with no readable body remain non-renderable', () => {
  assert.equal(canRenderGmailThread([]), false)
  assert.equal(canRenderGmailThread([{ presentation_mode: 'unsupported', body: '', attachments: [] }]), false)
  assert.equal(canRenderGmailThread([{ presentation_mode: 'readable_text', body: '  ' }]), false)
})

test('attachment URLs encode identifiers and separate inline image access', () => {
  assert.equal(attachmentUrl('msg/1', 'att 2'), '/api/gmail/messages/msg%2F1/attachments/att%202')
  assert.equal(attachmentUrl('msg1', 'att2', true), '/api/gmail/messages/msg1/attachments/att2?inline=true')
})

test('CID matching ignores brackets, prefix, case, and whitespace', () => {
  assert.equal(normalizeContentId(' <Hero@Mail> '), 'hero@mail')
  assert.equal(normalizeContentId('CID:hero@mail'), 'hero@mail')
  assert.equal(normalizeContentId('cid:<Hero%40Mail>'), 'hero@mail')
})

test('inline CID images without embedded bytes are fetched by the authenticated parent', () => {
  assert.deepEqual(inlineImageFetchPlan([
    { inline: true, content_id: '<Hero@Mail>', attachment_id: 'large-image', mime_type: 'image/png' },
    { inline: true, content_id: 'cid:hero@mail', attachment_id: 'duplicate', mime_type: 'image/png' },
    { inline: true, content_id: 'small', attachment_id: 'embedded', mime_type: 'image/jpeg', data_base64: 'AA==' },
    { inline: true, content_id: 'vector', attachment_id: 'svg', mime_type: 'image/svg+xml' },
    { inline: false, content_id: 'file', attachment_id: 'download', mime_type: 'image/png' },
  ]), [{ contentId: 'hero@mail', attachmentId: 'large-image' }])
})

test('CID CSS images are mapped to fetched inline-image variables and remote URLs remain countable', () => {
  const result = rewriteEmailCssImageUrls(
    'background-image: url("cid:<Hero@Mail>"); border-image: url(cid:missing); mask-image: url(https://img.example/logo.png);',
    (contentId) => contentId === 'hero@mail' ? '--driveagent-inline-image-0' : null,
  )

  assert.equal(result.css, 'background-image: var(--driveagent-inline-image-0); border-image: none; mask-image: url(https://img.example/logo.png);')
  assert.equal(result.remoteImageCount, 1)
})

test('CSS protocol-relative images count as external and non-image data URLs are untouched', () => {
  const result = rewriteEmailCssImageUrls(
    'background: url(//img.example/hero.png); icon: url(data:image/png;base64,AA==);',
    () => null,
  )

  assert.equal(result.remoteImageCount, 1)
  assert.match(result.css, /url\(data:image\/png;base64,AA==\)/)
})
