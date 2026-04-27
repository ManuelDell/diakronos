<template>
    <div class="text-center">
        <div class="text-2xl font-bold" :style="{ color }">{{ value }}</div>
        <div class="text-xs text-gray-500 mt-0.5">{{ label }}</div>
    </div>
</template>

<script setup>
defineProps({ value: [Number, String], label: String, color: String })
</script>
