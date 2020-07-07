import pandas as pd
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from src.data.quick_queries import queryDB
qdb = queryDB('sqlite','../../data/processed/covid_db.sqlite')


def cleanMainDataset(df, column_name):
    """
    Clean the COVID data acquired from John Hopkins University

    Parameters:
    df (dataframe) : dataframe to be cleaned, expecting a pivot-table with
                     country as index, date a column and column_name content
    column_name : output column representing content of the dataframe

    Returns:
    cleaned dataframe with columns ['country','date',column_name]
    """

    # rename columns
    df1 = df.copy()
    df1.rename(columns = {'Country/Region' : 'country',
                         'Province/State' : 'state',
                                    'Lat' : 'lat',
                                   'Long' : 'long'}, inplace = True)

    # remove country-data
    df1.drop(['lat','long'], axis = 1, inplace = True)

    # aggregate to country-level
    df_country = df1.groupby('country').sum().reset_index()
    assert df1[df1['country'] =='Australia']['5/7/20'].sum() == \
           df_country[df_country['country'] == 'Australia']['5/7/20'].iloc[0]

    # un-pivot table
    df2 = df_country.melt(id_vars = ["country"],
                         var_name = "date",
                       value_name = column_name)

    assert df2[(df2['country'] == 'Australia') & \
           (df2['date'] == '5/7/20')][column_name].iloc[0] == \
           df_country[df_country['country'] == 'Australia']['5/7/20'].iloc[0]

    # format date to 'yyyy-mm-dd
    df2['date'] = pd.to_datetime(df2['date'], format = '%m/%d/%y').astype(str)

    # remove inconsistent countries
    df2 = df2[~df2['country'].isin(['Diamond Princess','MS Zaandam','Kosovo'])]
    assert len(df2[df2['country'].isin(['Diamond Princess','MS Zaandam','Kosovo'])]) == 0

    # update names for consistency with other datasets
    trans_stats = {
                    "Cote d'Ivoire" : 'Ivory Coast',
                    'Burma' : 'Myanmar',
                    'Congo (Brazzaville)' : 'Congo',
                    'Congo (Kinshasa)' : 'DR Congo',
                    'West Bank and Gaza' : 'State of Palestine',
                    'Taiwan*' : 'Taiwan',
                    'Czechia' : 'Czech Republic',
                    'Korea, South' : 'South Korea',
                    'US' : 'United States'}
    df2.replace(trans_stats, inplace=True)
    assert len(df2[df2['country'].isin(list(trans_stats.keys()))]) == 0

    return df2


def download_data():
    """
    Dowload and clean the covid data from hardcoded endpoint.

    Parameters: None

    Returns:
    cleaned dataframe with columns ['country','date',column_name]
    """
    # base url to download csv data from github
    base_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/'

    # file-specific url
    files = {
        'global_confirmed' : 'time_series_covid19_confirmed_global.csv',
        'global_deaths' : 'time_series_covid19_deaths_global.csv',
        'global_recovered' : 'time_series_covid19_recovered_global.csv'
    }

    for metric in files.keys():
        # get the column name for the downloaded set
        col_name = metric.split('_')[-1]
        df_tmp = pd.read_csv(base_url + files[metric])

        # create output table
        if metric == list(files.keys())[0]:
            df = cleanMainDataset(df_tmp, col_name)
        else:
            df = df.merge(cleanMainDataset(df_tmp, col_name), on = ['country','date'])

    return df


def update_db():
    """
    Update the stats table with new data (new days). Note: this requires
    connetion to db to be established in qdb (quick_queries module).

    Parameters: None

    Returns: None (update db)
    """

    #download new data
    new_df = download_data()

    #check what data is to be added
    last_date = qdb.output_query("SELECT MAX(date) FROM stats").iloc[0][0]
    update_df = new_df[new_df['date'] > last_date]

    #update table
    update_df.to_sql('stats', con = qdb.engine, if_exists = 'append', index=False, chunksize = 1000)

    #check
    query = """
    SELECT date,
           COUNT(*) AS countries
      FROM stats
     GROUP BY date
     ORDER BY date DESC
     LIMIT 5;
    """
    last_day_check = qdb.output_query(query)
    assert last_day_check['date'].max() == update_df['date'].max()
    assert last_day_check['countries'].to_list() == [185, 185, 185, 185, 185]

    print('COVID data up-to-date till ' + last_day_check['date'].max())
