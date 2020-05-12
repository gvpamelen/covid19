# import
import pandas as pd
import ssl
from clean_dataset import cleanData
from query_db import queryDB

# setup
cd = cleanData()
qdb = queryDB('sqlite','../../data/processed/covid.sqlite')
ssl._create_default_https_context = ssl._create_unverified_context


# functions
def getRawData():
    """
    get raw covid-19 data from John Hopkin's github
    separate files needed for confirmed cases, deaths and recovered
    """
    # base url to download csv data from github
    base_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/'
    files = {
            'global_confirmed' : 'time_series_covid19_confirmed_global.csv',
            'global_deaths' : 'time_series_covid19_deaths_global.csv',
            'global_recovered' : 'time_series_covid19_recovered_global.csv'}

    # use try-except to deal with external data-sources
    try:
        confirmed_raw = pd.read_csv(base_url + files['global_confirmed'])
        death_raw = pd.read_csv(base_url + files['global_deaths'])
        recovered_raw = pd.read_csv(base_url + files['global_recovered'])

    except Exception as e:
        print('unable to get new data')
        print("---")
        print(str(e))
        print("---")

        # use backup data where needed
        # # TODO: check if these paths are correct (one more dir up??)
        confirmed_raw = pd.read_csv('../data/raw/global_confirmed.csv')
        death_raw = pd.read_csv('../data/raw/global_deaths.csv')
        recovered_raw = pd.read_csv('../data/raw/global_recovered.csv')

    return confirmed_raw, death_raw, recovered_raw


def createStats(confirmed_raw, death_raw, recovered_raw):
    """
    clean the 3 datasets - following data_cleaning notebook
    output a single dataframe with confirmed, death and recovered as columns
    """
    # clean data
    confirmed_cleaned = cd.cleanData(confirmed_raw,'confirmed')
    death_cleaned = cd.cleanData(death_raw,'death')
    recovered_cleaned = cd.cleanData(recovered_raw,'recovered')

    # combine the dataframes
    return confirmed_cleaned.merge(death_cleaned, on = ['country','date'], how='inner').merge(recovered_cleaned, on = ['country','date'], how='inner')


def createCountry(confirmed_raw):
    """
    create the country dataframe
    """
    # create the country dataframe
    country_data = confirmed_raw[['Province/State','Country/Region','Lat','Long']]
    country_data.columns = ['country','state','lat','long']
    return country_data


def checkDateDB():
    """
    get the last date (latest) from the stats tabel
    """
    # run a check
    query = """
    SELECT MAX(date) AS date
      FROM stats
    """
    latest_date = qdb.execute_query(query).iloc[0,0]
    return latest_date


def checkCountDB(table):
    """
    get the amount of records in the table
    """
    if table in qdb.engine.table_names():
        # run a check
        query = """
        SELECT COUNT(*) AS rows
          FROM {}
        """.format(table)
        row_count = qdb.execute_query(query).iloc[0,0]
        return row_count
    else:
        return 0


def updateTable(df, table):
    """
    hard update of a table: drop and re-create from the dataframe
    """
    # older data can be updated as well, do drop current table
    qdb.execute_query("""DROP TABLE IF EXISTS {};""".format(table))

    # load new table
    df.to_sql(table, con = qdb.engine, if_exists = 'append', index=False, chunksize = 1000)
    print('updated table {}'.format(table))


def checkAndUpdate(combined, country_data):
    """
    check if we have new data for the tables
    update when this is the case
    """
    ## stats table
    print('STATS TABLE')
    if len(combined) > checkCountDB('stats'):
        updateTable(combined, 'stats')
        print('DB up-to-date till: ', checkDateDB())
    else:
        print('no new data found')
        print('DB up-to-date till: ', checkDateDB())

    #stats table
    print('---')
    print('COUNTRY TABLE')
    if len(country_data) > checkCountDB('country'):
        updateTable(country_data, 'country')
    else:
        print('no new data found')


#### create daily_stats
def createDailyStats(table):
    """
    create a table with daily cases per date and country_data
    contains the raw valyes (confirmed, deaths annd recovered) and 7-day MA
    """
    # drop table if exists
    qdb.execute_query("""DROP TABLE IF EXISTS {};""".format(table))

    # create the table
    qdb.execute_query("""
    CREATE TABLE {} AS
    SELECT country,
           DATE(date) AS date,
           conf_today - conf_yesterday AS confirmed,
           death_today - death_yesterday AS death,
           recov_today - recov_yesterday AS recovered,
           AVG(conf_today - conf_yesterday) OVER (PARTITION BY country ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS confirmed_ma,
           AVG(death_today - death_yesterday) OVER (PARTITION BY country ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS death_ma,
           AVG(recov_today - recov_yesterday) OVER (PARTITION BY country ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS recovered_ma
      FROM (SELECT today.country,
                   today.date,
                   today.confirmed AS conf_today,
                   today.death AS death_today,
                   today.recovered AS recov_today,
                   yesterday.confirmed AS conf_yesterday,
                   yesterday.death AS death_yesterday,
                   yesterday.recovered AS recov_yesterday
              FROM stats AS today
                   JOIN stats AS yesterday
                   ON today.country = yesterday.country
                      AND DATE(yesterday.date) = DATE(today.date,'-1 day')) sub;""".format(table))
    # check
    assert(table in qdb.engine.table_names())
    print('created table: ',table)



def main():
    # get data from online_source
    ## TODO: refractior getRawData() -- loop!?
    confirmed_raw, death_raw, recovered_raw = getRawData()

    ## TODO: only run this section when the above worked
    # clean_data
    combined = createStats(confirmed_raw, death_raw, recovered_raw)
    country_data = createCountry(confirmed_raw)

    # update primary tables
    checkAndUpdate(combined, country_data)

    # create new table
    createDailyStats('daily_stats')

    ## TODO: update the backup (raw csv's when needed)
    ## TODO: add some documentation



if __name__ == '__main__':
    main()