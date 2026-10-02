import test from 'node:test'
import assert from 'node:assert/strict'
import { citationHref } from './citationLinks.mjs'

test('web citation opens its collected URL rather than the Drive reader', () => {
  assert.deepEqual(citationHref({ file_id: 'https://www.joc.or.jp/games/asia/2026/' }), {
    href: 'https://www.joc.or.jp/games/asia/2026/', title: 'Mở trang nguồn trên Internet',
  })
})
test('Drive citation keeps exact file and page even with a Google web-view link', () => {
  assert.equal(citationHref({ file_id: 'doc123', page_number: 7, web_view_link: 'https://docs.google.com/document/d/doc123' }).href, '/#/drive?file=doc123&page=7')
})
test('Gmail and local citations retain their dedicated readers', () => {
  assert.equal(citationHref({ file_id: 'mail1', web_view_link: 'https://mail.google.com/mail/u/0/#inbox/mail1' }).href, 'https://mail.google.com/mail/u/0/#inbox/mail1')
  assert.equal(citationHref({ file_id: 'local:1', web_view_link: '/#/local?source=1' }).href, '/#/local?source=1')
})
test('malformed or credential-bearing web URLs are not opened externally', () => {
  for (const file_id of ['https://', 'https://secret@example.com/file', 'javascript:alert(1)']) {
    assert.ok(citationHref({ file_id }).href.startsWith('/#/drive?file='))
  }
})
