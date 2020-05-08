import numpy as np
import pandas as pd
from datetime import datetime

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
