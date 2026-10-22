import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { ref, computed, shallowRef } from 'vue'

function router() {
  const callbacks = {}
  const window = {location:{hash:'#/wiki'},history:{replaceState(_a,_b,hash){window.location.hash=hash}},__DIakonosBOOT:{is_admin:true},addEventListener(name,fn){callbacks[name]=fn}}
  const ctx = vm.createContext({window,ref,computed,shallowRef,console,setzeFenstertitel:()=>{},lazyImport:async()=>({default:{}})})
  let source = readFileSync(new URL('../src/diakonos/router.js',import.meta.url),'utf8')
  source=source.replace(/^import .*$/gm,'').replace(/import\([^)]*\)/g,'lazyImport()').replace(/^export \{.*\}$/gm,'').replace(/^export /gm,'')
  vm.runInContext(source,ctx)
  return {ctx, window, run:code=>vm.runInContext(code,ctx), go(hash){window.location.hash=hash;return callbacks.hashchange()}}
}
test('Asynchrone Verwerfen-Antwort hält die alte Seite bis zur Zustimmung', async()=>{
  const h=router()
  h.run('let antwort; onBeforeEach(()=>new Promise(resolve=>{antwort=resolve}))')
  const nav=h.go('#/profile')
  assert.equal(h.run('currentPageName.value'),'Wiki')
  h.run('antwort(false)')
  await nav
  assert.equal(h.run('currentPageName.value'),'Wiki')
  assert.equal(h.window.location.hash,'#/wiki')
  const nav2=h.go('#/profile')
  h.run('antwort(true)')
  await nav2
  assert.equal(h.run('currentPageName.value'),'Profile')
})
test('Verspätete Zustimmung überschreibt keine neuere Navigation', async()=>{
  const h=router()
  h.run('let antwort; onBeforeEach(({to})=>to==="#/profile"?new Promise(resolve=>{antwort=resolve}):true)')
  const alt=h.go('#/profile')
  await h.go('#/wiki')
  h.run('antwort(true)')
  await alt
  assert.equal(h.run('currentPageName.value'),'Wiki')
})
