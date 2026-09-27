import { defineStore } from 'pinia'
import { api, wsClient } from '../api/client'

export const useSessionStore = defineStore('session', {
  state: () => ({
    activeSession: null,   // { session_id, user_id, started_at }
    sampleProgress: 0,     // 0-100
    uploadQueue: [],       // [{ t_ms, ppg_raw }]
    wsStatus: 'idle'       // idle / connecting / live / closed
  }),
  getters: {
    queuedCount: (s) => s.uploadQueue.length
  },
  actions: {
    async startSession(userId) {
      const res = await api.post('/api/ppg/sessions', { user_id: userId })
      this.activeSession = res.data
      this.sampleProgress = 0
      this.uploadQueue = []
      return res.data
    },
    pushSamples(batch) {
      this.uploadQueue.push(...batch)
    },
    async flushSamples() {
      if (!this.activeSession || !this.uploadQueue.length) return
      const res = await api.post(
        `/api/ppg/sessions/${this.activeSession.session_id}/samples`,
        { samples: this.uploadQueue }
      )
      this.uploadQueue = []
      this.sampleProgress = res.data?.progress ?? 100
      return res.data
    },
    connectWs(userId) {
      this.wsStatus = 'connecting'
      wsClient.connect(`/ws/live?user_id=${userId}`, {
        onopen: () => { this.wsStatus = 'live' },
        onclose: () => { this.wsStatus = 'closed' },
        onmessage: (msg) => {
          if (msg.type === 'vector_update') {
            // 预留：实时漂移更新事件（由视图订阅）
            this.onVectorUpdate?.(msg)
          }
        }
      })
    },
    disconnectWs() {
      wsClient.disconnect()
      this.wsStatus = 'idle'
    }
  }
})
