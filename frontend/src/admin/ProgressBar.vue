<template>
    <div class="mb-3">
        <div class="flex justify-between mb-1">
            <span class="text-sm text-gray-600">{{ label }}</span>
            <span class="text-sm font-semibold" :style="{ color }">{{ value }} ({{ pct }}%)</span>
        </div>
        <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
                class="h-full rounded-full transition-all duration-500"
                :style="{ width: pct + '%', background: color }"
            ></div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ label: String, value: Number, total: Number, color: String })
const pct = computed(() => props.total > 0 ? Math.round((props.value / props.total) * 100) : 0)
</script>
