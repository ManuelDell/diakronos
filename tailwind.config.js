import frappeUIPreset from 'frappe-ui/tailwind'

export default {
    presets: [frappeUIPreset],
    content: [
        './frontend/index.html',
        './frontend/src/**/*.{vue,js,ts,jsx,tsx}',
        './node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
        '../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
    ],
    theme: {
        extend: {},
    },
    plugins: [],
}
