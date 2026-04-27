<template>
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5" :style="{ borderTopColor: color, borderTopWidth: '3px' }">
        <div class="text-3xl font-extrabold leading-none" :style="{ color }">{{ value }}</div>
        <div class="text-xs text-gray-500 mt-2 font-medium">{{ label }}</div>
        <div v-if="sub" class="text-xs text-gray-400 mt-0.5">{{ sub }}</div>
    </div>
</template>

<script setup>
defineProps({ label: String, value: [Number, String], color: String, sub: String })
</script>
