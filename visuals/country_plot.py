import numpy as np
import pandas as pd
import geopandas as gpd
import json
from datetime import date, datetime
from src.data.query_db import queryDB
from bokeh.io import curdoc, show, output_file
from bokeh.plotting import figure
from bokeh.models import GeoJSONDataSource, ColumnDataSource, NumeralTickFormatter, LinearColorMapper, ColorBar, HoverTool, Slider, DateSlider, Button
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


def getCumulativeStats(scale=1000000.00):
    query = """
        SELECT DATE(date) AS date,
               SUM(confirmed)/{} AS confirmed,
               SUM(death)/{} AS death,
               SUM(recovered)/{} AS recovered
          FROM stats
         GROUP BY date
         ORDER BY date DESC;""".format(scale,scale,scale)

    overall = qdb.execute_query(query)
    return overall

def getDailyStats(scale=1000.00):
    query = """
        SELECT
            date,
            SUM(confirmed)/{} AS confirmed,
            SUM(death)/{} AS death,
            SUM(confirmed_ma)/{} AS confirmed_ma,
            SUM(death_ma)/{} AS death_ma
        FROM daily_stats
        GROUP BY date;""".format(scale,scale,scale,scale)

    daily = qdb.execute_query(query)
    return daily




### DATA
# load countries
countries = gpd.read_file('../data/processed/countries.geojson')

# load covid data
cases = getCasesByCountry(bins=9)
cases['date'] = cases['date'].astype(str) # require for JSON conversion
end_date = cases['date'].max()

# load cumulative data
overall = getCumulativeStats()
end_date = str(overall.date.max())[:10]
first_date = str(overall.date.min())[:10]
conf_max = (overall['confirmed'].max()//1+1)

# load daily incremental data
daily = getDailyStats()
daily_max = (daily['confirmed'].max()//10 +2)*10



### callback
def updateSlider(attr, old, new):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # get data for this new date
    geosource.geojson = selectDailyData(countries, cases, select_date)
    overall_source.data = overall[overall['date']<=select_date]
    daily_source.data = daily[daily['date']<=select_date]

    # update title
    plot.title.text = 'Covid cases per 1 Million inhabitants on ' + select_date

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

# tooltips
hover = HoverTool(tooltips=[('country','@country'),
                            ('infected per 1M','@conf_scaled'),
                            ('deaths per 1M','@death_scaled')])

# create the canvas
plot = figure(title = 'Covid cases per 1 Million inhabitants on ' + start_date,
           plot_height = 500,
           plot_width = 850,
           x_range = [-181,181],
           y_range = [-60,90],
           tools = [hover],
           toolbar_location = None)

# plot the geosource
plot.patches('xs','ys', source = geosource, fill_color = {'field' :'bin', 'transform' : color_mapper},
          line_color = 'black', line_width = 0.25, fill_alpha = 1)

# format axes (no grids no axes)
plot.xgrid.grid_line_color = None
plot.ygrid.grid_line_color = None
plot.axis.visible = False


### TOTAL PLOT
#set source
overall_source = ColumnDataSource(overall[overall['date']<start_date])

## TODO: make x and y range dynamic to max plot ranges in data
# create the plot
total_plot = figure(title = 'Cumulative Global Covid cases (x1 million)',
                   x_axis_type="datetime",
                   x_axis_label = 'Date',
                   x_range = (datetime.strptime(first_date, "%Y-%m-%d"),
                              datetime.strptime(end_date, "%Y-%m-%d")),
                   y_range = (0,conf_max),
                   plot_height = 280,
                   plot_width = 500,
                   toolbar_location = None)

total_plot.line(x='date', y='confirmed', line_width=2, source=overall_source, color='red', legend_label='confirmed')
total_plot.line(x='date', y='death', line_width=2, source=overall_source, color='blue', legend_label = 'death')

total_plot.yaxis.formatter=NumeralTickFormatter(format=",0")


total_plot.legend.location = "top_left"
total_plot.legend.click_policy="hide"


### DAILY PLOT
#set source
daily_source = ColumnDataSource(daily[daily['date']<start_date])

# use a time-delata for the width
bar_w = pd.Timedelta(hours = 12)


# create the plot
daily_plot = figure(title = 'Daily incremental Covid cases (x1,000)',
           x_axis_type="datetime",
           x_axis_label = 'Date',
           x_range = (datetime.strptime(first_date, "%Y-%m-%d"),
                      datetime.strptime(end_date, "%Y-%m-%d")),
           y_range = (0,daily_max),
           plot_height = 280,
           plot_width = 500,
           toolbar_location = None)

# confirmed cases
daily_plot.vbar(x='date', width = bar_w, top='confirmed', source=daily_source, color = 'red', alpha = 0.2, legend_label = 'confirmed cases')
daily_plot.line(x='date', y='confirmed_ma', line_width=2 ,source=daily_source, color='red')

# deaths
daily_plot.vbar(x='date', width = bar_w, top='death', source=daily_source, color = 'blue', alpha = 0.2, legend_label = 'deaths')
daily_plot.line(x='date', y='death_ma', line_width=2 ,source=daily_source, color='blue')

daily_plot.y_range.start = 0
daily_plot.yaxis.formatter=NumeralTickFormatter(format=",00")
daily_plot.legend.location = "top_left"





# doc
layout = row(column(plot, row(date_slider, button, sizing_mode='scale_width')),
             column(total_plot, daily_plot))

curdoc().add_root(layout)
curdoc().title = 'Covid-19'
