import { useState, useRef, useEffect } from 'react'
import { AgentAudioVisualizerAura } from './components/agents-ui/agent-audio-visualizer-aura'

// Helper: Downsample float32 buffer to 16,000 Hz box-averaged PCM
function downsampleBuffer(buffer, inSampleRate, outSampleRate = 16000) {
  if (inSampleRate === outSampleRate) return buffer
  if (inSampleRate < outSampleRate) return buffer
  const ratio = inSampleRate / outSampleRate
  const newLength = Math.round(buffer.length / ratio)
  const result = new Float32Array(newLength)
  let offsetResult = 0
  let offsetBuffer = 0
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio)
    let accum = 0
    let count = 0
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i]
      count++
    }
    result[offsetResult] = count > 0 ? accum / count : buffer[offsetBuffer]
    offsetResult++
    offsetBuffer = nextOffsetBuffer
  }
  return result
}

export default function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [isHearing, setIsHearing] = useState(true)
  const [agentState, setAgentState] = useState('idle') // 'idle' | 'listening' | 'thinking' | 'speaking'
  const [audioLevel, setAudioLevel] = useState(0)
  const [logs, setLogs] = useState([])
  const [reservations, setReservations] = useState([])
  const [securityAlerts, setSecurityAlerts] = useState([])

  // Live real-time inputs tracking (shows inputs getting filled on the side UI)
  const [activeFormType, setActiveFormType] = useState('room') // 'room' | 'dining'
  const [roomDraft, setRoomDraft] = useState({
    guest_name: '',
    guest_email: '',
    guest_phone: '',
    check_in_date: '',
    check_out_date: '',
    room_type: '',
    guests_count: '',
    additional_guests: '',
    status: 'drafting', // 'drafting' | 'confirmed'
  })
  const [diningDraft, setDiningDraft] = useState({
    customer_name: '',
    customer_phone: '',
    reservation_date: '',
    reservation_time: '',
    party_size: '',
    seating_type: '',
    status: 'drafting', // 'drafting' | 'confirmed'
  })

  const wsRef = useRef(null)
  const inputAudioContextRef = useRef(null)
  const outputAudioContextRef = useRef(null)
  const micStreamRef = useRef(null)
  const processorRef = useRef(null)
  const isHearingRef = useRef(true)
  const nextPlayTimeRef = useRef(0)
  const activeSourcesRef = useRef([])

  useEffect(() => {
    isHearingRef.current = isHearing
    if (isConnected) {
      if (!isHearing) {
        setAgentState('idle')
      } else if (agentState === 'idle') {
        setAgentState('listening')
      }
    }
  }, [isHearing, isConnected])

  const addLog = (msg, type = 'info') => {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLogs((prev) => [...prev.slice(-40), { time, msg, type }])
  }

  // --- Start Voice Session ---
  const startConversation = async () => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext

      // Output context for 24kHz Gemini playback
      outputAudioContextRef.current = new AudioCtx()
      if (outputAudioContextRef.current.state === 'suspended') {
        await outputAudioContextRef.current.resume()
      }
      nextPlayTimeRef.current = outputAudioContextRef.current.currentTime
      activeSourcesRef.current = []

      // Connect to FastAPI WebSocket
      const userId = 'test_user_001'
      const wsUrl = `ws://localhost:8000/ws/voice-agent/${userId}`
      const ws = new WebSocket(wsUrl)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = async () => {
        setIsConnected(true)
        setIsHearing(true)
        isHearingRef.current = true
        setAgentState('listening')
        addLog('Connected to Grand Luxe Concierge', 'success')
        await startMicrophone()
      }

      ws.onmessage = async (event) => {
        if (typeof event.data === 'string') {
          try {
            const data = JSON.parse(event.data)
            handleServerEvent(data)
          } catch (e) {
            console.error('Failed to parse text message:', e)
          }
        } else if (event.data instanceof ArrayBuffer) {
          playAudioChunk(event.data)
        } else if (event.data instanceof Blob) {
          const buffer = await event.data.arrayBuffer()
          playAudioChunk(buffer)
        }
      }

      ws.onerror = (err) => {
        console.error('WebSocket Error:', err)
        addLog('Connection error occurred', 'error')
      }

      ws.onclose = () => {
        setIsConnected(false)
        setAgentState('idle')
        stopMicrophone()
        stopAllAudio()
        addLog('Voice session ended', 'warning')
      }
    } catch (err) {
      console.error(err)
      addLog(`Initialization error: ${err.message}`, 'error')
    }
  }

  // --- Handle Realtime Events from Server ---
  const handleServerEvent = (data) => {
    // 1. Interruption by user speaking
    if (data.type === 'interrupted') {
      addLog('⚡ Assistant paused for user speech', 'warning')
      stopAllAudio()
      if (isHearingRef.current) {
        setAgentState('listening')
      }
    }

    // 2. Real-time Live Form Input Sync
    else if (data.type === 'draft_updated') {
      const d = data.data || {}
      const isRoom = d.booking_type === 'room' || d.check_in_date || d.room_type || d.guest_email
      const isDining = d.booking_type === 'dining' || d.seating_type || d.reservation_time

      if (isRoom) {
        setActiveFormType('room')
        setRoomDraft((prev) => ({
          ...prev,
          guest_name: d.guest_name || d.customer_name || prev.guest_name,
          guest_email: d.guest_email || prev.guest_email,
          guest_phone: d.guest_phone || d.customer_phone || prev.guest_phone,
          check_in_date: d.check_in_date || prev.check_in_date,
          check_out_date: d.check_out_date || prev.check_out_date,
          room_type: d.room_type || prev.room_type,
          guests_count: d.guests_count || d.guests || prev.guests_count,
          additional_guests: d.additional_guest_names || d.additional_guests || prev.additional_guests,
        }))
      }

      if (isDining) {
        setActiveFormType('dining')
        setDiningDraft((prev) => ({
          ...prev,
          customer_name: d.customer_name || d.guest_name || prev.customer_name,
          customer_phone: d.customer_phone || d.guest_phone || prev.customer_phone,
          reservation_date: d.reservation_date || prev.reservation_date,
          reservation_time: d.reservation_time || prev.reservation_time,
          party_size: d.party_size || prev.party_size,
          seating_type: d.seating_type || prev.seating_type,
        }))
      }
    }

    // 3. Turn complete
    else if (data.type === 'turn_complete') {
      if (isHearingRef.current) {
        setTimeout(() => {
          if (isHearingRef.current && nextPlayTimeRef.current <= (outputAudioContextRef.current?.currentTime || 0) + 0.1) {
            setAgentState('listening')
          }
        }, 300)
      }
    }

    // 4. Speech Transcript
    else if (data.type === 'transcript') {
      addLog(`🤖 ${data.text}`, 'ai')
    }

    // 5. Tool execution & Booking Confirmation
    else if (data.type === 'tool_executed') {
      if (data.tool === 'update_draft_details') {
        // Handled silently for smooth visual sync
        return
      }

      setAgentState('thinking')
      if (data.result?.status === 'success') {
        const isRoom = data.tool === 'book_room'
        const title = isRoom ? '🏨 Room Booked' : '🍽️ Table Reserved'
        const resId = data.result.reservation_id

        addLog(`✅ ${title}: #${resId}`, 'success')

        if (isRoom) {
          const dt = data.result.details || {}
          setRoomDraft((prev) => ({
            ...prev,
            ...dt,
            status: 'confirmed',
            reservation_id: resId,
          }))
          setActiveFormType('room')
        } else {
          const dt = data.result.details || {}
          setDiningDraft((prev) => ({
            ...prev,
            ...dt,
            status: 'confirmed',
            reservation_id: resId,
          }))
          setActiveFormType('dining')
        }

        setReservations((prev) => [
          {
            id: resId,
            type: data.tool,
            details: data.result.details || data.args,
            timestamp: new Date().toLocaleTimeString(),
          },
          ...prev,
        ])
      } else {
        addLog(`❌ Action failed: ${data.result?.message || 'Error executing booking'}`, 'error')
      }
    }

    // 6. Security Guardrail Alert (Input & Output Filter Violations)
    else if (data.type === 'security_alert') {
      addLog(`🛡️ [SECURITY INTERVENTION] ${data.guardrail.toUpperCase()} Guardrail: ${data.reason}`, 'error')
      setSecurityAlerts((prev) => [
        {
          timestamp: new Date().toLocaleTimeString(),
          guardrail: data.guardrail,
          attack_type: data.attack_type,
          reason: data.reason,
        },
        ...prev,
      ])
    }
  }

  // --- Microphone Capture (Guaranteed 16,000 Hz PCM Int16) ---
  const startMicrophone = async () => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext
      try {
        inputAudioContextRef.current = new AudioCtx({ sampleRate: 16000 })
      } catch {
        inputAudioContextRef.current = new AudioCtx()
      }

      if (inputAudioContextRef.current.state === 'suspended') {
        await inputAudioContextRef.current.resume()
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      micStreamRef.current = stream

      const source = inputAudioContextRef.current.createMediaStreamSource(stream)
      const processor = inputAudioContextRef.current.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        if (!isHearingRef.current) return

        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const rawFloat32 = e.inputBuffer.getChannelData(0)

          // Downsample to 16kHz
          const float32Data = downsampleBuffer(
            rawFloat32,
            inputAudioContextRef.current.sampleRate,
            16000
          )

          // RMS volume level for aura reactivity
          let sum = 0
          for (let i = 0; i < float32Data.length; i += 4) {
            sum += float32Data[i] * float32Data[i]
          }
          const rms = Math.sqrt(sum / (float32Data.length / 4 || 1))
          if (agentState !== 'speaking') {
            setAudioLevel(Math.min(1.0, rms * 5.0))
          }

          // Convert Float32 to Int16 PCM
          const pcmData = new Int16Array(float32Data.length)
          for (let i = 0; i < float32Data.length; i++) {
            pcmData[i] = Math.max(-1, Math.min(1, float32Data[i])) * 0x7fff
          }

          wsRef.current.send(pcmData.buffer)
        }
      }

      source.connect(processor)
      const dummyGain = inputAudioContextRef.current.createGain()
      dummyGain.gain.value = 0
      processor.connect(dummyGain)
      dummyGain.connect(inputAudioContextRef.current.destination)
    } catch (err) {
      console.error(err)
      addLog(`Microphone error: ${err.message}`, 'error')
    }
  }

  // --- Speaker Playback (24kHz PCM Int16 from Gemini Live) ---
  const playAudioChunk = (arrayBuffer) => {
    if (!outputAudioContextRef.current) return

    const ctx = outputAudioContextRef.current
    if (ctx.state === 'suspended') {
      ctx.resume()
    }

    const pcmData = new Int16Array(arrayBuffer)
    const float32Data = new Float32Array(pcmData.length)
    let sum = 0
    for (let i = 0; i < pcmData.length; i++) {
      const sample = pcmData[i] / 0x7fff
      float32Data[i] = sample
      if (i % 4 === 0) sum += sample * sample
    }

    const rms = Math.sqrt(sum / (pcmData.length / 4 || 1))
    setAudioLevel(Math.min(1.0, rms * 5.0))
    setAgentState('speaking')

    // 24kHz buffer played through output context at 1.0x normal speed
    const audioBuffer = ctx.createBuffer(1, float32Data.length, 24000)
    audioBuffer.getChannelData(0).set(float32Data)

    const source = ctx.createBufferSource()
    source.buffer = audioBuffer
    source.connect(ctx.destination)

    const currentTime = ctx.currentTime
    if (nextPlayTimeRef.current < currentTime) {
      nextPlayTimeRef.current = currentTime
    }

    source.start(nextPlayTimeRef.current)
    nextPlayTimeRef.current += audioBuffer.duration

    activeSourcesRef.current.push(source)
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source)
      if (activeSourcesRef.current.length === 0 && ctx.currentTime >= nextPlayTimeRef.current - 0.05) {
        if (isHearingRef.current) {
          setAgentState('listening')
          setAudioLevel(0)
        } else {
          setAgentState('idle')
        }
      }
    }
  }

  const stopAllAudio = () => {
    activeSourcesRef.current.forEach((src) => {
      try {
        src.stop()
      } catch {}
    })
    activeSourcesRef.current = []
    if (outputAudioContextRef.current) {
      nextPlayTimeRef.current = outputAudioContextRef.current.currentTime
    }
    setAudioLevel(0)
  }

  // Stop Hearing / Start Hearing toggle without disconnecting
  const toggleHearing = () => {
    if (!isConnected) return

    if (isHearing) {
      setIsHearing(false)
      isHearingRef.current = false
      setAgentState('idle')
      setAudioLevel(0)
      addLog('⏸️ Stopped hearing: Assistant is muted (Conversation preserved)', 'warning')
    } else {
      setIsHearing(true)
      isHearingRef.current = true
      setAgentState('listening')
      addLog('🎙️ Resumed hearing: Assistant is listening', 'info')
    }
  }

  const stopConversation = () => {
    if (wsRef.current) {
      wsRef.current.close()
    }
    stopMicrophone()
    stopAllAudio()
    if (outputAudioContextRef.current) {
      try {
        outputAudioContextRef.current.close()
      } catch {}
      outputAudioContextRef.current = null
    }
    setIsConnected(false)
    setAgentState('idle')
    setIsHearing(true)
    isHearingRef.current = true
  }

  const stopMicrophone = () => {
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop())
      micStreamRef.current = null
    }
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }
    if (inputAudioContextRef.current) {
      try {
        inputAudioContextRef.current.close()
      } catch {}
      inputAudioContextRef.current = null
    }
  }

  const resetForm = (type) => {
    if (type === 'room') {
      setRoomDraft({
        guest_name: '',
        guest_email: '',
        guest_phone: '',
        check_in_date: '',
        check_out_date: '',
        room_type: '',
        guests_count: '',
        additional_guests: '',
        status: 'drafting',
      })
    } else {
      setDiningDraft({
        customer_name: '',
        customer_phone: '',
        reservation_date: '',
        reservation_time: '',
        party_size: '',
        seating_type: '',
        status: 'drafting',
      })
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0a0b10',
        color: '#e4e7eb',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '20px 24px',
        boxSizing: 'border-box',
      }}
    >
      {/* Top Header */}
      <header
        style={{
          width: '100%',
          maxWidth: '1200px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingBottom: '16px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          marginBottom: '20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #1FD5F9 0%, #7928CA 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(31, 213, 249, 0.35)',
              fontSize: '18px',
            }}
          >
            🏨
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#ffffff', letterSpacing: '-0.3px' }}>
              Grand Luxe Concierge
            </h1>
            <p style={{ margin: 0, fontSize: '12px', color: '#8892b0' }}>
              Multi-Agent Real-time Voice Reservation Assistant
            </p>
          </div>
        </div>

        {/* Header Right Actions & Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Security Guardrails Indicator */}
          <div
            title="Two-Tier Input/Output Classifiers Active"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '20px',
              backgroundColor: securityAlerts.length > 0 ? 'rgba(235, 87, 87, 0.15)' : 'rgba(46, 213, 115, 0.1)',
              border: `1px solid ${securityAlerts.length > 0 ? 'rgba(235, 87, 87, 0.4)' : 'rgba(46, 213, 115, 0.3)'}`,
              fontSize: '12px',
              fontWeight: 500,
              color: securityAlerts.length > 0 ? '#eb5757' : '#2ed573',
            }}
          >
            <span>🛡️</span>
            <span>
              {securityAlerts.length > 0
                ? `${securityAlerts.length} Threat${securityAlerts.length > 1 ? 's' : ''} Blocked`
                : 'Guardrails Active'}
            </span>
          </div>

          {/* Status Pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 14px',
              borderRadius: '20px',
              backgroundColor: isConnected
                ? isHearing
                  ? agentState === 'speaking'
                    ? 'rgba(121, 40, 202, 0.25)'
                    : 'rgba(31, 213, 249, 0.15)'
                  : 'rgba(255, 171, 0, 0.15)'
                : 'rgba(255, 255, 255, 0.05)',
              border: `1px solid ${
                isConnected
                  ? isHearing
                    ? agentState === 'speaking'
                      ? '#7928CA'
                      : '#1FD5F9'
                    : '#ffab00'
                  : 'rgba(255, 255, 255, 0.1)'
              }`,
              fontSize: '13px',
              fontWeight: 500,
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isConnected
                  ? isHearing
                    ? agentState === 'speaking'
                      ? '#b872ff'
                      : '#1FD5F9'
                    : '#ffab00'
                  : '#666',
                boxShadow: isConnected ? `0 0 8px currentColor` : 'none',
                animation: isConnected ? 'pulse 2s infinite' : 'none',
              }}
            />
            <span style={{ color: isConnected ? '#ffffff' : '#888' }}>
              {!isConnected
                ? 'Disconnected'
                : !isHearing
                ? 'Paused (Not Hearing)'
                : agentState === 'speaking'
                ? 'Assistant Speaking...'
                : agentState === 'thinking'
                ? 'Processing Reservation...'
                : 'Listening...'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Two-Column Stage */}
      <main
        style={{
          width: '100%',
          maxWidth: '1200px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '24px',
          alignItems: 'start',
        }}
      >
        {/* LEFT COLUMN: Voice Assistant Stage & Aura */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
          }}
        >
          {/* Visualizer Aura */}
          <div
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '360px',
              height: '360px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(31, 213, 249, 0.05) 0%, rgba(10, 11, 16, 0) 70%)',
            }}
          >
            <AgentAudioVisualizerAura
              size="xl"
              color="#1FD5F9"
              colorShift={0.3}
              state={agentState}
              audioLevel={audioLevel}
              themeMode="dark"
              className="aspect-square size-auto w-full"
            />
            <div
              style={{
                position: 'absolute',
                bottom: '20px',
                padding: '5px 14px',
                borderRadius: '16px',
                backgroundColor: 'rgba(10, 11, 16, 0.8)',
                backdropFilter: 'blur(8px)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                fontSize: '11px',
                letterSpacing: '0.5px',
                textTransform: 'uppercase',
                color: '#1FD5F9',
                fontWeight: 600,
              }}
            >
              {isConnected ? agentState : 'Ready'}
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
            {!isConnected ? (
              <button
                onClick={startConversation}
                style={{
                  background: 'linear-gradient(135deg, #1FD5F9 0%, #0070F3 100%)',
                  color: '#ffffff',
                  border: 'none',
                  padding: '12px 28px',
                  borderRadius: '30px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: '0 4px 18px rgba(31, 213, 249, 0.35)',
                }}
              >
                <span>🎙️</span> Start Voice Conversation
              </button>
            ) : (
              <>
                <button
                  onClick={toggleHearing}
                  style={{
                    background: isHearing
                      ? 'rgba(255, 171, 0, 0.15)'
                      : 'linear-gradient(135deg, #1FD5F9 0%, #0070F3 100%)',
                    color: isHearing ? '#ffab00' : '#ffffff',
                    border: isHearing ? '1px solid #ffab00' : 'none',
                    padding: '11px 24px',
                    borderRadius: '30px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: !isHearing ? '0 0 14px rgba(31, 213, 249, 0.35)' : 'none',
                  }}
                >
                  <span>{isHearing ? '⏸️' : '▶️'}</span>
                  {isHearing ? 'Stop Hearing' : 'Start Hearing'}
                </button>

                <button
                  onClick={stopConversation}
                  style={{
                    background: 'rgba(235, 87, 87, 0.15)',
                    color: '#eb5757',
                    border: '1px solid rgba(235, 87, 87, 0.4)',
                    padding: '11px 20px',
                    borderRadius: '30px',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <span>⏹️</span> End Call
                </button>
              </>
            )}
          </div>

          {/* Prompt chips */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center' }}>
            {[
              'I want to book a Deluxe room for next weekend',
              'Reserve a dinner table for 4 tonight with window seating',
            ].map((p, i) => (
              <div
                key={i}
                style={{
                  fontSize: '11px',
                  padding: '5px 10px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#8f9bb3',
                }}
              >
                💬 "{p}"
              </div>
            ))}
          </div>

          {/* Transcript Box */}
          <div
            style={{
              width: '100%',
              backgroundColor: '#11131a',
              borderRadius: '14px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              padding: '14px 16px',
              height: '180px',
              display: 'flex',
              flexDirection: 'column',
              boxSizing: 'border-box',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#ffffff' }}>Live Voice Activity</span>
              <span style={{ fontSize: '11px', color: '#666' }}>{logs.length} items</span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {logs.length === 0 ? (
                <div style={{ color: '#555', fontSize: '12px', margin: 'auto' }}>
                  Voice transcript and system updates appear here.
                </div>
              ) : (
                logs.map((log, idx) => (
                  <div
                    key={idx}
                    style={{
                      fontSize: '12px',
                      lineHeight: '1.4',
                      color:
                        log.type === 'error'
                          ? '#eb5757'
                          : log.type === 'warning'
                          ? '#ffab00'
                          : log.type === 'success'
                          ? '#1FD5F9'
                          : log.type === 'ai'
                          ? '#c4b5fd'
                          : '#8f9bb3',
                      display: 'flex',
                      gap: '8px',
                    }}
                  >
                    <span style={{ fontSize: '10px', opacity: 0.5, minWidth: '50px' }}>{log.time}</span>
                    <span>{log.msg}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Real-Time Live Input Form + Confirmed Bookings */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Live Form Card */}
          <div
            style={{
              backgroundColor: '#11131a',
              borderRadius: '16px',
              border: '1px solid rgba(31, 213, 249, 0.25)',
              padding: '20px',
              boxShadow: '0 4px 24px rgba(0, 0, 0, 0.4)',
            }}
          >
            {/* Form Header Tabs */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setActiveFormType('room')}
                  style={{
                    backgroundColor: activeFormType === 'room' ? 'rgba(31, 213, 249, 0.15)' : 'transparent',
                    border: `1px solid ${activeFormType === 'room' ? '#1FD5F9' : 'rgba(255, 255, 255, 0.1)'}`,
                    color: activeFormType === 'room' ? '#1FD5F9' : '#8892b0',
                    padding: '6px 14px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  🏨 Room Booking
                </button>
                <button
                  onClick={() => setActiveFormType('dining')}
                  style={{
                    backgroundColor: activeFormType === 'dining' ? 'rgba(31, 213, 249, 0.15)' : 'transparent',
                    border: `1px solid ${activeFormType === 'dining' ? '#1FD5F9' : 'rgba(255, 255, 255, 0.1)'}`,
                    color: activeFormType === 'dining' ? '#1FD5F9' : '#8892b0',
                    padding: '6px 14px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  🍽️ Dining Booking
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    padding: '3px 8px',
                    borderRadius: '10px',
                    backgroundColor:
                      (activeFormType === 'room' ? roomDraft.status : diningDraft.status) === 'confirmed'
                        ? 'rgba(46, 213, 115, 0.2)'
                        : 'rgba(31, 213, 249, 0.15)',
                    color:
                      (activeFormType === 'room' ? roomDraft.status : diningDraft.status) === 'confirmed'
                        ? '#2ed573'
                        : '#1FD5F9',
                    fontWeight: 600,
                  }}
                >
                  {(activeFormType === 'room' ? roomDraft.status : diningDraft.status) === 'confirmed'
                    ? '✅ Confirmed'
                    : '🔄 Live Inputs'}
                </span>
                <button
                  onClick={() => resetForm(activeFormType)}
                  title="Clear inputs"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#666',
                    cursor: 'pointer',
                    fontSize: '12px',
                  }}
                >
                  ↺ Reset
                </button>
              </div>
            </div>

            {/* Confirmation Banner if Booked */}
            {activeFormType === 'room' && roomDraft.status === 'confirmed' && (
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(46, 213, 115, 0.12)',
                  border: '1px solid rgba(46, 213, 115, 0.35)',
                  marginBottom: '16px',
                  fontSize: '12px',
                  lineHeight: '1.5',
                  color: '#2ed573',
                }}
              >
                🎉 <strong>Your room has been booked!</strong>
                <br />
                Reservation ID: <strong>#{roomDraft.reservation_id}</strong>
                <br />
                Receipt & confirmation will be sent shortly to{' '}
                <strong>{roomDraft.guest_email || 'your email'}</strong>.
              </div>
            )}

            {activeFormType === 'dining' && diningDraft.status === 'confirmed' && (
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(46, 213, 115, 0.12)',
                  border: '1px solid rgba(46, 213, 115, 0.35)',
                  marginBottom: '16px',
                  fontSize: '12px',
                  lineHeight: '1.5',
                  color: '#2ed573',
                }}
              >
                🎉 <strong>Your dining table has been reserved!</strong>
                <br />
                Reservation ID: <strong>#{diningDraft.reservation_id}</strong>
                <br />
                Seating preference: <strong>{diningDraft.seating_type || 'Any'}</strong>.
              </div>
            )}

            {/* LIVE FORM FIELDS DISPLAY */}
            {activeFormType === 'room' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <FieldRow
                  label="Guest Full Name"
                  value={roomDraft.guest_name}
                  placeholder="e.g. John Doe"
                  required
                />
                <FieldRow
                  label="Email (for Receipt)"
                  value={roomDraft.guest_email}
                  placeholder="e.g. john@example.com"
                  required
                />
                <FieldRow
                  label="Phone Number"
                  value={roomDraft.guest_phone}
                  placeholder="e.g. +1 555-0199"
                  required
                />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <FieldRow
                    label="Check-In Date"
                    value={roomDraft.check_in_date}
                    placeholder="YYYY-MM-DD"
                    required
                  />
                  <FieldRow
                    label="Check-Out Date"
                    value={roomDraft.check_out_date}
                    placeholder="YYYY-MM-DD"
                    required
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <FieldRow
                    label="Room Type"
                    value={roomDraft.room_type}
                    placeholder="e.g. Deluxe Suite"
                    required
                  />
                  <FieldRow
                    label="Total Guests"
                    value={roomDraft.guests_count}
                    placeholder="e.g. 2"
                    required
                  />
                </div>

                {/* Additional Guests Names (Asked if guests > 1) */}
                <FieldRow
                  label="Additional Guest Names (if guests > 1)"
                  value={roomDraft.additional_guests}
                  placeholder={
                    roomDraft.guests_count > 1
                      ? 'e.g. Jane Doe, Alex Smith'
                      : 'None required for solo guest'
                  }
                  highlight={roomDraft.guests_count > 1 && !roomDraft.additional_guests}
                />
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <FieldRow
                  label="Customer Name"
                  value={diningDraft.customer_name}
                  placeholder="e.g. John Doe"
                  required
                />
                <FieldRow
                  label="Phone Number"
                  value={diningDraft.customer_phone}
                  placeholder="e.g. +1 555-0199"
                  required
                />
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <FieldRow
                    label="Reservation Date"
                    value={diningDraft.reservation_date}
                    placeholder="YYYY-MM-DD"
                    required
                  />
                  <FieldRow
                    label="Reservation Time"
                    value={diningDraft.reservation_time}
                    placeholder="e.g. 19:30 or 7:30 PM"
                    required
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <FieldRow
                    label="Party Size"
                    value={diningDraft.party_size}
                    placeholder="e.g. 4 people"
                    required
                  />
                  <FieldRow
                    label="Seating Type"
                    value={diningDraft.seating_type}
                    placeholder="indoor / outdoor / window / any"
                    required
                  />
                </div>
                <div
                  style={{
                    fontSize: '11px',
                    color: '#8892b0',
                    fontStyle: 'italic',
                    padding: '6px 10px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  }}
                >
                  ℹ️ Guest names are not required for dining reservations.
                </div>
              </div>
            )}
          </div>

          {/* Confirmed Bookings History */}
          {reservations.length > 0 && (
            <div
              style={{
                backgroundColor: '#11131a',
                borderRadius: '16px',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                padding: '16px',
                maxHeight: '220px',
                overflowY: 'auto',
              }}
            >
              <h3 style={{ margin: '0 0 10px 0', fontSize: '13px', fontWeight: 600, color: '#ffffff' }}>
                Confirmed Bookings History ({reservations.length})
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {reservations.map((res, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                      <span style={{ fontWeight: 600, color: '#ffffff' }}>
                        {res.type === 'book_room' ? '🏨 Hotel Room' : '🍽️ Dining Table'}
                      </span>
                      <span style={{ color: '#1FD5F9', fontWeight: 600 }}>ID #{res.id}</span>
                    </div>
                    <div style={{ color: '#8892b0', fontSize: '11px', lineHeight: '1.4' }}>
                      {res.type === 'book_room' ? (
                        <>
                          Guest: {res.details.guest_name} ({res.details.guest_email || 'No email'}) | Room: {res.details.room_type}
                          <br />
                          Dates: {res.details.check_in} to {res.details.check_out} | Guests: {res.details.guests}
                          {res.details.additional_guests && res.details.additional_guests !== 'None' && (
                            <> | Other Guests: {res.details.additional_guests}</>
                          )}
                        </>
                      ) : (
                        <>
                          Customer: {res.details.customer_name} ({res.details.customer_phone}) | Party: {res.details.party_size}
                          <br />
                          Time: {res.details.reservation_date} at {res.details.reservation_time} | Seating: {res.details.seating_type || 'any'}
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

// Reusable live input field row
function FieldRow({ label, value, placeholder, required = false, highlight = false }) {
  const isFilled = value !== '' && value !== undefined && value !== null
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        padding: '8px 10px',
        borderRadius: '8px',
        backgroundColor: isFilled ? 'rgba(31, 213, 249, 0.05)' : 'rgba(255, 255, 255, 0.02)',
        border: `1px solid ${
          isFilled
            ? 'rgba(31, 213, 249, 0.3)'
            : highlight
            ? 'rgba(255, 171, 0, 0.4)'
            : 'rgba(255, 255, 255, 0.06)'
        }`,
        transition: 'all 0.2s ease',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '11px', color: '#8892b0', fontWeight: 500 }}>
          {label} {required && <span style={{ color: '#eb5757' }}>*</span>}
        </span>
        <span style={{ fontSize: '11px' }}>
          {isFilled ? (
            <span style={{ color: '#2ed573' }}>✓ Filled</span>
          ) : (
            <span style={{ color: highlight ? '#ffab00' : '#555' }}>
              {highlight ? '⚠️ Needed' : 'Waiting...'}
            </span>
          )}
        </span>
      </div>
      <div
        style={{
          fontSize: '13px',
          fontWeight: isFilled ? 600 : 400,
          color: isFilled ? '#ffffff' : '#666',
          fontFamily: isFilled ? 'Inter, sans-serif' : 'monospace',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {isFilled ? value : placeholder}
      </div>
    </div>
  )
}
