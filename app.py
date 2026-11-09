"""NYC permits and street safety: interactive Dash dashboard.

Run locally:   python app.py        (then open http://127.0.0.1:8050)
Production:    gunicorn app:server
"""
import os
import re
import textwrap

import numpy as np
import pandas as pd
import plotly.io as pio
from dash import Dash, Input, Output, State, dcc, html, no_update

import charts
from search import PERMIT_LABELS, describe, parse_query

pio.templates.default = 'plotly_white'

# --------------------------------------------------------------------------- data
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'integrated_clean.csv')
df_all = pd.read_csv(DATA_PATH, dtype={'zip_code': str}, parse_dates=['year_month'])

BOROUGHS = charts.BOROUGH_ORDER
YEARS = sorted(int(y) for y in df_all['year'].unique())
ZIPS = sorted(df_all['zip_code'].unique())
VALID_ZIPS = set(ZIPS)
PERMIT_OPTIONS = [{'label': lbl, 'value': key} for key, lbl in PERMIT_LABELS.items()]
CRASH_OPTIONS = [{'label': 'All crashes', 'value': 'all'},
                 {'label': 'Crashes with at least one injury', 'value': 'injury'}]
CRASH_LABELS = {'all': 'all crashes', 'injury': 'injury crashes only'}


def apply_filters(df, boroughs, years, permit, crash, zips):
    """Apply the dashboard filters. Empty dropdown = no filter on that field."""
    d = df
    if boroughs:
        d = d[d['borough'].isin(boroughs)]
    if years:
        d = d[d['year'].isin(years)]
    if zips:
        d = d[d['zip_code'].isin(zips)]
    d = d.copy()
    if permit and permit != 'all':
        d['permits'] = d[permit]                       # housing category: count only this permit group
    if crash == 'injury':
        d['crashes'] = d['injury_crashes']             # transportation category: only crashes with injuries
    return d


# --------------------------------------------------------------------------- figures
QUESTIONS = [
    ('q1', 'Q1. Do ZIP codes with more permits also have more crashes?', charts.fig_q1,
     'Each dot is a ZIP code. Both axes are log scales. Busy ZIPs tend to have more of everything, so this is a baseline.'),
    ('q2', 'Q2. In months when a ZIP has more permits than usual, does it also have more crashes than usual?', charts.fig_q2,
     'Each ZIP is compared with itself and with the city trend that month. Bars near zero with error bars crossing zero mean no clear link.'),
    ('q3', 'Q3. Which kind of permit activity moves with pedestrian injuries?', charts.fig_q3,
     'Spearman correlation per permit group, after adjusting for each ZIP\'s usual level and the city trend. Values near 0 mean no detectable link.'),
    ('q4', 'Q4. Where do permit-heavy and crash-heavy ZIPs sit on the city map?', charts.fig_q4,
     'Bubble size is the number of crashes, colour is the number of permits. Hover for the ZIP code and borough.'),
    ('q5', 'Q5. Is the permits-crashes link the same in every borough and year?', charts.fig_q5,
     'Each cell is a Spearman correlation across ZIP codes. Needs at least 8 ZIPs per borough and year, so narrow filters can leave it empty.'),
    ('q6', 'Q6. Do permits and crashes follow the same seasonal rhythm?', charts.fig_q6,
     'Each calendar month is shown relative to an average month (100). Same months from different years are pooled.'),
    ('q7', 'Q7. Did ZIPs whose permit activity grew see crashes fall less?', charts.fig_q7,
     'Percentage change from the first to the last selected year, for ZIPs with at least 50 permits and 50 crashes in the first year. Needs two or more years. 2023-24 crashes are slightly undercounted (see limitations).'),
    ('q8', 'Q8. Are crashes more injurious in ZIP-months with costlier projects?', charts.fig_q8,
     'ZIP-months with 5 or more crashes, grouped into quartiles of the median permit cost. Cost covers all permit types.'),
    ('q9', 'Q9. Do pedestrians and cyclists make up a bigger share of injuries in permit-heavy ZIPs?', charts.fig_q9,
     'ZIP codes are split into thirds by total permits. Bars show the share of injured people who were pedestrians or cyclists.'),
    ('q10', 'Q10. Which ZIPs are double hotspots?', charts.fig_q10,
     'Red dots are in the top quarter of ZIP codes for both permits and crashes. Dotted lines mark the quarter cut-offs.'),
]
WIDE = {'q4', 'q10'}


def wrap_title(fig, suffix):
    """Wrap the long chart title onto several lines and append the active filter note."""
    t = fig.layout.title.text or ''
    if suffix:
        t = f'{t} [{suffix}]'
    fig.update_layout(title=dict(text='<br>'.join(textwrap.wrap(t, 70)), font=dict(size=13), x=0.01, xanchor='left'),
                      margin=dict(t=90, l=50, r=20, b=50), height=440)
    return fig


def safe_fig(fn, d, suffix):
    try:
        return wrap_title(fn(d), suffix)
    except Exception as exc:                                    # keep the page alive if one chart fails
        return wrap_title(charts.empty_fig('This chart could not be drawn for this filter'), '')


def kpi(label, value):
    return html.Div([html.Div(value, className='kpi-value'), html.Div(label, className='kpi-label')], className='kpi')


def fmt(n):
    return f'{int(n):,}'


def build_report(boroughs, years, permit, crash, zips):
    """Return (figures, kpi_children, note_text) for the chosen filters."""
    d = apply_filters(df_all, boroughs, years, permit, crash, zips)
    suffix_parts = []
    if permit and permit != 'all':
        suffix_parts.append('permits: ' + PERMIT_LABELS[permit])
    if crash == 'injury':
        suffix_parts.append('injury crashes only')
    suffix = '; '.join(suffix_parts)

    def label(values, everything):
        return ', '.join(str(v).title() if isinstance(v, str) else str(v) for v in values) if values else everything

    note = (f"Showing: {label(boroughs, 'all boroughs')} | {label(years, 'all years (2023-2025)')} | "
            f"{PERMIT_LABELS.get(permit, PERMIT_LABELS['all'])} | {CRASH_LABELS.get(crash, 'all crashes')} | "
            f"{'ZIP ' + ', '.join(zips) if zips else 'all ZIP codes'}.")

    if d.empty:
        figs = [wrap_title(charts.empty_fig('No data for this filter combination'), '') for _ in QUESTIONS]
        kpis = [kpi('ZIP codes', '0'), kpi('Permits', '0'), kpi('Crashes', '0'), kpi('People injured', '0')]
        return figs, kpis, note + ' No data matches. Clear a filter and click Generate Report again.'

    figs = [safe_fig(fn, d, suffix) for _, _, fn, _ in QUESTIONS]
    active_zips = d.groupby('zip_code')[['permits', 'crashes']].sum()
    kpis = [kpi('ZIP codes', fmt(d['zip_code'].nunique())), kpi('Permits issued', fmt(d['permits'].sum())),
            kpi('Crashes', fmt(d['crashes'].sum())), kpi('People injured', fmt(d['persons_injured'].sum()))]
    both = active_zips[(active_zips['permits'] > 0) & (active_zips['crashes'] > 0)]
    if len(both) >= 5:
        rho = both['permits'].corr(both['crashes'], method='spearman')
        note += f' Across the {len(both)} ZIP codes with both permits and crashes, the Spearman correlation is {rho:.2f}.'
    return figs, kpis, note


# --------------------------------------------------------------------------- layout
def card(qid, title, hint):
    return html.Div([
        html.H3(title, className='q-title'),
        html.P(hint, className='q-hint'),
        dcc.Graph(id=f'g-{qid}', config={'displaylogo': False, 'responsive': True}, style={'height': '440px'}),
    ], className='card wide' if qid in WIDE else 'card')


STORY = html.Section([
    html.H2('Our story'),
    html.Div([
        html.Div([html.H4('The question'),
                  html.P('Do ZIP codes with more construction and renovation permit activity also have more '
                         'street-safety problems (crashes and injuries)? We joined NYC DOB NOW approved permits with '
                         'NYPD motor vehicle collisions at the ZIP code by month level, January 2023 to December 2025.')]),
        html.Div([html.H4('Key findings'),
                  html.Ul([
                      html.Li('Across ZIP codes, more permits goes with more crashes (Spearman 0.75). Busy places have more of everything, so this is mostly size.'),
                      html.Li('Month to month, a ZIP\'s permit surges do not line up with its own crash surges (Spearman -0.01). No permit type stood out for pedestrian injuries.'),
                      html.Li('The ZIP-level link is strong in Manhattan (0.83-0.88) and Queens (0.77-0.83), and clearly weaker in Brooklyn (0.29-0.44), in all three years.'),
                  ])]),
        html.Div([html.H4('Limitations'),
                  html.Ul([
                      html.Li('Associations only. Nothing here shows that permits cause crashes.'),
                      html.Li('ZIP codes differ in size and population, and counts are not per person.'),
                      html.Li('About 7% of crashes could not be placed in a ZIP and were dropped, mostly in 2023-24, so those years are slightly undercounted.'),
                      html.Li('Permits issued are planned work, not completed buildings. Project costs repeat across a job\'s permits.'),
                  ])]),
        html.Div([html.H4('So what for NYC'),
                  html.P('Permit activity alone is a weak signal for when crashes will spike in a neighbourhood. '
                         'For street-safety planning, the double hotspots (Q10) are the ZIP codes where heavy construction '
                         'activity and many crashes overlap, a sensible place to start looking, alongside other factors '
                         'such as traffic volume and population that this data does not include.')]),
    ], className='story-grid'),
], className='story')

app = Dash(__name__, title='NYC Permits and Street Safety')
server = app.server          # gunicorn app:server

app.layout = html.Div([
    html.Header([
        html.H1('NYC construction activity and street safety'),
        html.P('Do ZIP codes with more building permits also have more crashes? Explore 2023-2025 data from NYC Open Data '
               '(DOB NOW approved permits and NYPD motor vehicle collisions), joined at ZIP code and month.'),
    ], className='hero'),

    STORY,

    html.Section([
        html.H2('Explore the data'),
        html.Div([
            html.Label('Search', htmlFor='search'),
            dcc.Input(id='search', type='text', debounce=True, className='search',
                      placeholder='Try: Brooklyn 2024 scaffolds injury   (press Enter)'),
            html.Div(id='search-msg', className='search-msg'),
        ], className='search-row'),
        html.Div([
            html.Div([html.Label('Borough'), dcc.Dropdown(id='f-borough', multi=True, placeholder='All boroughs',
                                                          options=[{'label': b.title(), 'value': b} for b in BOROUGHS])]),
            html.Div([html.Label('Year'), dcc.Dropdown(id='f-year', multi=True, placeholder='All years',
                                                       options=[{'label': str(y), 'value': y} for y in YEARS])]),
            html.Div([html.Label('Permit type (housing)'), dcc.Dropdown(id='f-permit', clearable=False, value='all',
                                                                        options=PERMIT_OPTIONS)]),
            html.Div([html.Label('Crash type (transportation)'), dcc.Dropdown(id='f-crash', clearable=False, value='all',
                                                                              options=CRASH_OPTIONS)]),
            html.Div([html.Label('ZIP code'), dcc.Dropdown(id='f-zip', multi=True, placeholder='All ZIP codes',
                                                           options=[{'label': z, 'value': z} for z in ZIPS])]),
        ], className='filters'),
        html.Button('Generate Report', id='generate', n_clicks=0, className='generate'),
        html.P('Filters and search only take effect when you click Generate Report.', className='fine'),
    ], className='controls'),

    dcc.Loading(html.Section([
        html.Div(id='kpis', className='kpis'),
        html.P(id='report-note', className='report-note'),
        html.Div([card(qid, title, hint) for qid, title, _, hint in QUESTIONS], className='grid'),
    ]), type='circle'),

    html.Footer('Data: NYC Open Data, DOB NOW: Build Approved Permits (rbx6-tga4) and Motor Vehicle Collisions Crashes '
                '(h9gi-nx95). Cleaned and integrated for the Data Engineering and Visualization course project.',
                className='footer'),
])


# --------------------------------------------------------------------------- callbacks
@app.callback(
    Output('f-borough', 'value'), Output('f-year', 'value'), Output('f-permit', 'value'),
    Output('f-crash', 'value'), Output('f-zip', 'value'), Output('search-msg', 'children'),
    Input('search', 'value'),
    prevent_initial_call=True,
)
def apply_search(query):
    """Search mode: type a query, and the filters above are set for you."""
    if not query or not query.strip():
        return no_update, no_update, no_update, no_update, no_update, ''
    filters, notes = parse_query(query, VALID_ZIPS)
    return (filters['boroughs'] or [], filters['years'] or [], filters['permit'], filters['crash'],
            filters['zips'] or [], describe(filters, notes))


@app.callback(
    [Output(f'g-{qid}', 'figure') for qid, *_ in QUESTIONS] + [Output('kpis', 'children'), Output('report-note', 'children')],
    Input('generate', 'n_clicks'),
    State('f-borough', 'value'), State('f-year', 'value'), State('f-permit', 'value'),
    State('f-crash', 'value'), State('f-zip', 'value'),
)
def generate_report(_clicks, boroughs, years, permit, crash, zips):
    figs, kpis, note = build_report(boroughs or [], years or [], permit or 'all', crash or 'all', zips or [])
    return figs + [kpis, note]


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 8050)), debug=False)
