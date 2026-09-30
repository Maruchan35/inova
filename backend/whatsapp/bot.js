// Bot de avisos por WhatsApp de CabildoAbierto.
//
// Usa una cuenta NORMAL de WhatsApp vinculada como "dispositivo" (igual que WhatsApp Web). Automatizar una
// cuenta normal va contra las reglas de WhatsApp y el número puede ser bloqueado: usa un chip de repuesto.
//
//   cd backend/whatsapp  →  npm install  →  npm start
//   La primera vez abre http://127.0.0.1:3001/qr y escanéalo desde el teléfono:
//   WhatsApp → Dispositivos vinculados → Vincular un dispositivo. La sesión queda en ./sesion (no se sube a Git).
//
// El backend le pide enviar mensajes por HTTP local (POST /enviar). El bot los manda en fila, con pausas,
// para no parecer spam. Si alguien responde "BAJA", le avisa al backend para darlo de baja.

import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import makeWASocket, { DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } from '@whiskeysockets/baileys'
import QRCode from 'qrcode'

const AQUI = path.dirname(fileURLToPath(import.meta.url))

// libsignal (dependencia de Baileys) imprime sesiones completas, con llaves privadas: nunca deben quedar en un log.
const SECRETO = /^(Closing session|Closing open session|Removing old closed session|Decrypted message with closed session|Session error|Failed to decrypt)/
for (const metodo of ['log', 'info', 'warn', 'error']) {
  const original = console[metodo].bind(console)
  console[metodo] = (...args) => { if (!(typeof args[0] === 'string' && SECRETO.test(args[0]))) original(...args) }
}

// Misma configuración que el backend: backend/.env (las variables del entorno tienen prioridad).
const ENV = path.join(AQUI, '..', '.env')
if (fs.existsSync(ENV)) {
  for (const linea of fs.readFileSync(ENV, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/)
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '')
  }
}
const PUERTO = Number(process.env.WHATSAPP_BOT_PUERTO || 3001)
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8000'
const TOKEN = process.env.WHATSAPP_BOT_TOKEN || ''
const PAUSA_MS = [4000, 9000] // entre mensaje y mensaje, al azar

const silencio = { level: 'silent', child() { return this }, trace() {}, debug() {}, info() {}, warn() {}, error() {}, fatal() {} }
let sock = null
let estado = { conectado: false, numero: null, qr: null }
const fila = []
let enviando = false

async function conectar() {
  const { state, saveCreds } = await useMultiFileAuthState(path.join(AQUI, 'sesion'))
  const { version } = await fetchLatestBaileysVersion()
  sock = makeWASocket({ version, auth: state, logger: silencio, browser: ['CabildoAbierto', 'Chrome', '1.0'], markOnlineOnConnect: false })
  sock.ev.on('creds.update', saveCreds)
  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      estado = { conectado: false, numero: null, qr }
      console.log(`Escanea el QR para vincular el número: http://127.0.0.1:${PUERTO}/qr`)
    }
    if (connection === 'open') {
      estado = { conectado: true, numero: sock.user?.id?.split(':')[0].split('@')[0] ?? null, qr: null }
      console.log(`Conectado como ${estado.numero}`)
      mandarSiguiente()
    }
    if (connection === 'close') {
      estado.conectado = false
      const codigo = lastDisconnect?.error?.output?.statusCode
      if (codigo === DisconnectReason.loggedOut) {
        console.log('Se cerró la sesión desde el teléfono. Borra la carpeta sesion/ y vuelve a escanear el QR.')
      } else {
        console.log(`Conexión cerrada (${codigo ?? 'sin código'}); reconectando…`)
        setTimeout(conectar, 3000)
      }
    }
  })
  sock.ev.on('messages.upsert', ({ messages, type }) => {
    if (type !== 'notify') return
    for (const m of messages) atenderMensaje(m).catch((e) => console.log('Error al leer un mensaje:', e.message))
  })
}

// "BAJA" → el backend desactiva sus avisos. El número puede venir como @s.whatsapp.net o, en cuentas nuevas, como @lid.
async function atenderMensaje(m) {
  if (m.key.fromMe) return
  const texto = (m.message?.conversation || m.message?.extendedTextMessage?.text || '').trim().toUpperCase()
  if (texto !== 'BAJA') return
  const jid = [m.key.remoteJid, m.key.remoteJidAlt, m.key.senderPn].find((j) => j?.endsWith('@s.whatsapp.net'))
  if (!jid) {
    await sock.sendMessage(m.key.remoteJid, { text: 'No pude identificar tu número. Escríbenos desde la página para darte de baja.' })
    return
  }
  const r = await fetch(`${BACKEND}/api/interno/baja`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Bot-Token': TOKEN },
    body: JSON.stringify({ telefono: jid.split('@')[0] }),
  })
  const texto_respuesta = r.ok
    ? 'Listo, ya no te enviaremos avisos. Si quieres volver a recibirlos, suscríbete de nuevo en la página.'
    : 'No pudimos darte de baja en este momento. Inténtalo más tarde.'
  await sock.sendMessage(m.key.remoteJid, { text: texto_respuesta })
}

// Un número de México puede estar registrado en WhatsApp como 52 + 10 dígitos o como 521 + 10 dígitos.
async function jidDe(telefono) {
  const diez = telefono.slice(-10)
  for (const candidato of [telefono, `52${diez}`, `521${diez}`]) {
    const [r] = (await sock.onWhatsApp(candidato)) || []
    if (r?.exists) return r.jid
  }
  return null
}

async function mandarSiguiente() {
  if (enviando || !estado.conectado || !fila.length) return
  enviando = true
  const { telefono, texto } = fila.shift()
  try {
    const jid = await jidDe(telefono)
    if (jid) {
      await sock.sendMessage(jid, { text: texto })
      console.log(`Enviado a ${telefono.slice(0, 4)}******${telefono.slice(-2)}`)
    } else {
      console.log(`El número ${telefono.slice(0, 4)}******${telefono.slice(-2)} no tiene WhatsApp`)
    }
  } catch (e) {
    console.log('No se pudo enviar:', e.message)
  }
  const [min, max] = PAUSA_MS
  setTimeout(() => { enviando = false; mandarSiguiente() }, min + Math.random() * (max - min))
}

function responder(res, estatus, datos, tipo = 'application/json') {
  res.writeHead(estatus, { 'Content-Type': `${tipo}; charset=utf-8` })
  res.end(tipo === 'application/json' ? JSON.stringify(datos) : datos)
}

http.createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/estado') {
    return responder(res, 200, { conectado: estado.conectado, numero: estado.numero, pendientes: fila.length })
  }
  if (req.method === 'GET' && req.url === '/qr') {
    if (estado.conectado) return responder(res, 200, `<h2 style="font-family:sans-serif">Ya está vinculado (${estado.numero}).</h2>`, 'text/html')
    if (!estado.qr) return responder(res, 200, '<h2 style="font-family:sans-serif">Esperando el QR… recarga en unos segundos.</h2>', 'text/html')
    const svg = await QRCode.toString(estado.qr, { type: 'svg', margin: 2, width: 320 })
    return responder(res, 200, `<meta http-equiv="refresh" content="20"><div style="font-family:sans-serif;text-align:center">
      <h2>Vincula el WhatsApp que mandará los avisos</h2><p>WhatsApp → Dispositivos vinculados → Vincular un dispositivo</p>
      <div style="width:320px;margin:auto">${svg}</div><p>El código cambia cada 20 segundos; esta página se actualiza sola.</p></div>`, 'text/html')
  }
  if (req.method === 'POST' && req.url === '/enviar') {
    if (TOKEN && req.headers['x-bot-token'] !== TOKEN) return responder(res, 403, { detail: 'Token inválido' })
    let cuerpo = ''
    for await (const parte of req) cuerpo += parte
    try {
      const { telefono, texto } = JSON.parse(cuerpo)
      if (!/^\d{12,13}$/.test(telefono) || !texto) return responder(res, 400, { detail: 'Falta teléfono (52 + 10 dígitos) o texto' })
      if (!estado.conectado) return responder(res, 503, { detail: 'El WhatsApp no está vinculado' })
      fila.push({ telefono, texto })
      mandarSiguiente()
      return responder(res, 202, { encolado: true, pendientes: fila.length })
    } catch {
      return responder(res, 400, { detail: 'JSON inválido' })
    }
  }
  responder(res, 404, { detail: 'No existe' })
}).listen(PUERTO, '127.0.0.1', () => console.log(`Bot de WhatsApp escuchando en http://127.0.0.1:${PUERTO}`))

conectar()
