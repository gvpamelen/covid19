import numpy as np
import pandas as pd
from datetime import date, datetime
from src.data.query_db import queryDB
from bokeh.io import curdoc, show, output_file
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, NumeralTickFormatter, ColorBar, HoverTool, Slider, DateSlider, Button
from bokeh.layouts import widgetbox, row, column


# initialise
qdb = queryDB('sqlite','../data/processed/covid.sqlite')

# main parameters
start_date = '2020-03-01'


### USER DEFINED FUNCTIONS
def getCumulativeStats():
    query = """
        SELECT DATE(date) AS date,
               SUM(confirmed) AS confirmed,
               SUM(death) AS death,
               SUM(recovered) AS recovered
          FROM stats
         GROUP BY date
         ORDER BY date DESC;"""

    overall = qdb.execute_query(query)
    return overall

def getDailyStats():
    query = """
        SELECT
            date,
            SUM(confirmed) AS confirmed,
            SUM(death) AS death,
            SUM(confirmed_ma) AS confirmed_ma,
            SUM(death_ma) AS death_ma
        FROM daily_stats
        GROUP BY date;"""

    daily = qdb.execute_query(query)
    return daily


# get the dataset
overall = getCumulativeStats()
end_date = str(overall.date.max())[:10]
first_date = str(overall.date.min())[:10]
conf_max = (overall['confirmed'].max()//1000000 +1)*1000000

daily = getDailyStats()
daily_max = (daily['confirmed'].max()//10000 +2)*10000

### callback
def updateSlider(attr, old, new):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # get data for this new date
    #geosource.geojson = selectDailyData(countries, cases, select_date)
    overall_source.data = overall[overall['date']<=select_date]
    daily_source.data = daily[daily['date']<=select_date]

    # update title
    total_plot.title.text = 'Total Global Covid cases on ' + select_date

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




### TOTAL PLOT
#set source
overall_source = ColumnDataSource(overall[overall['date']<start_date])

## TODO: make x and y range dynamic to max plot ranges in data
# create the plot
total_plot = figure(title = 'Covid Progress',
                   x_axis_type="datetime",
                   x_axis_label = 'Date',
                   x_range = (datetime.strptime(first_date, "%Y-%m-%d"),
                              datetime.strptime(end_date, "%Y-%m-%d")),
                   y_range = (0,conf_max),
                   y_axis_label = 'Persons',
                   plot_height = 300,
                   plot_width = 600)

total_plot.line(x='date', y='confirmed', line_width=2, source=overall_source, color='red', legend_label='confirmed')
total_plot.line(x='date', y='death', line_width=2, source=overall_source, color='blue', legend_label = 'death')

total_plot.yaxis.formatter=NumeralTickFormatter(format=",00")


total_plot.legend.location = "top_left"
total_plot.legend.click_policy="hide"


### DAILY PLOT
#set source
daily_source = ColumnDataSource(daily[daily['date']<start_date])

# use a time-delata for the width
bar_w = pd.Timedelta(hours = 12)


# create the plot
daily_plot = figure(title = 'Covid Progress',
           x_axis_type="datetime",
           x_axis_label = 'Date',
           x_range = (datetime.strptime(first_date, "%Y-%m-%d"),
                      datetime.strptime(end_date, "%Y-%m-%d")),
           y_range = (0,daily_max),
           y_axis_label = 'Persons',
           plot_height = 300,
           plot_width = 600)

# confirmed cases
daily_plot.vbar(x='date', width = bar_w, top='confirmed', source=daily_source, color = 'red', alpha = 0.2, legend_label = 'confirmed cases')
daily_plot.line(x='date', y='confirmed_ma', line_width=2 ,source=daily_source, color='red')

# deaths
daily_plot.vbar(x='date', width = bar_w, top='death', source=daily_source, color = 'blue', alpha = 0.2, legend_label = 'deaths')
daily_plot.line(x='date', y='death_ma', line_width=2 ,source=daily_source, color='blue')

daily_plot.y_range.start = 0
daily_plot.yaxis.formatter=NumeralTickFormatter(format=",00")
daily_plot.legend.location = "top_left"




### add layout here
layout = column(total_plot, daily_plot, row(date_slider, button, sizing_mode='scale_width'))

# output
curdoc().add_root(layout)
curdoc().title = 'Covid-19'
