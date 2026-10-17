import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const privacyPage = await readFile(new URL('../public/privacy.html', import.meta.url), 'utf8')
const chatPage = await readFile(new URL('./pages/ChatPage.tsx', import.meta.url), 'utf8')
const localSourcesPage = await readFile(new URL('./pages/LocalSourcesPage.tsx', import.meta.url), 'utf8')
const setupGate = await readFile(new URL('./components/SetupGate.tsx', import.meta.url), 'utf8')

test('public data notice explains Gemini free-tier risk and Veridra retention behavior', () => {
  assert.match(privacyPage, /lang="vi"/)
  assert.match(privacyPage, /Google Gemini/)
  assert.match(privacyPage, /hạn mức miễn phí/)
  assert.match(privacyPage, /người đánh giá có thể xem/)
  assert.match(privacyPage, /đủ 30 ngày/)
  assert.match(privacyPage, /chỉ dọn sau khi bạn xác nhận/)
  assert.match(privacyPage, /không xóa thư, lịch hay tệp gốc trong Google/)
  assert.match(privacyPage, /dbp3206@gmail\.com/)
})

test('data processing notice is visible before chat use and Google authorization', () => {
  assert.match(chatPage, /chat-data-use-notice/)
  assert.match(chatPage, /href="\/privacy\.html"/)
  assert.match(setupGate, /href="\/privacy\.html"/)
  assert.match(localSourcesPage, /hạn mức miễn phí/)
  assert.match(localSourcesPage, /ngay lúc nạp/)
  assert.match(localSourcesPage, /nội dung có thể được gửi sang Google ngay lúc nạp/)
  assert.match(localSourcesPage, /href="\/privacy\.html"/)
  assert.match(setupGate, /trước khi|Khi trò chuyện/)
})

test('Drive explains Gemini transfer before a user indexes a file', async () => {
  const drivePage = await readFile(new URL('./pages/DrivePage.tsx', import.meta.url), 'utf8')
  assert.match(drivePage, /Khi bấm “Lập chỉ mục”, nội dung tệp được gửi tới Google Gemini/)
  assert.match(drivePage, /người đánh giá có thể xem/)
  assert.match(drivePage, /đừng dùng dữ liệu cá nhân, nhạy cảm hoặc bí mật/i)
  assert.match(drivePage, /href="\/privacy\.html"/)
})
