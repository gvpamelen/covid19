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
