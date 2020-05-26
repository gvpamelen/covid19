import numpy as np
import pandas as pd
from datetime import date, datetime
from src.data.query_db import queryDB
from bokeh.io import curdoc, show, output_file
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, LinearColorMapper, ColorBar, HoverTool, Slider, DateSlider, Button
from bokeh.palettes import Category10
from bokeh.layouts import widgetbox, row, column

# initialise
qdb = queryDB('sqlite','../data/processed/covid.sqlite')

# main parameters
start_date = '2020-02-01'


# User Defined Functions
def setAxes(exp):
    """
    Generate labels for double logaritmic axes in a bokeh plot bases on the
    dateset to be plotted (in exp)
    """
    # find the range required
    x_max = np.ceil(np.log10(exp.total_confirmed.max()))
    y_max = np.ceil(np.log10(exp.new_last_week.max()))

    # generate locations
    x_locs_raw = 10**np.arange(0,x_max+1,1)
    x_locs = [int(i) for i in x_locs_raw]
    y_locs_raw = 10**np.arange(0,y_max+1,1)
    y_locs = [int(i) for i in y_locs_raw]

    # generate labels
    x_labels = ['{:,.0f}'.format(v) for v in x_locs]
    y_labels = ['{:,.0f}'.format(v) for v in y_locs]

    # get required format
    x_set = dict(zip(x_locs, x_labels))
    y_set = dict(zip(y_locs, y_labels))

    return x_set, y_set, x_max, y_max


def getExpData(countries):
    """
    Query the database
    """
    # prepare query to get countries
    country_string = '('
    for country in countries:
        country_string += """'""" + country + """',"""
    country_string = country_string[:-1] + """)"""

    # prepare the query
    query = """
        SELECT *
          FROM exp_stats
         WHERE country IN {}
           AND total_confirmed > 25
        """.format(country_string)

    return qdb.execute_query(query)


def getPlotDataSource(sample_exp, dt = '2020-05-20'):
    """Create the required ColumnDataSource for the multi-lineplot for
    date up till dt start_date (used in slider)
    """
    # get individual countries
    countries = sample_exp.country.unique().tolist()

    total_conf_set, last_week_set = [], []
    for country in countries:
        single_country = sample_exp[(sample_exp['country']==country) & (sample_exp['date'] <= dt)]
        total_conf_set.append(np.array(single_country.total_confirmed))
        last_week_set.append(np.array(single_country.new_last_week))

    # create dict for ColumnDataSource
    data = {'xs' : total_conf_set,
            'ys' : last_week_set,
            'color' : [(Category10[n_countries])[i] for i in range(len(countries))],
            'country' : countries}

    # color array is consistent...
    return data


# Get the dataset
countries = ['Netherlands', 'Italy', 'Malaysia', 'China', 'United States', 'Brazil']
exp_data = getExpData(countries)
n_countries = len(countries)
end_date = str(exp_data.date.max())[:10]
start_date = min(str(exp_data['date'].min())[:10], start_date)  #overwrite to first date in set

### callback will come here
def updateSlider(attr, old, new):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # get data for this new date
    source.data = getPlotDataSource(exp_data, select_date)

    # update title
    p.title.text = 'Covid exponential growth assessment on ' + select_date


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
        dt_formatted = start_date
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
# create the plot
p = figure(title = 'Covid exponential growth assessment on ' + start_date,
           x_axis_type = 'log',
           y_axis_type = 'log',
           x_axis_label = 'Total confirmed cases',
           y_axis_label = 'New cases last week',
           plot_height = 400,
           plot_width = 700)

# create the source
source = ColumnDataSource(data = getPlotDataSource(exp_data, start_date))

# plot
p.multi_line(xs="xs", ys="ys", line_color="color", legend_field = 'country',
                line_width=2, source=source)


# get parameters for axes and baselines
x_set, y_set, x_max, y_max = setAxes(exp_data)

# get grey shaded & dashed baseline
n = int(min(x_max,y_max))
ln = np.logspace(0, int(n), int(n))
p.line(ln, ln, line_dash="4 4", line_width=1, color='gray')

# set axes
p.xaxis.major_label_overrides = x_set
p.yaxis.major_label_overrides = y_set

# add legend
p.legend.location = "top_left"

### add layout here
layout = column(p, row(date_slider, button, sizing_mode='scale_width'))

# output
curdoc().add_root(layout)
curdoc().title = 'Covid-19'
