import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [tailwindcss()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        login: resolve(__dirname, 'login.html'),
        dashboard: resolve(__dirname, 'dashboard.html'),
        customers: resolve(__dirname, 'customers.html'),
        'customer-profile': resolve(__dirname, 'customer-profile.html'),
        'customer-daily': resolve(__dirname, 'customer-daily.html'),
        payments: resolve(__dirname, 'payments.html'),
        notifications: resolve(__dirname, 'notifications.html'),
        copilot: resolve(__dirname, 'copilot.html'),
        reports: resolve(__dirname, 'reports.html'),
        settings: resolve(__dirname, 'settings.html'),
        admin: resolve(__dirname, 'admin.html'),
        activate: resolve(__dirname, 'activate.html'),
        '403': resolve(__dirname, '403.html'),
        '404': resolve(__dirname, '404.html'),
        '500': resolve(__dirname, '500.html'),
        forgot: resolve(__dirname, 'forgot.html'),
      }
    }
  }
})


