import pandas as pd
from sqlalchemy import create_engine

class queryDB:
    def __init__(self, driver, filename):
        self.engine_string = driver+":///"+filename
        self.engine = create_engine(self.engine_string)
        self.conn = self.engine.connect()
        print(self.engine_string)



    def execute_query(self, query, ret = True, dates = ['date']):
        """
        Execute query
        """
        try:
            if ret:
                res = pd.read_sql(query, con = self.engine, parse_dates = dates)
                print(str(len(res)) + " rows affected")
                return res
            else:
                self.conn.execute(query)

        except Exception as e:
            print('unable to execute query')
            print("---")
            print(str(e))
            print("---")


    def get_daily_stats_country(self, country):
        """
        Get details from daily_stats for a specific country
        """
        #query to exectuyre
        query = """
                SELECT *
                  FROM daily_stats
                 WHERE country = '{}';
                """.format(country)

        # run query
        return self.execute_query(query)
