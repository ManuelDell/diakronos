import { ref } from 'vue'

const isOpen = ref(false)
const isPending = ref(false)
const isSubmitting = ref(false)
const currentPolicy = ref(null)
let resolvePromise = null
let rejectPromise = null

export function useAuditConfirm() {
  function openConfirm(policy) {
    // Race-Condition-Schutz: Vorherigen Promise rejecten
    if (isOpen.value && rejectPromise) {
      rejectPromise(new Error('Superseded by newer confirmation'))
      rejectPromise = null
    }
    currentPolicy.value = policy
    isOpen.value = true
    isPending.value = true
    isSubmitting.value = false
    return new Promise((resolve, reject) => {
      resolvePromise = resolve
      rejectPromise = reject
    })
  }

  function submit(reason) {
    isOpen.value = false
    isPending.value = false
    resolvePromise?.(reason)
    resolvePromise = null
    rejectPromise = null
  }

  function cancel() {
    isOpen.value = false
    isPending.value = false
    resolvePromise?.(null)
    resolvePromise = null
    rejectPromise = null
  }

  return { isOpen, isPending, isSubmitting, currentPolicy, openConfirm, submit, cancel }
}
