import numpy as np
import pandas as pd
import geopandas as gpd
import json
from datetime import date, datetime

from src.data.process_data import update_db
from src.visualization.prepare_dashboard_data import get_country_colormap, country_plot_data, prep_geojson
from src.data.quick_queries import queryDB
qdb = queryDB('sqlite','../../data/processed/covid_db.sqlite')

from bokeh.io import curdoc
from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource, GeoJSONDataSource, NumeralTickFormatter, HoverTool, TapTool, DateSlider, Button, CDSView, BooleanFilter, Span
from bokeh.palettes import brewer
from bokeh.layouts import row, column

#### Update Database when starting the dashboard
try:
    update_db()
except Exception as e:
    print('unable to update db')
    print("---")
    print(str(e))
    print("---")


#### Get and prepare datasources
df = qdb.get_coutry_data()
countries = gpd.read_file("../../data/processed/countries.shp")
plot_data = country_plot_data(df, countries)


#### starting variables
start_date = '2020-03-10' #'2020-02-01'
first_date = df['date'].min()
end_date = df['date'].max()

# show totals by default (obtained via rollup with 'total' in country)
country = 'total'

# convert date to datetime for plotting with temporal axis
df['date_obj'] = pd.to_datetime(df['date'])

# colorscheme (red, black, blue) for consistent use
color_scheme = {'confirmed' : '#bf4040',
                'deaths' : '#868f96',
                'recovered' : '#a4d5fc'}

# plot sources
geosource = GeoJSONDataSource(geojson = prep_geojson(plot_data, start_date))
source = ColumnDataSource(df[df['country']==country])
booleans = [True if date == start_date else False for date in source.data['date']]
view = CDSView(source=source, filters = [BooleanFilter(booleans)])
#source_hl = ColumnDataSource(df[(df['country']==country)
#                                    & (df['date'] == start_date)])

#### interactive elements
def update_slider(attr, old, new):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # get data for this new date
    geosource.geojson = prep_geojson(plot_data, select_date)

    # update our view to highlight this data in the lineplots
    cur_date.location = datetime.strptime(select_date, "%Y-%m-%d")
    cur_date_dy.location = datetime.strptime(select_date, "%Y-%m-%d")
    booleans = [True if date == select_date else False for date in source.data['date']]
    view.filters[0] = BooleanFilter(booleans)

    # update title
    map_plot.title.text = 'Covid cases per 1 Million inhabitants on ' + select_date

# update slider during animation
def animate_update():
    dt = date_slider.value + (3600*24*1000) #1 day in seconds
    dt_formatted = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")
    if dt_formatted > slider_end.strftime("%Y-%m-%d"):
        dt_formatted = start_date #date(2020, 3, 1).strftime("%Y-%m-%d")
    date_slider.value = datetime.strptime(dt_formatted, "%Y-%m-%d")

# run the animation
def animate():
    global callback_id
    if button.label == '► Play':
        button.label = '❚❚ Pause'
        # second parameter is the step-time in ms
        callback_id = curdoc().add_periodic_callback(animate_update, 200)
    else:
        button.label = '► Play'
        curdoc().remove_periodic_callback(callback_id)

def function_geosource(attr, old, new):
    try:
        indx = geosource.selected.indices[0]
        cntry = json.loads(geosource.geojson)['features'][indx]['properties']['country']
        source.data = df[df['country'] == cntry]
        overall_plot.title.text = 'Total cases to date: ' + cntry
        daily_plot.title.text = 'Daily new cases: ' + cntry

    except Exception as e:
        source.data = df[df['country'] == 'total']
        overall_plot.title.text = 'Total cases to date: global'
        daily_plot.title.text = 'Daily new cases: global'
        pass


#### visual elements
# date-slider - 'updateSlider'
slider_end = datetime.strptime(end_date, "%Y-%m-%d")
date_slider = DateSlider(title = "Date: ", start = datetime.strptime(first_date, '%Y-%m-%d'),
                         end = slider_end, value = datetime.strptime(start_date, '%Y-%m-%d'),
                         step=1)
date_slider.on_change('value', update_slider)

# play button - 'animate'
button = Button(label='► Play', width=60)
button.on_click(animate)

# taptool: click on country 'function_geosource'
geosource.selected.on_change('indices', function_geosource)


## 1.mapplot
# tooltips
hover = HoverTool(tooltips=[('country','@country'),
                            ('infected per 1M','@confirmed_scaled'),
                            ('deaths per 1M','@deaths_scaled')])
tap = TapTool()

# create the plot
map_plot = figure(title = 'Covid cases per 1 Million inhabitants on ' + start_date,
           plot_height = 500,
           plot_width = 850,
           x_range = [-181,181],
           y_range = [-60,90],
           tools = [hover, tap],
           toolbar_location = None)

map_plot.patches('xs','ys', source = geosource, fill_color = 'color',
          line_color = 'black', line_width = 0.25, fill_alpha = 1,
          nonselection_alpha=0.2)


## 2. overall cases plot (cumulative per day)
hover = HoverTool(tooltips=[('confirmed','@confirmed{,00}'),
                            ('deaths','@deaths{,00}'),
                            ('recovered','@recovered{,00}')])
# create the plot
overall_plot = figure(title = 'Total cases to date: global',
           x_axis_type="datetime",
           x_axis_label = 'Date',
           x_range = (datetime.strptime(first_date, "%Y-%m-%d"),
                      datetime.strptime(end_date, "%Y-%m-%d")),
           plot_height = 280,
           plot_width = 500,
           tools = [hover],
           toolbar_location = None)

# overall trend
overall_plot.line(x='date_obj', y='confirmed', line_width=2, source=source,
                  color=color_scheme['confirmed'], legend_label='confirmed')
overall_plot.line(x='date_obj', y='deaths', line_width=2, source=source,
                  color=color_scheme['deaths'], legend_label = 'death')
overall_plot.line(x='date_obj', y='recovered', line_width=2, source=source,
                  color=color_scheme['recovered'], legend_label = 'recovered')

# highlight specific date: vertical line
cur_date = Span(location = datetime.strptime(start_date, "%Y-%m-%d"),
                dimension='height', line_color='grey', line_alpha = 0.1,
                line_width=5)
overall_plot.add_layout(cur_date)
# and points
overall_plot.circle(x = 'date_obj', y = 'confirmed', size = 10, fill_alpha = 1,
                    source = source, view=view, color = color_scheme['confirmed'])
overall_plot.circle(x = 'date_obj', y = 'deaths', size = 10, fill_alpha = 1,
                    source = source, view=view, color = color_scheme['deaths'])
overall_plot.circle(x = 'date_obj', y = 'recovered', size = 10, fill_alpha = 1,
                    source = source, view=view, color = color_scheme['recovered'])

# format axes
overall_plot.yaxis.formatter=NumeralTickFormatter(format=",00")
overall_plot.legend.location = "top_left"
overall_plot.legend.click_policy="hide"


## 3. daily_new_cases
# use a time-delta for the width
bar_w = pd.Timedelta(hours = 12)

hover = HoverTool(tooltips=[('confirmed','@daily_confirmed{,00}'),
                            ('deaths','@daily_deaths{,00}'),
                            ('recovered','@daily_recovered{,00}')])

daily_plot = figure(title = 'Daily new cases: global',
           x_axis_type="datetime",
           x_axis_label = 'Date',
           x_range = (datetime.strptime(first_date, "%Y-%m-%d"),
                      datetime.strptime(end_date, "%Y-%m-%d")),
           plot_height = 280,
           plot_width = 500,
           tools = [hover],
           toolbar_location = None)

# confirmed
daily_plot.vbar(x='date_obj', width = bar_w, top='daily_confirmed', source=source, color = color_scheme['confirmed'], alpha = 0.1)
daily_plot.line(x='date_obj', y='daily_confirmed_ma7', line_width=2 ,source=source, color = color_scheme['confirmed'])
# death
daily_plot.vbar(x='date_obj', width = bar_w, top='daily_deaths', source=source, color = color_scheme['deaths'], alpha = 0.3)
daily_plot.line(x='date_obj', y='daily_deaths_ma7', line_width=2 ,source=source, color = color_scheme['deaths'])
# recovered
#p.vbar(x='date', width = bar_w, top='daily_recovered', source=source, color = '#a4d5fc', alpha = 0.3, legend_label = 'deaths')
daily_plot.line(x='date_obj', y='daily_recovered_ma7', line_width=2 ,source=source, color = color_scheme['recovered'])

# highlight specific date
cur_date_dy = Span(location = datetime.strptime(start_date, "%Y-%m-%d"),
                dimension='height', line_color='grey', line_alpha = 0.1,
                line_width=5)
daily_plot.add_layout(cur_date_dy)
daily_plot.circle(x = 'date_obj', y = 'daily_confirmed_ma7', size = 10, fill_alpha = 1,
                    source = source, view=view, color = color_scheme['confirmed'])
daily_plot.circle(x = 'date_obj', y = 'daily_deaths_ma7', size = 10, fill_alpha = 1,
                    source = source, view=view, color = color_scheme['deaths'])
daily_plot.circle(x = 'date_obj', y = 'daily_recovered_ma7', size = 10, fill_alpha = 1,
                    source = source, view=view, color = color_scheme['recovered'])

# format axes (leave out legend, use this from overall plot)
daily_plot.y_range.start = 0
daily_plot.yaxis.formatter=NumeralTickFormatter(format=",00")



#### Layout
layout = row(column(map_plot, row(date_slider, button, sizing_mode='scale_width')),
             column(overall_plot, daily_plot))

curdoc().add_root(layout)
curdoc().title = 'Covid-19'
