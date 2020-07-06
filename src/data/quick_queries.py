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
        results as pandas dataframe
        """
        try:
            return pd.read_sql(query, con = self.engine, parse_dates = None)
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
