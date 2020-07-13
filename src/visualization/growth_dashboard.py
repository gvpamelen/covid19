import numpy as np
import pandas as pd
from datetime import date, datetime

from src.data.process_data import update_db
from src.visualization.prepare_dashboard_data import prep_exp_plot, setAxes
from src.data.quick_queries import queryDB
qdb = queryDB('sqlite','../../data/processed/covid_db.sqlite')

from bokeh.io import curdoc
from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource, GeoJSONDataSource, NumeralTickFormatter, HoverTool, DateSlider, Button
from bokeh.layouts import row, column


#### Update Database when starting the dashboard
try:
    update_db()
except Exception as e:
    print('unable to update db')
    print("---")
    print(str(e))
    print("---")


#### Get and prepare data
# colorscheme per continent used througout all plots
continent_colors = {'Africa' : '#003f5c',
                    'Asia' : '#444e86',
                    'Europe' : '#955196',
                    'North America' : '#dd5182',
                    'Oceania' : '#ff6e54',
                    'South America' : '#ffa600'}

# dataset for barplots
bar_data = qdb.get_top10_countries()
bar_data['color'] = bar_data['continent'].replace(continent_colors)
top10_countries = bar_data[bar_data['conf_rnk']<=10]

# name-lists by date for factors on axis
country_range = top10_countries.groupby('date')['country'].aggregate(lambda x: list(x)).reset_index()

# prepare continent barplot
cont_bars = bar_data[bar_data['plot_continent']==1]

# dataset for exp_plot
exp_data = qdb.get_exp_data()
exp_data['color'] = exp_data['continent'].replace(continent_colors)
exp_data = prep_exp_plot(exp_data)
x_set, y_set, x_max, y_max = setAxes(exp_data)


#### starting variables
start_date = '2020-03-10' #'2020-02-01'
first_date = top10_countries['date'].min()
end_date = top10_countries['date'].max()


#### create bokeh datasources
top10_source = ColumnDataSource(top10_countries[top10_countries['date']==start_date])
cont_source = ColumnDataSource(cont_bars[cont_bars['date']==start_date])
exp_source = ColumnDataSource(exp_data[exp_data['date'] == start_date])


#### interactive elements
def update_slider(attr, old, new):
    # changes to listen for
    dt = date_slider.value
    select_date = datetime.fromtimestamp(dt/1000).strftime("%Y-%m-%d")

    # update data
    exp_source.data = exp_data[exp_data['date'] == select_date]
    top10_source.data = top10_countries[top10_countries['date']==select_date]
    cont_source.data = cont_bars[cont_bars['date']==select_date]

    # update categorical plot range (countries) top-10 plot
    top10_plot.y_range.factors = country_range[country_range['date'] == select_date]['country'].iloc[0][::-1]

    # update title
    #map_plot.title.text = 'Covid cases per 1 Million inhabitants on ' + select_date

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


#### plots
## 1. barplot per continents
hover = HoverTool(tooltips=[('continent','@continent'),
                            ('confirmed','@confirmed_continent{,00}'),
                            ('deaths', '@deaths_continent{,00}'),
                            ('recovered', '@recovered_continent{,00}')]) # also add deaths, recovered

cont_plot = figure(title = 'Covid case per continent',
                   y_range = list(continent_colors.keys())[::-1],
                   plot_height = 300,
                   toolbar_location = None,
                   tools = [hover])

cont_plot.hbar(y='continent', right='confirmed_continent', color = 'color',
               source = cont_source, height=0.8)

cont_plot.xaxis.formatter = NumeralTickFormatter(format=",00")
cont_plot.ygrid.grid_line_color = None
cont_plot.x_range.start = 0


## 2. Barplot top 10 countries
hover = HoverTool(tooltips=[('continent','@continent'),
                            ('country','@country'),
                            ('confirmed','@confirmed{,00}'),
                            ('deaths', '@deaths{,00}'),
                            ('recovered', '@recovered{,00}')]) # also add deaths, recovered

top10_plot = figure(title = 'Top 10 countries with most Covid cases',
                    y_range = country_range[country_range['date'] == start_date]['country'].iloc[0][::-1],
                    plot_height=300,
                    toolbar_location = None,
                    tools=[hover])

top10_plot.hbar(y='country', right='confirmed', color = 'color',
       source = top10_source, height=0.8)

top10_plot.xaxis.formatter = NumeralTickFormatter(format=",00")
top10_plot.ygrid.grid_line_color = None
top10_plot.x_range.start = 0


## 3. Exponetial (growth) plot
hover = HoverTool(tooltips=[('continent','@continent'),
                            ('country','@country')])

# create the plot
exp_plot = figure(title = 'Growth progress of Covid in top-10 countries',
                  x_axis_type = 'log',
                  y_axis_type = 'log',
                  x_axis_label = 'Total confirmed cases',
                  y_axis_label = 'New cases last week',
                  plot_height = 600,
                  plot_width = 700,
                  toolbar_location = None,
                  tools=[hover])

# plot
exp_plot.multi_line(xs="confirmed", ys="new_last_week", line_color="color", alpha='alpha',
                    line_width=2, source=exp_source)

# get grey shaded & dashed baseline
n = int(min(x_max,y_max))
ln = np.logspace(0, int(n), int(n))
exp_plot.line(ln, ln, line_dash="4 4", line_width=1, color='gray')

# set axes
exp_plot.x_range.start = 10
exp_plot.xaxis.major_label_overrides = x_set
exp_plot.y_range.start = 10
exp_plot.yaxis.major_label_overrides = y_set


#### layout
layout = row(
             column(top10_plot, cont_plot),
             column(exp_plot,
                    row(date_slider, button, sizing_mode='scale_width')))

curdoc().add_root(layout)
curdoc().title = 'Covid-19'
