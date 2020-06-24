import numpy as np
import pandas as pd
from datetime import date, datetime
from src.data.query_db import queryDB
from bokeh.io import curdoc, show, output_file
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, LinearColorMapper, ColorBar, HoverTool, Slider, DateSlider, Button, NumeralTickFormatter, FactorRange
from bokeh.layouts import widgetbox, row, column
from bokeh.palettes import Category10

# initialise
qdb = queryDB('sqlite','../data/processed/covid.sqlite')

# main parameters
start_date = '2020-02-01'


# User Defined Functions
def getBarData(n=10):
    """
    Get top N countries per day by total confirmed cases
    """
    query = """
            SELECT *
            FROM (
                SELECT
                    DATE(date) AS date,
                    country,
                    SUM(confirmed) AS confirmed,
                    ROW_NUMBER() OVER (PARTITION BY date ORDER BY SUM(confirmed) DESC) AS rnk
                FROM stats
                GROUP BY date, country) AS sub
            WHERE rnk <= {}
            """.format(n)

    return qdb.execute_query(query)


def getContinentData():
    query = """
        SELECT
            date,
            continent,
            SUM(confirmed) AS confirmed
        FROM stats
        JOIN populations
            ON stats.country = populations.country
        WHERE continent != 'Seven seas (open ocean)'
        GROUP BY
            date,
            continent
        ORDER BY
            date,
            SUM(confirmed) DESC
        """

    continent = qdb.execute_query(query)
    return continent


def createColorMapping(countries):
    """
    Create a dict of countries & colors to keep fixed colors through plotting sequence
    """
    coutry_color_mapping = {}
    n = len(countries)
    if n > 10:
        print('Maximum of 10 countries for this color-range')

    else:
        for i in range(n):
            coutry_color_mapping[countries[i]] = Category10[n][i]

    return coutry_color_mapping


def updateColorMapping(coutry_color_mapping, new_countries):
    """
    Update countries to the new top-10 set
    """
    # find which countries have changed
    old_countries = list(coutry_color_mapping.keys())
    old_countries_rm = [x for x in old_countries if x not in new_countries]
    new_countries = [x for x in new_countries if x not in old_countries]

    # switch out old -> new countries
    for i in range(len(old_countries_rm)):
        coutry_color_mapping[new_countries[i]] = coutry_color_mapping.pop(old_countries_rm[i])

    return coutry_color_mapping


# get the main dataset
bar_data = getBarData()
end_date = str(bar_data.date.max())[:10]
continent = getContinentData()

# create the source
initial_data = bar_data[bar_data['date'] == start_date].sort_values('rnk')
initial_countries = list(initial_data.country)
country_color_mapping = createColorMapping(initial_countries)

### callback will come here
def updateSlider(attr, old, new, country_color_mapping = country_color_mapping):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # get data for this new date
    new_data = bar_data[bar_data['date'] == select_date].sort_values('rnk')
    source.data = new_data#getPlotDataSource(exp_data, select_date)

    # reset to initial color-mapping at passing start-date
    if select_date == start_date:
        country_color_mapping = createColorMapping(initial_countries)
        source.data['color'] = [country_color_mapping.get(key) for key in initial_countries]

    else:
        # set colors
        new_countries = list(new_data['country']) #[::-1])
        country_color_mapping = updateColorMapping(country_color_mapping, new_countries)
        source.data['color'] = [country_color_mapping.get(key) for key in new_countries]

    # update title
    rc.title.text = 'Top 10 countries with most COVID-19 cases on ' + select_date
    rc.y_range.factors = list(source.data['country'][::-1])

    cont_source.data = continent[continent['date'] == select_date]
    cont_bars.title.text = 'Confirmed cases per continent on ' + select_date


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
        callback_id = curdoc().add_periodic_callback(animate_update, 300)
    else:
        button.label = '► Play'
        curdoc().remove_periodic_callback(callback_id)

# create a button
button = Button(label='► Play', width=60)
button.on_click(animate)



#### RACE CHART
source = ColumnDataSource(data = initial_data)
source.data['color'] = [country_color_mapping.get(key) for key in initial_countries]

# setup
rc = figure(title = 'Top 10 countries with most COVID-19 cases on ' + start_date,
           y_range = FactorRange(factors = source.data['country'][::-1]),
           plot_height=300,
           toolbar_location=None,
           tools="")


# plot
rc.hbar(y='country', right='confirmed',
        fill_color = 'color', line_color = None, source = source, height=0.8)

# formatting
rc.xaxis.formatter=NumeralTickFormatter(format=",00")
rc.ygrid.grid_line_color = None
rc.x_range.start = 0


#### CONTINENT CHART
cont_data = continent[continent['date'] == start_date]
cont_source = ColumnDataSource(cont_data)
cont_bars = figure(title = 'Confirmed cases per continent on ' + start_date,
                   y_range=np.sort(continent['continent'].unique()),
                   plot_height=300, toolbar_location=None, tools="")

cont_bars.hbar(y = 'continent', right = 'confirmed', source = cont_source, height=0.8)
cont_bars.ygrid.grid_line_color = None
cont_bars.x_range.start = 0
cont_bars.xaxis.formatter=NumeralTickFormatter(format=",00")



### add layout here
layout = column(rc, cont_bars, row(date_slider, button, sizing_mode='scale_width'))

# output
curdoc().add_root(layout)
curdoc().title = 'Covid-19'
