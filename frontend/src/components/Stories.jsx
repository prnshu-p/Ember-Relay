import { STORIES } from '../lib/places.js'

export default function Stories({ area, sel, onPick }) {
  return (
    <div className="stories" role="group" aria-label="Places and months worth a look">
      {STORIES.map((s) => (
        <button
          key={s.title}
          className={`story${area === s.area && sel === s.month ? ' on' : ''}`}
          onClick={() => onPick(s)}
        >
          <b>{s.title}</b>
          <span>{s.sub}</span>
        </button>
      ))}
    </div>
  )
}
