export default function Fragmento({ texto }) {
  return texto.split(/(\[\[.*?\]\])/).map((parte, i) =>
    parte.startsWith('[[') ? <mark key={i}>{parte.slice(2, -2)}</mark> : parte,
  )
}
