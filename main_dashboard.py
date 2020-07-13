# change working directory to src/visualization
import os
os.chdir('src/visualization') # allow for local run via bokeh serve
print(os.getcwd())

# import tab capability bokeh
from bokeh.io import curdoc
from bokeh.models.widgets import Panel, Tabs

# update the DB to include new data if available
from src.data.process_data import update_db
update_db()

# import the dashboard pages/tabs
from src.visualization.growth_dashboard import growth_tab
from src.visualization.country_dashboard import country_tab

# create the tabls
country_tab = Panel(child = country_tab(), title = 'Countries')
growth_tab = Panel(child = growth_tab(), title = 'Growth')

# combine to final output
tabs = Tabs(tabs=[country_tab, growth_tab])

#### output
curdoc().add_root(tabs)
curdoc().title = 'Covid-19'
