import pandas as pd
from sqlalchemy import create_engine

class queryDB:
    def __init__(self, driver, filename):
        self.engine_string = driver+":///"+filename
        self.engine = create_engine(self.engine_string)
        self.conn = self.engine.connect()
        print(self.engine_string)


    def output_query(self, query, dates = None):
        """
        query the DB and return result as pandas dataframe

        Parameters:
        query (string) : sql query to be exectuted
        dates : columns to be parsed as date in the returned dataframe

        Returns:
        query result as pandas dataframe
        """
        try:
            return pd.read_sql(query, con = self.engine, parse_dates = dates)
        except Exception as e:
            print('unable to execute query')
            print("---")
            print(str(e))
            print("---")


    def admin_query(self,query):
        """
        query the DB where no return statement is expected (CREATE/INSERT/ALTER)

        Parameters:
        query (string) : sql query to be exectuted
        """
        try:
            self.conn.execute(query)
        except Exception as e:
            print('unable to execute query')
            print("---")
            print(str(e))
            print("---")


    def get_coutry_data(self):
        query = """
                WITH cases_rollup AS (
                        SELECT 'total' AS country,
                               date,
                               SUM(confirmed) AS confirmed,
                               SUM(deaths) AS deaths,
                               SUM(recovered) AS recovered
                          FROM stats
                         WHERE date >= '{}'
                         GROUP BY date

                         UNION

                        SELECT *
                          FROM stats
                         WHERE date >= '{}'),

                scaled_to_pop AS (
                    SELECT cases_rollup.country,
                           date,
                           confirmed,
                           deaths,
                           recovered,
                           CAST(confirmed/scaled_pop AS int) AS confirmed_scaled,
                           CAST(deaths/scaled_pop AS int) AS deaths_scaled,
                           CAST(recovered/scaled_pop AS int) AS recovered_scaled
                      FROM cases_rollup
                           LEFT JOIN (SELECT country,
                                             population/1000000.0 AS scaled_pop
                                        FROM populations) AS pops
                                  ON cases_rollup.country = pops.country),

                daily_stats AS (
                    SELECT *,
                           ROUND(deaths*1.0 / MAX(confirmed,1),2) AS death_rate,
                           COALESCE(confirmed - LAG(confirmed) OVER daily_window,0) AS daily_confirmed,
                           COALESCE(deaths - LAG(deaths) OVER daily_window,0) AS daily_deaths,
                           COALESCE(recovered - LAG(recovered) OVER daily_window,0) AS daily_recovered
                      FROM scaled_to_pop
                      WINDOW daily_window AS (PARTITION BY country ORDER BY date))

                SELECT *,
                       ROUND(AVG(daily_confirmed) OVER ma7,2) AS daily_confirmed_ma7,
                       ROUND(AVG(daily_deaths) OVER ma7,2) AS daily_deaths_ma7,
                       ROUND(AVG(daily_recovered) OVER ma7,2) AS daily_recovered_ma7,
                       DENSE_RANK() OVER (PARTITION BY date ORDER BY CAST(confirmed_scaled AS int)) AS conf_group
                FROM daily_stats
                WINDOW ma7 AS (PARTITION BY country ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
                ORDER BY date, country
                """.format('2020-02-01','2020-02-01')
        return self.output_query(query) # not required to reformat date


    def get_top10_countries(self):
        query = """
                SELECT date,
                       continent,
                       stats.country,
                       confirmed,
                       ROW_NUMBER() OVER (PARTITION BY date ORDER BY confirmed DESC, stats.country) AS conf_rnk,
                       deaths,
                       recovered,
                       SUM(confirmed) OVER continent_totals AS confirmed_continent,
                       SUM(deaths) OVER continent_totals AS deaths_continent,
                       SUM(recovered) OVER continent_totals AS recovered_continent,
                       ROW_NUMBER() OVER (PARTITION BY date, continent ORDER BY stats.country) AS plot_continent
                  FROM stats
                       JOIN populations
                         ON stats.country = populations.country
                 WHERE date >= '2020-02-01'
                 WINDOW continent_totals AS (PARTITION BY date, continent)
                 ORDER BY date, conf_rnk""" # dynamic start-date!?
        return self.output_query(query)


    def get_exp_data(self):
        query = """
                /* main data: confirmed & daily new. optional: got to weekly
                data, i.e. each Sunday when this becomes to granular */
                WITH exp_data AS (
                    SELECT continent,
                           stats.country,
                           date,
                           confirmed,
                           confirmed - LAG(confirmed) OVER (PARTITION BY stats.country ORDER BY date) AS daily_new,
                           ROW_NUMBER() OVER (PARTITION BY date ORDER BY confirmed DESC, stats.country) AS conf_rnk
                      FROM stats
                           JOIN populations
                             ON stats.country = populations.country),

                /* cut to relevant dates, get new cases last week
                and the minimum rank a country has ever had (has it ever
                been top-10) for later selection */
                relevant_data AS (
                    SELECT continent,
                           country,
                           date,
                           confirmed,
                           SUM(daily_new) OVER (PARTITION BY country ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS new_last_week,
                           conf_rnk,
                           MIN(conf_rnk) OVER (PARTITION BY country ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS min_rnk
                      FROM exp_data
                     WHERE date >= '2020-01-25')

               /* for multiline in bokeh we need all points per country.
               for quick plotting, we're pre-processing this by day (all points
               up till that date) in a string_agg (ideally would be array_agg)*/
                SELECT today.continent,
                       today.country,
                       today.date,
                       MIN(today.conf_rnk) AS conf_rnk,
                       MIN(today.min_rnk) AS min_rnk,
                       group_concat(past.confirmed) AS confirmed,
                       MAX(past.confirmed) AS confirmedmax,
                       group_concat(past.new_last_week) AS new_last_week,
                       MAX(past.new_last_week) AS new_last_weekmax
                  FROM relevant_data AS today
                       JOIN relevant_data AS past
                         ON today.date >= past.date
                         AND today.country = past.country
                 WHERE today.min_rnk <= 10
                 GROUP BY today.continent,
                          today.country,
                          today.date
                 ORDER BY today.country,
                          today.date"""
        return self.output_query(query)
