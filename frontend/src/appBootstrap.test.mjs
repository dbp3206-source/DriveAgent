import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

// Execute the actual App with a minimal hook/render harness. Lazy modules are
// only resolved when the returned authenticated tree contains their element.
function harness() {
  const source = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText
  const states = [], effects = [], lazyPages = [], calls = []
  let cursor = 0, effectCursor = 0, chunkAttempts = 0, failChunk = false
  let resolveAuth
  const auth = new Promise(resolve => { resolveAuth = resolve })
  const react = {
    useState(initial) {
      const index = cursor++
      if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value }]
    },
    useRef: value => ({ current: value }),
    useEffect(effect) { if (!(effectCursor++ in effects)) effects.push(effect) },
    lazy(loader) { const page = { loader }; lazyPages.push(page); return page },
    Suspense: 'Suspense',
  }
  const jsx = (type, props) => ({ type, props })
  const chat = { ChatPage: () => { calls.push('/api/chat/private'); return null } }
  const require = path => {
    if (path === 'react') return react
    if (path === 'react/jsx-runtime') return { jsx, jsxs: jsx }
    if (path === './pages/ChatPage') {
      chunkAttempts++
      if (failChunk) throw new Error('chunk offline')
      return chat
    }
    if (path === './api') return { api(path) {
      calls.push(path)
      return path === '/api/auth/status' ? auth : Promise.resolve(null)
    } }
    if (path === './pageRoute.mjs') return { pageFromHash: () => 'chat', hashForPage: () => '#/chat' }
    if (path === './emailWorkflow.mjs') return { roleCanCreateDraft: () => false, roleCanSendEmail: () => false }
    return new Proxy({}, { get: (_object, name) => String(name) })
  }
  const storage = { getItem: () => null, setItem() {}, removeItem() {} }
  const exports = {}
  vm.runInNewContext(code, { exports, require,
    window: { location: { hash: '#/chat', reload() {} }, history: { replaceState() {} },
      addEventListener() {}, removeEventListener() {}, scrollTo() {} },
    document: { documentElement: { dataset: {} } }, localStorage: storage, sessionStorage: storage,
  })
  function render() { cursor = 0; effectCursor = 0; return exports.default() }
  async function mount(tree) {
    if (!tree || typeof tree !== 'object') return
    if (tree.type?.loader) {
      const module = await tree.type.loader()
      module.default(tree.props)
    }
    for (const child of Object.values(tree.props ?? {})) {
      if (Array.isArray(child)) for (const item of child) await mount(item)
      else await mount(child)
    }
  }
  return { render, mount, effects, calls, resolveAuth,
    get chunkAttempts() { return chunkAttempts },
    set failChunk(value) { failChunk = value },
  }
}

test('App overlaps Chat chunk with pending auth, but only mounts private Chat after authentication', async () => {
  const app = harness()
  const pendingTree = app.render()
  for (const effect of app.effects) effect()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(app.chunkAttempts, 1)
  assert.deepEqual(app.calls, ['/api/health', '/api/auth/status'])
  await app.mount(pendingTree)
  assert.ok(!app.calls.includes('/api/chat/private'))
  app.resolveAuth({ authenticated: true, user: { role: 'owner' } })
  await new Promise(resolve => setImmediate(resolve))
  await app.mount(app.render())
  assert.ok(app.calls.includes('/api/chat/private'))
  assert.equal(app.chunkAttempts, 1, 'lazy render reuses the successful preloaded module')
})

test('App retries failed preload during authenticated lazy render', async () => {
  const app = harness()
  app.failChunk = true
  app.render()
  for (const effect of app.effects) effect()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(app.chunkAttempts, 1)
  assert.ok(!app.calls.includes('/api/chat/private'))
  app.failChunk = false
  app.resolveAuth({ authenticated: true, user: { role: 'owner' } })
  await new Promise(resolve => setImmediate(resolve))
  await app.mount(app.render())
  assert.equal(app.chunkAttempts, 2)
  assert.ok(app.calls.includes('/api/chat/private'))
})
