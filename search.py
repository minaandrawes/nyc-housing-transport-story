"""Search mode: turn a typed query such as "Brooklyn 2024 scaffolds injury" into dashboard filters."""
import re

BOROUGH_WORDS = {
    'bronx': 'BRONX',
    'brooklyn': 'BROOKLYN',
    'manhattan': 'MANHATTAN',
    'queens': 'QUEENS',
    'staten island': 'STATEN ISLAND',
    'statenisland': 'STATEN ISLAND',
}

# Permit group keywords. Checked in this order; the first group that matches is used.
PERMIT_WORDS = [
    ('permits_systems', ['building systems', 'systems', 'plumbing', 'mechanical', 'solar', 'boiler', 'boilers',
                         'sprinkler', 'sprinklers', 'standpipe', 'antenna', 'green roof']),
    ('permits_site_safety', ['site safety', 'safety', 'shed', 'sheds', 'scaffold', 'scaffolds', 'scaffolding',
                             'fence', 'fences', 'temporary']),
    ('permits_construction', ['construction', 'structural', 'foundation', 'demolition', 'excavation',
                              'building', 'buildings']),
    ('permits_other', ['sign', 'signs', 'curb', 'curb cut', 'other']),
]

PERMIT_LABELS = {
    'all': 'All permit types',
    'permits_construction': 'Construction & structural',
    'permits_systems': 'Building systems & equipment',
    'permits_site_safety': 'Site safety & temporary',
    'permits_other': 'Other (signs, curb cuts)',
}

INJURY_WORDS = ['injury', 'injuries', 'injured', 'hurt']
IGNORED = {'in', 'the', 'and', 'for', 'with', 'of', 'a', 'an', 'show', 'me', 'permits', 'permit', 'crashes',
           'crash', 'collisions', 'collision', 'zip', 'code', 'codes', 'only', 'to', 'at', 'on', 'new'}

YEARS_AVAILABLE = (2023, 2024, 2025)


def _find(text, phrase):
    """Whole-word / whole-phrase match; returns the matched span or None."""
    m = re.search(r'(?<![a-z0-9])' + re.escape(phrase) + r'(?![a-z0-9])', text)
    return m.span() if m else None


def parse_query(query, valid_zips):
    """Return (filters, notes). filters keys: boroughs, years, permit, crash, zips."""
    text = (query or '').lower()
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    used = [False] * len(text)
    notes = {'ignored': [], 'unavailable_years': [], 'unknown_zips': [], 'permit_conflict': []}

    def mark(span):
        for i in range(span[0], span[1]):
            used[i] = True

    boroughs = []
    for word, name in BOROUGH_WORDS.items():
        span = _find(text, word)
        if span:
            mark(span)
            if name not in boroughs:
                boroughs.append(name)

    years = []
    for tok in re.finditer(r'(?<![0-9])(20[0-9]{2})(?![0-9])', text):
        mark(tok.span())
        y = int(tok.group(1))
        if y in YEARS_AVAILABLE:
            if y not in years:
                years.append(y)
        else:
            notes['unavailable_years'].append(y)

    zips = []
    for tok in re.finditer(r'(?<![0-9])(1[01][0-9]{3})(?![0-9])', text):
        mark(tok.span())
        z = tok.group(1)
        if z in valid_zips:
            if z not in zips:
                zips.append(z)
        else:
            notes['unknown_zips'].append(z)

    permit_hits = []
    for col, words in PERMIT_WORDS:
        for w in sorted(words, key=len, reverse=True):          # longest phrase first
            span = _find(text, w)
            if span and not any(used[span[0]:span[1]]):
                mark(span)
                if col not in permit_hits:
                    permit_hits.append(col)
    permit = permit_hits[0] if permit_hits else 'all'
    notes['permit_conflict'] = permit_hits[1:]

    crash = 'all'
    for w in INJURY_WORDS:
        span = _find(text, w)
        if span:
            mark(span)
            crash = 'injury'

    leftover = ''.join(ch if not used[i] else ' ' for i, ch in enumerate(text)).split()
    notes['ignored'] = [t for t in leftover if t not in IGNORED]

    filters = {'boroughs': boroughs, 'years': years, 'permit': permit, 'crash': crash, 'zips': zips}
    return filters, notes


def describe(filters, notes):
    """One readable sentence saying what the search understood."""
    parts = []
    if filters['boroughs']:
        parts.append(', '.join(b.title() for b in filters['boroughs']))
    if filters['years']:
        parts.append(', '.join(str(y) for y in filters['years']))
    if filters['zips']:
        parts.append('ZIP ' + ', '.join(filters['zips']))
    if filters['permit'] != 'all':
        parts.append(PERMIT_LABELS[filters['permit']])
    if filters['crash'] == 'injury':
        parts.append('injury crashes only')
    msg = 'Applied: ' + ' | '.join(parts) + '.' if parts else 'No filters recognized, showing everything.'
    extras = []
    if notes['unavailable_years']:
        extras.append('years not in the data (2023-2025): ' + ', '.join(map(str, notes['unavailable_years'])))
    if notes['unknown_zips']:
        extras.append('ZIPs not in the data: ' + ', '.join(notes['unknown_zips']))
    if notes['permit_conflict']:
        extras.append('used the first permit type, also saw: ' +
                      ', '.join(PERMIT_LABELS[c] for c in notes['permit_conflict']))
    if notes['ignored']:
        extras.append('ignored words: ' + ', '.join(notes['ignored']))
    if extras:
        msg += ' (' + '; '.join(extras) + ')'
    return msg + ' Click Generate Report to update the charts.'
