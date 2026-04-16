import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

// ── Datas das sugestões ───────────────────────────────────────
const MONTHS = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
const fmt     = d => `${d.getDate()} ${MONTHS[d.getMonth()]}`
const fmtFull = d =>
  `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`
const addDays = (d, n) => new Date(d.getTime() + n * 86_400_000)

function buildChips() {
  const nm  = new Date(); nm.setDate(1); nm.setMonth(nm.getMonth() + 1)
  const nm2 = new Date(nm); nm2.setMonth(nm2.getMonth() + 1)
  return [
    { label: `🗼  Paris   ·   ${fmt(nm)} – ${fmt(addDays(nm, 7))}`,                   msg: `Paris, de ${fmtFull(nm)} a ${fmtFull(addDays(nm, 7))}` },
    { label: `🏖️  Cancún   ·   ${fmt(addDays(nm, 14))} – ${fmt(addDays(nm, 21))}`,    msg: `Cancún, de ${fmtFull(addDays(nm, 14))} a ${fmtFull(addDays(nm, 21))}` },
    { label: `🌸  Tóquio   ·   ${fmt(nm2)} – ${fmt(addDays(nm2, 10))}`,               msg: `Tóquio, de ${fmtFull(nm2)} a ${fmtFull(addDays(nm2, 10))}` },
  ]
}
const CHIPS = buildChips()

// ── Conversa ──────────────────────────────────────────────────
function createConv() {
  return { id: crypto.randomUUID(), sessionId: crypto.randomUUID(), title: 'Nova conversa', messages: [] }
}
const _init = createConv()

// ── Markdown leve ─────────────────────────────────────────────
function md(raw) {
  const inline = s =>
    s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
     .replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
  const lines = raw.split('\n')
  const out = []
  let inUl = false, inOl = false
  const closeList = () => {
    if (inUl) { out.push('</ul>'); inUl = false }
    if (inOl) { out.push('</ol>'); inOl = false }
  }
  for (const line of lines) {
    const t = line.trim()
    if (!t) { closeList(); out.push('<br>'); continue }
    const ul = t.match(/^[-*•]\s+(.+)/)
    if (ul) {
      if (inOl) { out.push('</ol>'); inOl = false }
      if (!inUl) { out.push('<ul>'); inUl = true }
      out.push(`<li>${inline(ul[1])}</li>`); continue
    }
    const ol = t.match(/^\d+\.\s+(.+)/)
    if (ol) {
      if (inUl) { out.push('</ul>'); inUl = false }
      if (!inOl) { out.push('<ol>'); inOl = true }
      out.push(`<li>${inline(ol[1])}</li>`); continue
    }
    if (/^#{1,3}\s+/.test(t)) {
      closeList()
      out.push(`<p class="md-heading">${inline(t.replace(/^#{1,3}\s+/, ''))}</p>`)
      continue
    }
    closeList()
    out.push(`<p>${inline(t)}</p>`)
  }
  closeList()
  return out.join('')
}

// ── Sidebar ───────────────────────────────────────────────────
function Sidebar({ open, onClose, convs, currentId, onSelect, onNew, pending }) {
  return (
    <>
      <div className={`backdrop ${open ? 'visible' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${open ? 'open' : ''}`}>

        <div className="sidebar-hd">
          <span className="sidebar-title">Histórico</span>
          <button className="sidebar-close-btn" onClick={onClose} aria-label="Fechar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div className="sidebar-new">
          <button className="sidebar-new-btn" onClick={onNew} disabled={pending}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Nova conversa
          </button>
        </div>

        <div className="sidebar-list">
          {convs.length === 0 && (
            <p className="sidebar-empty">Nenhuma conversa ainda.</p>
          )}
          {[...convs].reverse().map(conv => (
            <button
              key={conv.id}
              className={`conv-item ${conv.id === currentId ? 'active' : ''}`}
              onClick={() => onSelect(conv.id)}
            >
              <svg className="conv-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              <div className="conv-text">
                <span className="conv-title">{conv.title}</span>
                {conv.messages.length > 0 && (
                  <span className="conv-meta">{conv.messages.length} mensagem{conv.messages.length !== 1 ? 's' : ''}</span>
                )}
              </div>
            </button>
          ))}
        </div>

      </aside>
    </>
  )
}

// ── Bolhas de mensagem ────────────────────────────────────────
function UserBubble({ content }) {
  return (
    <div className="msg msg-user">
      <div className="bubble">{content}</div>
    </div>
  )
}

function BotBubble({ content, historical }) {
  return (
    <div className="msg msg-bot">
      <div className="av">✈️</div>
      <div className="bot-content">
        {historical && (
          <div className="warn">
            📅 Dados baseados em histórico climático. Verifique a previsão real quando a viagem estiver próxima.
          </div>
        )}
        <div className="bubble" dangerouslySetInnerHTML={{ __html: md(content) }} />
      </div>
    </div>
  )
}

function TypingBubble() {
  return (
    <div className="msg msg-bot">
      <div className="av">✈️</div>
      <div className="bubble typing">
        <span className="dot" /><span className="dot" /><span className="dot" />
      </div>
    </div>
  )
}

function EmptyState({ onChip }) {
  return (
    <div className="empty">
      <span className="plane">✈️</span>
      <h2>Para onde você vai?</h2>
      <p>Me diga o destino e as datas.<br />Vou te contar o que vestir!</p>
      <div className="chips">
        {CHIPS.map(c => (
          <button key={c.label} className="chip" onClick={() => onChip(c.msg)}>
            {c.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────
export default function App() {
  const [convs,       setConvs]       = useState([_init])
  const [currentId,   setCurrentId]   = useState(_init.id)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [pending,     setPending]     = useState(false)
  const [dark,        setDark]        = useState(
    () => (localStorage.getItem('vf-theme') ?? 'dark') === 'dark'
  )
  const [input, setInput] = useState('')

  const bottomRef   = useRef(null)
  const textareaRef = useRef(null)

  const current  = convs.find(c => c.id === currentId) ?? convs[0]
  const messages = current.messages

  useEffect(() => {
    const theme = dark ? 'dark' : 'light'
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('vf-theme', theme)
  }, [dark])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pending])

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [input])

  useEffect(() => {
    const handler = e => { if (e.key === 'Escape') setSidebarOpen(false) }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const send = useCallback(async (text) => {
    const trimmed = text.trim()
    if (!trimmed || pending) return

    setInput('')

    setConvs(prev => prev.map(c => c.id === currentId ? {
      ...c,
      title:    c.title === 'Nova conversa' ? trimmed.slice(0, 42) : c.title,
      messages: [...c.messages, { role: 'user', content: trimmed }],
    } : c))

    setPending(true)

    try {
      const res = await fetch('/chat', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ session_id: current.sessionId, message: trimmed }),
      })
      if (!res.ok) throw new Error('http ' + res.status)
      const data = await res.json()
      setConvs(prev => prev.map(c => c.id === currentId ? {
        ...c,
        messages: [...c.messages, {
          role:       'assistant',
          content:    data.reply,
          historical: data.used_historical ?? false,
        }],
      } : c))
    } catch {
      setConvs(prev => prev.map(c => c.id === currentId ? {
        ...c,
        messages: [...c.messages, {
          role:       'assistant',
          content:    'Não consegui conectar ao servidor. Tente novamente em instantes. 🔌',
          historical: false,
        }],
      } : c))
    } finally {
      setPending(false)
    }
  }, [pending, currentId, current.sessionId])

  const newConversation = useCallback(() => {
    if (pending) return
    if (current.messages.length === 0) {
      setSidebarOpen(false)
      return
    }
    const conv = createConv()
    setConvs(prev => [...prev, conv])
    setCurrentId(conv.id)
    setInput('')
    setSidebarOpen(false)
  }, [pending, current.messages.length])

  const switchConv = useCallback((id) => {
    if (pending) return
    setCurrentId(id)
    setInput('')
    setSidebarOpen(false)
  }, [pending])

  const handleKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="app">

      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        convs={convs}
        currentId={currentId}
        onSelect={switchConv}
        onNew={newConversation}
        pending={pending}
      />

      {/* ── Header ── */}
      <header className="header">
        <div className="header-left">
          <button
            className="menu-btn"
            onClick={() => setSidebarOpen(o => !o)}
            aria-label="Abrir histórico"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="3" y1="6"  x2="21" y2="6"/>
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
          <div className="logo">✈️</div>
          <div className="title-block">
            <span className="title">ViajaFácil</span>
            <span className="subtitle">conselheiro de vestimentas para viagens</span>
          </div>
        </div>
        <div className="header-actions">
          <button className="reset-btn" onClick={newConversation} disabled={pending} title="Nova conversa">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
              <path d="M3 3v5h5"/>
            </svg>
            Nova conversa
          </button>
          <button className="theme-btn" onClick={() => setDark(d => !d)}>
            <span className="theme-track">
              <span className="theme-thumb">{dark ? '🌙' : '☀️'}</span>
            </span>
            <span className="theme-label">{dark ? 'Escuro' : 'Claro'}</span>
          </button>
        </div>
      </header>

      {/* ── Mensagens ── */}
      <main className="messages">
        <div className="messages-inner">
          {messages.length === 0 && !pending && (
            <EmptyState onChip={msg => send(msg)} />
          )}
          {messages.map((m, i) =>
            m.role === 'user'
              ? <UserBubble key={i} content={m.content} />
              : <BotBubble  key={i} content={m.content} historical={m.historical} />
          )}
          {pending && <TypingBubble />}
          <div ref={bottomRef} />
        </div>
      </main>

      {/* ── Input ── */}
      <div className="input-bar">
        <div className="input-row">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ex: Vou para Lisboa de 10 a 20 de maio…"
            rows={1}
            disabled={pending}
          />
          <button
            className="send-btn"
            onClick={() => send(input)}
            disabled={!input.trim() || pending}
            aria-label="Enviar"
          >
            ↑
          </button>
        </div>
      </div>

    </div>
  )
}
