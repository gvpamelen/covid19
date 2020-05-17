import numpy as np
import pandas as pd
import geopandas as gpd
import json
from datetime import date, datetime
from src.data.query_db import queryDB
from bokeh.io import curdoc, show, output_file
from bokeh.plotting import figure
from bokeh.models import GeoJSONDataSource, LinearColorMapper, ColorBar, HoverTool, Slider, DateSlider, Button
from bokeh.palettes import brewer
from bokeh.layouts import widgetbox, row, column


# initialise
qdb = queryDB('sqlite','../data/processed/covid.sqlite')

# main parameters
start_date = '2020-03-01'

### USER DEFINED FUNCTIONS
# load dataset (month included)
def getCasesByCountry(bins=9):
    query = """
    SELECT *,
           NTILE({}) OVER (PARTITION BY date ORDER BY conf_scaled) AS bin
      FROM (SELECT stats.country,
                   date,
                   population,
                   CAST(confirmed/scaled_pop AS integer) AS conf_scaled,
                   CAST(death/scaled_pop AS integer) AS death_scaled,
                   CAST(recovered/scaled_pop AS integer) AS recov_scaled
              FROM stats
             INNER JOIN populations
                ON stats.country = populations.country
             ORDER BY conf_scaled DESC) sub;""".format(bins)

    return qdb.execute_query(query)


def selectDailyData(countries, df, select_date):
    cases_select = df[df['date'] == select_date]

    # left join (we need all countries)
    df = countries.merge(cases_select, on = 'country', how = 'left')

    # select a date and convert to JSON
    merged_json = json.loads(df.to_json())
    json_data = json.dumps(merged_json)
    return json_data


### DATA
# load countries
countries = gpd.read_file('../data/processed/countries.geojson')

# load covid data
cases = getCasesByCountry(bins=9)
cases['date'] = cases['date'].astype(str) # require for JSON conversion
end_date = cases['date'].max()


### callback
def updateSlider(attr, old, new):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # get data for this new date
    geosource.geojson = selectDailyData(countries, cases, select_date)

    # update title
    plot.title.text = 'Covid cases per 1 Million inhabitants on ' + select_date


### PLOT
# ColumnDataSource
geosource = GeoJSONDataSource(geojson = selectDailyData(countries, cases, start_date))

# set the colorscheme
palette = brewer['Reds'][9]
palette = palette[::-1]
color_mapper = LinearColorMapper(palette = palette, low = 1, high = 9,
                                 nan_color = '#d9d9d9')

#Create color bar.
color_bar = ColorBar(color_mapper=color_mapper, label_standoff=8,width = 500,
                        height = 20, border_line_color=None, location = (0,0),
             orientation = 'horizontal')


# date-slider
slider_end = datetime.strptime(end_date, "%Y-%m-%d")
date_slider = DateSlider(title = "Date: ", start = date(2020, 3, 1),
                         end = slider_end, value = date(2020, 3, 1),
                         step=1)
date_slider.on_change('value', updateSlider)


# update slider during animation
def animate_update():
    dt = date_slider.value + (3600*24*1000) #1 day in seconds
    dt_formatted = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")
    if dt_formatted > slider_end.strftime("%Y-%m-%d"):
        dt_formatted = date(2020, 3, 1).strftime("%Y-%m-%d")
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




# tooltips
hover = HoverTool(tooltips=[('country','@country'),
                            ('infected per 1M','@conf_scaled'),
                            ('deaths per 1M','@death_scaled')])

# create the canvas
plot = figure(title = 'Covid cases per 1 Million inhabitants on ' + start_date,
           plot_height = 500, plot_width = 900,
           x_range = [-181,181], y_range = [-60,90],
           tools = [hover])

# plot the geosource
plot.patches('xs','ys', source = geosource, fill_color = {'field' :'bin', 'transform' : color_mapper},
          line_color = 'black', line_width = 0.25, fill_alpha = 1)

# format axes (no grids no axes)
plot.xgrid.grid_line_color = None
plot.ygrid.grid_line_color = None
plot.axis.visible = False

# doc
layout = column(plot, row(date_slider, button, sizing_mode='scale_width'))

curdoc().add_root(layout)
curdoc().title = 'Covid-19'
