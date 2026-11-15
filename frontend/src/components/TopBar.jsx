// Validated responsive layout, theme switches, and country search
import Icon from './Icon.jsx'

const LOGO = [
  '#fee08b',
  '#f99b2b',
  '#c64a05',
  '#fdc050',
  '#ea6f12',
  '#f99b2b',
  '#fee08b',
  '#fdc050',
  '#fee08b',
]
const SEARCH = 'M21 21l-4.3-4.3M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14z'
const SUN =
  'M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6l1.4 1.4m10 10l1.4 1.4M5.6 18.4l1.4-1.4m10-10l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z'
const MOON = 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z'

export default function TopBar({ countries, query, miss, onQuery, onPick, onWorld, theme, onTheme }) {
  return (
    <div className="bar">
      <div className="brand">
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="7" fill="#16150f" />
          <g>
            {LOGO.map((c, i) => (
              <rect
                key={i}
                x={5 + (i % 3) * 8}
                y={6 + Math.floor(i / 3) * 7.5}
                width="6"
                height="5"
                rx="1"
                fill={c}
              />
            ))}
          </g>
        </svg>
        <span>Burning Activity Calendar</span>
      </div>
      <form
        className="search"
        role="search"
        onSubmit={(ev) => {
          ev.preventDefault()
          onPick(query)
        }}
      >
        <Icon d={SEARCH} />
        <input
          list="places"
          placeholder="Search a country…"
          aria-label="Search a country"
          value={query}
          onChange={(ev) => {
            onQuery(ev.target.value)
            // Typing only fills the box (Enter looks it up), but a suggestion chosen from the list is looked up at
            // once: it arrives as a replacement, not as typing.
            const type = ev.nativeEvent.inputType
            if (!type || type === 'insertReplacementText') onPick(ev.target.value, true)
          }}
        />
        <datalist id="places">
          {countries?.map((c) => (
            <option key={c.id} value={c.name} />
          ))}
        </datalist>
        <span className="miss" role="status">
          {miss && 'No country by that name'}
        </span>
      </form>
      <div className="grow" />
      <button className="btn ghost hide-s" onClick={onWorld}>
        World
      </button>
      <a
        className="btn ghost hide-s"
        href="#evidence"
        onClick={(ev) => {
          ev.preventDefault()
          document.getElementById('evidence').scrollIntoView()
        }}
      >
        How we know
      </a>
      <button
        className="btn icon"
        aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
        onClick={onTheme}
      >
        <Icon d={theme === 'dark' ? SUN : MOON} />
      </button>
    </div>
  )
}
