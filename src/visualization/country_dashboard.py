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
from bokeh.models import ColumnDataSource, GeoJSONDataSource, NumeralTickFormatter, HoverTool, TapTool, DateSlider, Button, OpenURL
from bokeh.palettes import brewer
from bokeh.layouts import row, column

# set color_scheme
color_scheme = {'confirmed' : '#bf4040',
                'deaths' : '#868f96',
                'recovered' : '#a4d5fc'}

## Update Database
try:
    update_db()
except Exception as e:
    print('unable to get new data')
    print("---")
    print(str(e))
    print("---")


## Get and prepare datasources
df = qdb.get_coutry_data()
countries = gpd.read_file("../../data/processed/countries.shp")
plot_data = country_plot_data(df, countries)

## starting variables
start_date = '2020-02-01'
end_date = df['date'].max()
country = 'total'
df['date'] = pd.to_datetime(df['date'])


## 2. Interactivity
### callback
def updateSlider(attr, old, new):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # get data for this new date
    geosource.geojson = prep_geojson(plot_data, select_date)
    #overall_source.data = overall[overall['date']<=select_date]
    #daily_source.data = daily[daily['date']<=select_date]

    # update title
    map_plot.title.text = 'Covid cases per 1 Million inhabitants on ' + select_date

# date-slider
slider_end = datetime.strptime(end_date, "%Y-%m-%d")
date_slider = DateSlider(title = "Date: ", start = datetime.strptime(start_date, '%Y-%m-%d'),
                         end = slider_end, value = datetime.strptime(start_date, '%Y-%m-%d'),
                         step=1)
date_slider.on_change('value', updateSlider)

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

# create a button
button = Button(label='► Play', width=60)
button.on_click(animate)

def function_geosource(attr, old, new):
    try:
        indx = geosource.selected.indices[0]
        cntry = json.loads(geosource.geojson)['features'][indx]['properties']['country']
        source.data = df[df['country'] == cntry]

    except Exception as e:
        source.data = df[df['country'] == 'total']
        pass

## 3. Plots
#### mapplot
geosource = GeoJSONDataSource(geojson = prep_geojson(plot_data, start_date))
source = ColumnDataSource(df[df['country']==country])

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
          line_color = 'black', line_width = 0.25, fill_alpha = 1)

geosource.selected.on_change('indices', function_geosource)


#### overall cases plot
# create the plot
overall_plot = figure(title = 'Covid Progress',
           x_axis_type="datetime",
           x_axis_label = 'Date',
           y_axis_label = 'Persons',
           plot_height = 280,
           plot_width = 500,
           toolbar_location = None)

overall_plot.line(x='date', y='confirmed', line_width=2, source=source, color='#bf4040', legend_label='confirmed')
overall_plot.line(x='date', y='deaths', line_width=2, source=source, color='#868f96', legend_label = 'death')
overall_plot.line(x='date', y='recovered', line_width=2, source=source, color='#a4d5fc', legend_label = 'recovered')

#
overall_plot.yaxis.formatter=NumeralTickFormatter(format=",00")
overall_plot.legend.location = "top_left"
overall_plot.legend.click_policy="hide"


#### daily_new_cases
# use a time-delta for the width
bar_w = pd.Timedelta(hours = 12)

daily_plot = figure(title = 'Covid Progress',
           x_axis_type="datetime",
           x_axis_label = 'Date',
           y_axis_label = 'Persons',
           plot_height = 280,
           plot_width = 500,
           toolbar_location = None)

daily_plot.vbar(x='date', width = bar_w, top='daily_confirmed', source=source, color = color_scheme['confirmed'], alpha = 0.1)
daily_plot.line(x='date', y='daily_confirmed_ma7', line_width=2 ,source=source, color = color_scheme['confirmed'], legend_label='confirmed cases')

daily_plot.vbar(x='date', width = bar_w, top='daily_deaths', source=source, color = color_scheme['deaths'], alpha = 0.3)
daily_plot.line(x='date', y='daily_deaths_ma7', line_width=2 ,source=source, color = color_scheme['deaths'], legend_label='deaths')

#p.vbar(x='date', width = bar_w, top='daily_recovered', source=source, color = '#a4d5fc', alpha = 0.3, legend_label = 'deaths')
daily_plot.line(x='date', y='daily_recovered_ma7', line_width=2 ,source=source, color = color_scheme['recovered'], legend_label='recoveries')

daily_plot.y_range.start = 0
daily_plot.yaxis.formatter=NumeralTickFormatter(format=",00")
daily_plot.legend.location = "top_left"




## 4. Layout
layout = row(column(map_plot, row(date_slider, button, sizing_mode='scale_width')),
             column(overall_plot, daily_plot))

curdoc().add_root(layout)
curdoc().title = 'Covid-19'
