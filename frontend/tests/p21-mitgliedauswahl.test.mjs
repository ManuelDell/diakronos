import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, ref } from 'vue'

const s=readFileSync(new URL('../src/diakonos/components/MitgliedAuswahl.vue',import.meta.url),'utf8')
const filter=s.slice(s.indexOf('const gefiltert = computed('),s.indexOf('async function laden('))
test('Mehrwort-Feinfilter entspricht der Serversuche, auch mit umgekehrter Reihenfolge',()=>{
  const ctx=vm.createContext({computed,suche:ref('  BEISPIEL   anna  '),normal:x=>String(x||'').toLowerCase().trim(),alle:ref([{name:'Anna Beispiel'},{name:'Anna Anders'}])})
  vm.runInContext(filter,ctx)
  assert.deepEqual(Array.from(vm.runInContext('gefiltert.value.map(m=>m.name)',ctx)),['Anna Beispiel'])
})
