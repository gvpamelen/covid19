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

#def getBarData(n=10):
#    """
#    Get top N countries per day by total confirmed cases
#    """
#    query = """
#            SELECT *
#            FROM (
#                SELECT
#                    DATE(date) AS date,
#                    country,
#                    SUM(confirmed) AS confirmed,
#                    ROW_NUMBER() OVER (PARTITION BY date ORDER BY SUM(confirmed) DESC) AS rnk
#                FROM stats
#                GROUP BY date, country) AS sub
#            WHERE rnk <= {}
#            """.format(n)
#
#    return qdb.execute_query(query)


def getExpData():
    query = """
        SELECT total.date,
               total.country,
               total_confirmed AS confirmed,
               new_last_week,
               ROW_NUMBER() OVER (PARTITION BY total.date ORDER BY total_confirmed DESC) as rnk
          FROM (SELECT country,
                       DATE(date) AS date,
                       confirmed AS total_confirmed
                  FROM stats ) AS total
          JOIN (SELECT DATE(date) AS date,
                       country,
                       SUM(confirmed) OVER (PARTITION BY country ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS new_last_week
                  FROM daily_stats ) AS last_week
            ON last_week.date = total.date AND last_week.country = total.country;"""

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

def getPlotDataSource(sample_exp, countries, coutry_color_mapping, dt = '2020-05-20'):
    """Create the required ColumnDataSource for the multi-lineplot for
    date up till dt start_date (used in slider)
    """
    # get individual countries
    #countries = sample_exp.country.unique().tolist()
    #sample_exp[sample_exp[]]
    # current & past top 10
    rel_countries = list(sample_exp[(sample_exp['date'] <= dt) & (sample_exp['rnk'] <= 10)]['country'].unique())

    total_conf_set, last_week_set = [], []
    for country in rel_countries:
        single_country = sample_exp[(sample_exp['country']==country) & (sample_exp['date'] <= dt) & (sample_exp['confirmed']>=100)]
        total_conf_set.append(np.array(single_country.confirmed))
        last_week_set.append(np.array(single_country.new_last_week))

    # create dict for ColumnDataSource
    data = {'xs' : total_conf_set,
            'ys' : last_week_set,
            'color' : [coutry_color_mapping[country] if country in countries else '#D5DBDB' for country in rel_countries],
            'country' : rel_countries}

    # color array is consistent...
    return data

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

def setAxes(exp):
    """
    Generate labels for double logaritmic axes in a bokeh plot bases on the
    dateset to be plotted (in exp)
    """
    # find the range required
    x_max = np.ceil(np.log10(exp.confirmed.max()))
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


# get the main dataset
#bar_data = getBarData()
full_exp_data = getExpData()
bar_data = full_exp_data[full_exp_data['rnk']<=10]
#exp_data = full_exp_data
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
        p_exp_source.data = getPlotDataSource(full_exp_data, initial_countries, country_color_mapping, select_date)

    else:
        # set colors
        new_countries = list(new_data['country']) #[::-1])
        country_color_mapping = updateColorMapping(country_color_mapping, new_countries)
        source.data['color'] = [country_color_mapping.get(key) for key in new_countries]
        p_exp_source.data = getPlotDataSource(full_exp_data, new_countries, country_color_mapping, select_date)

    # update title
    rc.title.text = 'Top 10 countries with most COVID-19 cases on ' + select_date
    rc.y_range.factors = list(source.data['country'][::-1])

    # update cont_plot
    cont_source.data = continent[continent['date'] == select_date]
    cont_bars.title.text = 'Confirmed cases per continent on ' + select_date

    # update exp_plot




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
           plot_width = 500,
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
                   y_range=np.sort(continent['continent'].unique())[::-1],
                   plot_height=300, plot_width = 500,
                   toolbar_location=None, tools="")

cont_bars.hbar(y = 'continent', right = 'confirmed',
               fill_color = 'red', fill_alpha = 0.5,
               line_color = None, source = cont_source, height=0.8)

cont_bars.ygrid.grid_line_color = None
cont_bars.x_range.start = 0
cont_bars.xaxis.formatter=NumeralTickFormatter(format=",00")


#### EXPONENTIAL PLOT
# tooltips
hover = HoverTool(tooltips=[('country','@country')])

# create the plot
p_exp = figure(title = 'Covid exponential growth assessment on ' + start_date,
           x_axis_type = 'log',
           y_axis_type = 'log',
           x_axis_label = 'Total confirmed cases',
           y_axis_label = 'New cases last week',
           plot_height = 600,
           plot_width = 700,
           tools = [hover],
           toolbar_location = None)

# create the source
p_exp_source = ColumnDataSource(data = getPlotDataSource(full_exp_data, initial_countries, country_color_mapping, start_date))

# plot
p_exp.multi_line(xs="xs", ys="ys", line_color="color",
                line_width=2, source=p_exp_source)



# get parameters for axes and baselines
x_set, y_set, x_max, y_max = setAxes(full_exp_data)

# get grey shaded & dashed baseline
n = int(min(x_max,y_max))
ln = np.logspace(0, int(n), int(n))
p_exp.line(ln, ln, line_dash="4 4", line_width=1, color='gray')

# set axes
p_exp.x_range.start = 100
p_exp.xaxis.major_label_overrides = x_set
p_exp.y_range.start = 100
p_exp.yaxis.major_label_overrides = y_set




### add layout here
#layout = column(rc, cont_bars, row(date_slider, button, sizing_mode='scale_width'))
layout = row(column(rc, cont_bars),
             column(p_exp,row(date_slider, button, sizing_mode='scale_width')))
# output
curdoc().add_root(layout)
curdoc().title = 'Covid-19'
