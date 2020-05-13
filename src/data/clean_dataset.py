import numpy as np
import pandas as pd
import json
from datetime import datetime
from query_db import queryDB

# setup
qdb = queryDB('sqlite','../../data/processed/covid.sqlite')


class cleanData():

    def changeDateFormat(self, old_dates):
        """
        Convert an array of strings representing a date in format 'd-m-yy'
        to a string in format 'yyyy-mm-dd'
        """
        # extract individual date elements
        date_parts = old_dates.str.split('/', expand=True) # month
        date_parts.columns = ['month','day','year']

        # pad month and day to 2 digits
        date_parts.month = date_parts.month.str.pad(width=2, side='left',fillchar='0')
        date_parts.day = date_parts.day.str.pad(width=2, side='left',fillchar='0')

        # add '20' to year
        date_parts.year = np.repeat('20',len(date_parts)) + date_parts.year

        # get the full date
        return date_parts['year'] + '-' + date_parts['month'] + '-' + date_parts['day']



    def cleanData(self, df, title):
        """
        Convert raw data into a cleaned dataframe.
        Tests are done using data from Australia on 2020-05-07
        """
        # copy dataframe
        df_clean = df.copy()

        # rename columns
        df_clean.rename(columns = {'Country/Region' : 'country',
                                   'Province/State' : 'state',
                                   'Lat' : 'lat',
                                   'Long' : 'long'}, inplace=True)

        # remove unneeded columns
        df_clean.drop(['lat','long'], axis=1, inplace=True)

        # group by coutry and store in new df
        df_clean2 = df_clean.groupby('country').sum().reset_index()
        assert df_clean[df_clean['country']=='Australia']['5/7/20'].sum() == df_clean2[df_clean2['country']=='Australia']['5/7/20'].iloc[0]

        # move dates to a single row
        df_clean3 = df_clean2.melt(id_vars=["country"],
                                   var_name="date",
                                   value_name=title)
        assert df_clean3[(df_clean3['country']=='Australia') & (df_clean3['date']=='5/7/20')][title].iloc[0] == df_clean2[df_clean2['country']=='Australia']['5/7/20'].iloc[0]

        # update date format
        df_clean3['date'] = self.changeDateFormat(df_clean3.date)
        df_clean3['date'] = pd.to_datetime(df_clean3['date'], format="%Y-%m-%d")

        # change 'US' to 'United States'
        df_clean3.replace('US','United States', inplace=True)
        assert len(df_clean3[df_clean3['country']=='US']) == 0

        return df_clean3



    def updateCountry(self,table, original, replacement):
        """
        Change country from original to replacement in table
        """
        # clean countries based on hash table
        qdb.execute_query("""
            UPDATE {}
               SET country = '{}'
             WHERE country = '{}';""".format(table, replacement, original), ret=False)



        # clean (queries) -> SQL clean
    def cleanPopulation(self, raw_table = 'population_raw', target_table = 'populations',
                        country_trans_file = '../src/data/clean_country_names.json'):
        """
        Create populations table containing the cleaned population data
        """
        # clean data in raw table and store it in target table
        if raw_table in qdb.engine.table_names():
            qdb.execute_query('DROP TABLE IF EXISTS {};'.format(target_table), ret=False)
            qdb.execute_query("""
                CREATE TABLE {} AS
                SELECT rank,
                       country,
                       CAST(REPLACE(populations,',','') AS integer) AS population,
                       CAST(REPLACE(yearly_change,'%','') AS numeric) AS yearly_change_pct,
                       CAST(REPLACE(net_change,',','') AS integer) AS net_change,
                       CAST(density AS integer) AS density,
                       CAST(REPLACE(land_area,',','') AS integer) AS land_are,
                       CAST(REPLACE(migrants,',','') AS integer) AS migrants,
                       CAST(fert_rate AS numeric) AS fert_rate,
                       CAST(med_age AS integer) AS med_age,
                       CAST(REPLACE(urban_pop_pct,'%','') AS integer) AS urban_pop_pct,
                       CAST(REPLACE(world_share_pct,'%','') AS numeric) AS world_share_pct
                  FROM population_raw;""".format(target_table), ret=False)

            # remove invalid countries or countries without population data from stats table
            qdb.execute_query("""
                DELETE FROM stats
                 WHERE country IN ('Diamond Princess','MS Zaandam','Kosovo');""", ret=False)

            assert qdb.execute_query("""
                SELECT COUNT(*)
                  FROM stats
                 WHERE country IN ('Diamond Princess','MS Zaandam','Kosovo');""").iloc[0,0] == 0

            # open the country translation table
            with open(country_trans_file) as f:
                country_trans = json.loads(f.read())

            # clean countries in stats table
            for table in ['stats', 'populations']:
                # remove apostrophe in 'Core d'Ivor'
                qdb.execute_query("""
                    UPDATE {}
                       SET country = replace(country, char(39), '')
                     WHERE country LIKE 'C_te%';""".format(table), ret=False)

                # update individual countries
                for key in country_trans[table].keys():
                    self.updateCountry(table, key, country_trans[table][key])

            # check country conversion (missing keys..)
            assert qdb.execute_query("""
                    SELECT COUNT(DISTINCT stats.country) AS cnt
                      FROM stats
                           LEFT JOIN populations
                        ON populations.country = stats.country
                     WHERE populations.rank IS NULL;""").iloc[0,0] == 0 # update

            # drop SQL raw
            qdb.execute_query('DROP TABLE IF EXISTS {};'.format(raw_table), ret=False)

        else:
            print('error: raw data not available')
