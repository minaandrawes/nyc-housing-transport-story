"""Chart functions for the NYC permits vs crashes dashboard.
Each function takes a (filtered) DataFrame of ZIP x month rows and returns a Plotly figure."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

BOROUGH_ORDER = ['BRONX', 'BROOKLYN', 'MANHATTAN', 'QUEENS', 'STATEN ISLAND']


def empty_fig(msg):
    """Placeholder chart when a filter leaves too little data."""
    fig = go.Figure()
    fig.update_layout(title=msg, xaxis={'visible': False}, yaxis={'visible': False})
    return fig


def adjusted(df, col):
    """Standardize `col` within each ZIP (z-score), then subtract the city-wide average for that month.
    Positive = busier than this ZIP's usual AND busier than the city trend that month."""
    g = df.groupby('zip_code')[col]
    std = g.transform('std').replace(0, np.nan)          # ZIPs with no variation have no z-score
    z = (df[col] - g.transform('mean')) / std
    return z - z.groupby(df['year_month']).transform('mean')


# ---------------- Q1: permits vs crashes per ZIP (totals) ----------------
def fig_q1(df):
    zt = df.groupby(['zip_code', 'borough'], as_index=False)[['permits', 'crashes']].sum()
    zt = zt[(zt['permits'] > 0) & (zt['crashes'] > 0)]
    if len(zt) < 5:
        return empty_fig('Not enough ZIP codes for this filter')
    rho = zt['permits'].corr(zt['crashes'], method='spearman')
    return px.scatter(zt, x='permits', y='crashes', color='borough', hover_name='zip_code',
                      log_x=True, log_y=True, category_orders={'borough': BOROUGH_ORDER},
                      title=f'Q1: Permits vs crashes per ZIP (log scales, Spearman rho = {rho:.2f}, {len(zt)} ZIPs)',
                      labels={'permits': 'Permits issued (total)', 'crashes': 'Crashes (total)', 'borough': 'Borough'})


# ---------------- Q2: busier-than-usual permit months vs crashes ----------------
def fig_q2(df):
    d = df.copy()
    d['permits_adj'] = adjusted(d, 'permits')
    d['crashes_adj'] = adjusted(d, 'crashes')
    d = d.dropna(subset=['permits_adj', 'crashes_adj'])
    if len(d) < 50:
        return empty_fig('Not enough data for this filter')
    rho = d['permits_adj'].corr(d['crashes_adj'], method='spearman')
    labels = ['Lowest 20%', 'Low', 'Middle', 'High', 'Highest 20%']
    d['permit_level'] = pd.qcut(d['permits_adj'].rank(method='first'), 5, labels=labels)  # rank avoids tie errors
    s = d.groupby('permit_level', observed=True)['crashes_adj'].agg(['mean', 'sem']).reset_index()
    return px.bar(s, x='permit_level', y='mean', error_y='sem',
                  title=f'Q2: Crashes vs permit activity, each ZIP compared with itself and the city (rho = {rho:.2f})',
                  labels={'permit_level': 'Permit activity that month (vs the ZIP usual)',
                          'mean': 'Crashes vs usual (standardized, 0 = typical)'})


# ---------------- Q3: which permit group moves with pedestrian injuries ----------------
def fig_q3(df):
    groups = {'permits_construction': 'Construction & structural',
              'permits_systems': 'Building systems & equipment',
              'permits_site_safety': 'Site safety & temporary',
              'permits_other': 'Other (signs, curb cuts)'}
    y = adjusted(df, 'pedestrians_injured')
    rows = [{'permit group': label, 'rho': adjusted(df, col).corr(y, method='spearman')}
            for col, label in groups.items()]
    r = pd.DataFrame(rows).dropna()
    if r.empty:
        return empty_fig('Not enough data for this filter')
    return px.bar(r, x='permit group', y='rho', text_auto='.3f',
                  title='Q3: Link between each permit type and pedestrian injuries (Spearman rho, ZIP-month)',
                  labels={'rho': 'Spearman rho', 'permit group': 'Permit group'})


# ---------------- Q4: map, permits (colour) and crashes (size) per ZIP ----------------
def fig_q4(df):
    z = df.groupby('zip_code').agg(permits=('permits', 'sum'), crashes=('crashes', 'sum'),
                                   latitude=('latitude', 'first'), longitude=('longitude', 'first'),
                                   borough=('borough', 'first')).reset_index()
    z = z.dropna(subset=['latitude', 'longitude'])
    z = z[(z['permits'] + z['crashes']) > 0]
    if z.empty:
        return empty_fig('No ZIP codes for this filter')
    kwargs = dict(lat='latitude', lon='longitude', size='crashes', color='permits', hover_name='zip_code',
                  hover_data={'borough': True, 'permits': True, 'crashes': True, 'latitude': False, 'longitude': False},
                  size_max=28, zoom=9.2, center={'lat': 40.72, 'lon': -73.95},
                  color_continuous_scale='Viridis',
                  title='Q4: ZIP codes, bubble size = crashes, colour = permits issued',
                  labels={'permits': 'Permits', 'crashes': 'Crashes'})
    if hasattr(px, 'scatter_map'):
        fig = px.scatter_map(z, map_style='carto-positron', **kwargs)    # free tiles, no token needed
    else:
        fig = px.scatter_mapbox(z, mapbox_style='carto-positron', **kwargs)
    fig.update_layout(margin={'l': 0, 'r': 0, 'b': 0})
    return fig


# ---------------- Q5: permits-crashes link by borough and year ----------------
def fig_q5(df):
    zy = df.groupby(['borough', 'zip_code', 'year'], as_index=False)[['permits', 'crashes']].sum()
    rows = []
    for (b, yr), g in zy.groupby(['borough', 'year']):
        if len(g) >= 8 and g['permits'].nunique() > 1 and g['crashes'].nunique() > 1:
            rows.append({'borough': b, 'year': int(yr), 'rho': g['permits'].corr(g['crashes'], method='spearman')})
    if not rows:
        return empty_fig('Not enough ZIP codes per borough for this filter')
    r = pd.DataFrame(rows).pivot(index='borough', columns='year', values='rho')
    fig = px.imshow(r, text_auto='.2f', color_continuous_scale='RdBu_r', zmin=-1, zmax=1, aspect='auto',
                    title='Q5: Spearman correlation of ZIP permits vs crashes, by borough and year',
                    labels={'color': 'Spearman rho', 'x': 'Year', 'y': 'Borough'})
    fig.update_xaxes(type='category')
    return fig


MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# ---------------- Q6: seasonal rhythm ----------------
def fig_q6(df):
    g = df.groupby('month')[['permits', 'crashes']].sum()
    if len(g) < 3 or (g.mean() == 0).any():
        return empty_fig('Not enough data for this filter')
    idx = (g / g.mean() * 100).reset_index()                  # 100 = an average month
    rho = idx['permits'].corr(idx['crashes'], method='spearman')
    long = idx.melt(id_vars='month', value_vars=['permits', 'crashes'],
                    var_name='measure', value_name='monthly_index')
    long['measure'] = long['measure'].map({'permits': 'Permits issued', 'crashes': 'Crashes'})
    fig = px.line(long, x='month', y='monthly_index', color='measure', markers=True,
                  title=f'Q6: Seasonal pattern, calendar months pooled (100 = average month, rho = {rho:.2f})',
                  labels={'month': 'Calendar month', 'monthly_index': 'Index (100 = average month)', 'measure': ''})
    fig.update_xaxes(tickmode='array', tickvals=list(range(1, 13)), ticktext=MONTH_NAMES)
    return fig

# ---------------- Q7: change over time, permits vs crashes ----------------
def q7_data(df):
    if df.empty:
        return None, None, None
    y0, y1 = int(df['year'].min()), int(df['year'].max())
    if y0 == y1:
        return None, y0, y1
    a = df[df['year'] == y0].groupby(['zip_code', 'borough'])[['permits', 'crashes']].sum()
    b = df[df['year'] == y1].groupby(['zip_code', 'borough'])[['permits', 'crashes']].sum()
    z = a.join(b, lsuffix='_first', rsuffix='_last', how='inner').reset_index()
    z = z[(z['permits_first'] >= 50) & (z['crashes_first'] >= 50)].copy()   # avoid noisy % from tiny bases
    z['permit_change'] = (z['permits_last'] / z['permits_first'] - 1) * 100
    z['crash_change'] = (z['crashes_last'] / z['crashes_first'] - 1) * 100
    return z, y0, y1

def fig_q7(df):
    z, y0, y1 = q7_data(df)
    if z is None:
        return empty_fig('Needs data from at least two different years for this filter')
    if len(z) < 10:
        return empty_fig('Not enough ZIP codes for this filter')
    rho = z['permit_change'].corr(z['crash_change'], method='spearman')
    fig = px.scatter(z, x='permit_change', y='crash_change', color='borough', hover_name='zip_code',
                     category_orders={'borough': BOROUGH_ORDER},
                     title=f'Q7: Change {y0} to {y1}, permits vs crashes per ZIP (rho = {rho:.2f}, {len(z)} ZIPs)',
                     labels={'permit_change': f'Change in permits {y0} to {y1} (%, axis trimmed)',
                             'crash_change': f'Change in crashes {y0} to {y1} (%, axis trimmed)',
                             'borough': 'Borough'})
    fig.add_hline(y=0, line_dash='dot', line_color='gray')
    fig.add_vline(x=0, line_dash='dot', line_color='gray')
    for axis, col in (('x', 'permit_change'), ('y', 'crash_change')):   # trim axes to 2nd-98th percentile
        lo, hi = z[col].quantile([0.02, 0.98])
        pad = (hi - lo) * 0.1
        getattr(fig, f'update_{axis}axes')(range=[lo - pad, hi + pad])
    return fig

# ---------------- Q8: injuries per crash by permit cost level ----------------
def q8_data(df):
    d = df[(df['permits'] > 0) & df['median_cost'].notna() & (df['crashes'] >= 5)].copy()  # 5+ crashes: stable ratio
    if len(d) < 100:
        return None
    d['injuries_per_crash'] = d['persons_injured'] / d['crashes']
    d['q'] = pd.qcut(d['median_cost'].rank(method='first'), 4, labels=False)  # rank avoids tie errors
    bounds = d.groupby('q')['median_cost'].agg(['min', 'max'])
    names = {i: f"Q{i + 1}: ${r['min']:,.0f} to ${r['max']:,.0f}" for i, r in bounds.iterrows()}
    d['cost_group'] = d['q'].map(names)
    return d, [names[i] for i in sorted(names)]

def fig_q8(df):
    res = q8_data(df)
    if res is None:
        return empty_fig('Not enough ZIP-months for this filter')
    d, order = res
    rho = d['median_cost'].corr(d['injuries_per_crash'], method='spearman')
    return px.box(d, x='cost_group', y='injuries_per_crash', points=False,
                  category_orders={'cost_group': order},
                  title=f'Q8: Injuries per crash by permit cost level (ZIP-months with 5+ crashes, rho = {rho:.2f})',
                  labels={'cost_group': 'Median permit cost in the ZIP-month (quartile)',
                          'injuries_per_crash': 'Injured people per crash'})

# ---------------- Q9: pedestrian and cyclist share of injuries by ZIP permit level ----------------
def q9_table(df):
    z = df.groupby('zip_code', as_index=False)[['permits', 'persons_injured',
                                                'pedestrians_injured', 'cyclists_injured']].sum()
    z = z[z['persons_injured'] > 0].copy()
    if len(z) < 9:
        return None
    z['tercile'] = pd.qcut(z['permits'].rank(method='first'), 3,
                           labels=['Fewest permits', 'Middle', 'Most permits'])
    s = (z.groupby('tercile', observed=True)
           .agg(zips=('zip_code', 'size'), ped=('pedestrians_injured', 'sum'),
                cyc=('cyclists_injured', 'sum'), total=('persons_injured', 'sum'))
           .reset_index())
    s['Pedestrians'] = s['ped'] / s['total'] * 100       # pooled share, so big ZIPs count more
    s['Cyclists'] = s['cyc'] / s['total'] * 100
    return s

def fig_q9(df):
    s = q9_table(df)
    if s is None:
        return empty_fig('Not enough ZIP codes for this filter')
    long = s.melt(id_vars=['tercile', 'zips'], value_vars=['Pedestrians', 'Cyclists'],
                  var_name='group', value_name='share')
    return px.bar(long, x='tercile', y='share', color='group', barmode='stack', text_auto='.1f',
                  hover_data={'zips': True},
                  title='Q9: Share of injured people who were pedestrians or cyclists, by ZIP permit level',
                  labels={'tercile': 'ZIP permit level (thirds of ZIP codes)',
                          'share': '% of all injured people', 'group': 'Group', 'zips': 'ZIPs'})

# ---------------- Q10: double hotspots ----------------
def double_hotspots(df):
    z = df.groupby(['zip_code', 'borough'], as_index=False)[['permits', 'crashes']].sum()
    z = z[(z['permits'] > 0) & (z['crashes'] > 0)].copy()
    if len(z) < 8:
        return None, None, None
    qx, qy = z['permits'].quantile(0.75), z['crashes'].quantile(0.75)
    z['group'] = np.where((z['permits'] >= qx) & (z['crashes'] >= qy),
                          'Double hotspot (top 25% on both)', 'Other ZIPs')
    return z, qx, qy

def fig_q10(df):
    z, qx, qy = double_hotspots(df)
    if z is None:
        return empty_fig('Not enough ZIP codes for this filter')
    n_hot = int((z['group'] != 'Other ZIPs').sum())
    fig = px.scatter(z, x='permits', y='crashes', color='group', hover_name='zip_code',
                     hover_data={'borough': True}, log_x=True, log_y=True,
                     color_discrete_map={'Double hotspot (top 25% on both)': '#d62728', 'Other ZIPs': '#9aa5b1'},
                     title=f'Q10: Double hotspots, {n_hot} of {len(z)} ZIPs are in the top quarter for permits and crashes',
                     labels={'permits': 'Permits issued (total)', 'crashes': 'Crashes (total)', 'group': ''})
    # quartile guide lines drawn as traces so they work on log axes
    fig.add_trace(go.Scatter(x=[qx, qx], y=[z['crashes'].min(), z['crashes'].max()], mode='lines',
                             line=dict(dash='dot', color='gray'), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=[z['permits'].min(), z['permits'].max()], y=[qy, qy], mode='lines',
                             line=dict(dash='dot', color='gray'), showlegend=False, hoverinfo='skip'))
    return fig
