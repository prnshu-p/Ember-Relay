export const STORIES = [
  { title: 'Black Summer', sub: 'Australia · Dec 2019', area: 'box:140,-39,154,-28', month: '2019-12' },
  { title: 'California megafires', sub: 'Sep 2020', area: 'box:-124.5,32.5,-114,42', month: '2020-09' },
  { title: "Canada's record season", sub: 'Jun 2023', area: 'country:canada', month: '2023-06' },
  { title: 'Indonesian haze', sub: 'Sep 2015', area: 'country:indonesia', month: '2015-09' },
  { title: 'Greece, before VIIRS', sub: 'Aug 2007 · estimated', area: 'country:greece', month: '2007-08' },
  { title: 'Amazon arc of fire', sub: 'Sep 2007 · estimated', area: 'box:-70,-15,-45,0', month: '2007-09' },
  { title: 'Siberia', sub: 'Jul 2021', area: 'box:105,58,140,72', month: '2021-07' },
  { title: 'Portugal', sub: 'Oct 2017', area: 'country:portugal', month: '2017-10' },
  {
    title: 'Córdoba sierras',
    sub: 'Argentina · Sep 2013',
    area: 'box:-65.75,-35,-61.75,-29.5',
    month: '2013-09',
  },
  { title: "Zambia's dry season", sub: 'every Aug–Sep', area: 'country:zambia', month: null },
]

// The data keeps its ids and its dated names; the app shows today's names and finds a country by any of them.
const NAMES = {
  'russian-federation': 'Russia',
  'cote-d-ivoire': "Côte d'Ivoire",
  'dem-rep-korea': 'North Korea',
  'republic-of-korea': 'South Korea',
  'lao-pdr': 'Laos',
  swaziland: 'Eswatini',
  'macedonia-former-yugoslav-republic-of': 'North Macedonia',
  'czech-republic': 'Czechia',
  'republic-of-congo': 'Republic of the Congo',
  reunion: 'Réunion',
  'aland-islands': 'Åland Islands',
  'faeroe-islands': 'Faroe Islands',
  'heard-i-and-mcdonald-islands': 'Heard Island and McDonald Islands',
  curacao: 'Curaçao',
  'brunei-darussalam': 'Brunei',
  'saint-barthelemy': 'Saint Barthélemy',
}
const ALIAS = {
  usa: 'united-states',
  us: 'united-states',
  'united-states-of-america': 'united-states',
  america: 'united-states',
  uk: 'united-kingdom',
  'great-britain': 'united-kingdom',
  britain: 'united-kingdom',
  'ivory-coast': 'cote-d-ivoire',
  turkiye: 'turkey',
  'dr-congo': 'democratic-republic-of-the-congo',
  drc: 'democratic-republic-of-the-congo',
  'congo-kinshasa': 'democratic-republic-of-the-congo',
  congo: 'republic-of-congo',
  'congo-brazzaville': 'republic-of-congo',
  burma: 'myanmar',
  'east-timor': 'timor-leste',
  'cabo-verde': 'cape-verde',
  gambia: 'the-gambia',
  macedonia: 'macedonia-former-yugoslav-republic-of',
  dprk: 'dem-rep-korea',
  korea: 'republic-of-korea',
  micronesia: 'federated-states-of-micronesia',
  'the-bahamas': 'bahamas',
  'st-lucia': 'saint-lucia',
  'st-kitts-and-nevis': 'saint-kitts-and-nevis',
  'st-vincent-and-the-grenadines': 'saint-vincent-and-the-grenadines',
  england: 'united-kingdom',
  'u-s-a': 'united-states',
  'u-s': 'united-states',
  'u-k': 'united-kingdom',
  uae: 'united-arab-emirates',
  holland: 'netherlands',
  'viet-nam': 'vietnam',
  lao: 'lao-pdr',
  bosnia: 'bosnia-and-herzegovina',
  'slovak-republic': 'slovakia',
  'kyrgyz-republic': 'kyrgyzstan',
  'syrian-arab-republic': 'syria',
}

export const withTodaysNames = (countries) =>
  countries.map((c) => (NAMES[c.id] ? { ...c, name: NAMES[c.id] } : c))

// the form of the ids: "Côte d'Ivoire" -> 'cote-d-ivoire'
export const slug = (s) =>
  s
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')

// a country by its name, a former or everyday name, or the start of one
export function findCountry(countries, query) {
  const k = slug(query)
  if (!k || !countries) return null
  return (
    countries.find((c) => c.id === (ALIAS[k] || k) || slug(c.name) === k) ||
    countries.find((c) => slug(c.name).startsWith(k) || c.id.startsWith(k))
  )
}
