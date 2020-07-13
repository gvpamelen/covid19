import numpy as np
import pandas as pd
import geopandas as gpd
import json
from bokeh.palettes import brewer


def get_country_colormap(bins=9):
    """
    Generate a colormapping. Required bokeh brewer palette

    Paramters: None

    Return: dictionary with number (1-9) and color
    """
    # create a colorscheme for 9 bins
    palette = brewer['Reds'][bins][::-1]
    colormap = {}

    for i in np.arange(bins):
        colormap[i+1] = palette[i] # start at 1 (NTILE on 1-9)

    return colormap


def country_plot_data(df, countries):
    """
    Get data to create a choropleth map

    Parameters:
    df (pandas dataframe): main dataframe with covid cases per country & day
    countries (geopandas dataframe): countries and geometry

    Returns:
    pandas dataframe with relevant data for choropleth map
    """
    # bin country on 1-9 by confirmed_cases per day ('partition')
    color_col = []
    for date in list(df['date'].unique()):
        ranks = df[df['date'] == date]['conf_group'] - 1 #-1 deals with the conf_group 1 for 'totals'
        max_rank = ranks.max()

        # if we have >9 ranks, map them back to 9
        if max_rank >= 9:
            bins = np.percentile(np.arange(max_rank+1), [0, 11, 22, 33, 44, 55, 66, 77, 88, 100]).round()
            ranks = pd.cut(ranks,  bins, labels = np.arange(9)+1)

        # assign a color from bokeh brewer
        colormap = get_country_colormap()
        color_col.append(ranks.replace(colormap))

        # add the color columns - ordering is safe since DF is ordered by date, country
    df['color'] = np.array(color_col).flatten()

    # left merge to include 'countries' without data (i.e. Greenland)
    # no need to keep totals here.
    plot_data = countries.merge(df, on = 'country', how = 'left')

    # plot countries where we have no data (i.e. Greenland) as grey.
    plot_data['color'] = plot_data['color'].fillna('#d9d9d9')

    # select relevant columns used in plot
    cols = ['date','country','geometry','confirmed_scaled','deaths_scaled','color']

    return plot_data[cols]


def prep_geojson(df, date):
    """
    Create a geojson to serve a bokeh GeoJSONdatasource

    Parameters:
    df (geopandas dataframe): data to be plotted for multiple days
    date (string): date for which to select data in df

    Returns:
    json object (string) to serve as bokeh GeoJSONdatasource
    """
    # also include NA (countries with no data and hence no date i.e. Greenland)
    plot_day = df[(df['date'] == date) | (df['date'].isna())]

    #Read data to json
    merged_json = json.loads(plot_day.to_json())

    #Convert to String like object.
    json_data = json.dumps(merged_json)
    return json_data


def prep_exp_plot(df, main_alpha = 1.0, non_selection_alpha = 0.2):
    """
    Convert string_agg object to an array of ints and add an alpha Column
    for plotting bases in wether or not a country is in top-10 most cases

    Parameters:
    df (pandas dataframe): base dataframe for exponential plot
                           (output of qdb.get_exp_data)
    main_alpha (float): base alpha value in plot (default = 1)
    non_selection_alpha (float): alpha for values not in top-10 (default = 0.2)

    Returns:
    df (pandas dataframe)
    """
    # add alpha
    df['alpha'] = (df['conf_rnk'] <= 10) * (main_alpha - non_selection_alpha) + non_selection_alpha

    # apply function to row of pandas df
    df['confirmed'] = df['confirmed'].apply(lambda x: np.array(x.split(',')).astype(int))
    df['new_last_week'] = df['new_last_week'].apply(lambda x: np.array(x.split(',')).astype(int))

    return df


def setAxes(exp):
    """
    Create ticks & ticklabels for the double-log growth plot

    Parameters:
    exp: pandas dataframe containing at least the columns `confirmedmax`
         and `new_last_weekmax`

    Returns:
    x_set: dictionary of tick locations & tick labels for the x-axis
    y_set: dictionary of tick locations & tick labels for the x-axis
    x_max: maximum x-position (log)
    y_max: maximum y-position (log)
    """
    # find the range required
    x_max = np.ceil(np.log10(exp.confirmedmax.max()))
    y_max = np.ceil(np.log10(exp.new_last_weekmax.max()))

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
