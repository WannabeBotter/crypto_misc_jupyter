import pandas as pd
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TimeScaleDBUtil:
    def __init__(self, user = None, password = None, host = None, port = None, database = None):
        self._user = user
        self._password = password
        self._host = host
        self._port = port
        self._database = database
        
        self._sqlalchemy_config = f'postgresql+psycopg2://{self._user}:{self._password}@{self._host}:{self._port}/{self._database}'
        self._engine = create_engine(self._sqlalchemy_config)
        
        # enum_side型の存在を確認し、なければ作る
        _df = self.read_sql_query("SELECT * from pg_type WHERE typname='enum_side'")
        if _df.empty == True:
            self.sql_execute("CREATE TYPE enum_side AS ENUM ('buy', 'sell')")

    def read_sql_query(self, sql = '', index_column = '', dtype={}):
        df = pd.read_sql_query(sql, self._engine, dtype=dtype)
        if len(index_column) > 0:
            df = df.set_index(index_column)
        return df
    
    def sql_execute(self, sql = ''):
        return self._engine.execute(sql)
    
    def df_to_sql(self, df = None, schema = None, if_exists = 'fail'):
        if df.empty or schema == None:
            return  
        return df.to_sql(schema, con = self._engine, if_exists = if_exists, index = False)
    
    ### 約定履歴テーブル関係の処理
    def get_trade_table_name(self, exchange, symbol):
        return (f'{exchange}_{symbol}_trade').lower()
    
    def init_trade_table(self, exchange='binance', symbol='BTC/USDT', force=False):    
        _table_name = self.get_trade_table_name(exchange, symbol)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == False and force == False:
            return
        
        # トレード記録テーブルを作成
        _sql = (f'DROP TABLE IF EXISTS "{_table_name}" CASCADE;'
                f' CREATE TABLE IF NOT EXISTS "{_table_name}" (datetime TIMESTAMP WITH TIME ZONE NOT NULL, id text, side enum_side NOT NULL, liquidation BOOL NOT NULL, price NUMERIC NOT NULL, amount NUMERIC NOT NULL, dollar NUMERIC NOT NULL, dollar_cumsum NUMERIC NOT NULL, UNIQUE(datetime, id));'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC);'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC, dollar_cumsum);'
                f" SELECT create_hypertable ('{_table_name}', 'datetime');")
        self.sql_execute(_sql)
        
    def get_latest_trade(self, exchange='ftx', symbol='BTC-PERP'):
        _table_name = self.get_trade_table_name(exchange, symbol)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == True:
            return None
        
        _df = self.read_sql_query(f'SELECT * FROM "{_table_name}" ORDER BY dollar_cumsum DESC LIMIT 1', dtype={'price': str, 'amount': str, 'dollar': str, 'dollar_cumsum': str})
        if len(_df) > 0:
            _to_decimal = lambda x: Decimal(x)
            _df['price'] = _df['price'].apply(_to_decimal)
            _df['amount'] = _df['amount'].apply(_to_decimal)
            _df['dollar'] = _df['dollar'].apply(_to_decimal)
            _df['dollar_cumsum'] = _df['dollar_cumsum'].apply(_to_decimal)
            return _df.iloc[0]
        
        return None
    
    def get_first_trade(self, exchange='ftx', symbol='BTC-PERP'):
        _table_name = self.get_trade_table_name(exchange, symbol)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == True:
            return None
        
        _df = self.read_sql_query(f'SELECT * FROM "{_table_name}" ORDER BY dollar_cumsum ASC LIMIT 1', dtype={'price': str, 'amount': str, 'dollar': str, 'dollar_cumsum': str})
        if len(_df) > 0:
            _to_decimal = lambda x: Decimal(x)
            _df['price'] = _df['price'].apply(_to_decimal)
            _df['amount'] = _df['amount'].apply(_to_decimal)
            _df['dollar'] = _df['dollar'].apply(_to_decimal)
            _df['dollar_cumsum'] = _df['dollar_cumsum'].apply(_to_decimal)
            return _df.iloc[0]
        
        return None
    
    ### ドルバーテーブル関係の処理
    def get_dollarbar_table_name(self, exchange, symbol, interval):
        return (f'{exchange}_{symbol}_dollarbar_{interval}').lower()
    
    def init_dollarbar_table(self, exchange='ftx', symbol='BTC-PERP', interval=10_000_000, force=False):    
        _table_name = self.get_dollarbar_table_name(exchange, symbol, interval)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == False and force == False:
            return
        
        # ドルバー記録テーブルを作成
        _sql = (f'DROP TABLE IF EXISTS "{_table_name}" CASCADE;'
                f' CREATE TABLE IF NOT EXISTS "{_table_name}" (datetime TIMESTAMP WITH TIME ZONE NOT NULL, datetime_from TIMESTAMP WITH TIME ZONE NOT NULL, id text, id_from text, open NUMERIC NOT NULL, high NUMERIC NOT NULL, low NUMERIC NOT NULL, close NUMERIC NOT NULL, amount NUMERIC NOT NULL, dollar_volume NUMERIC NOT NULL, dollar_buy_volume NUMERIC NOT NULL, dollar_sell_volume NUMERIC NOT NULL, dollar_liquidation_buy_volume NUMERIC NOT NULL, dollar_liquidation_sell_volume NUMERIC NOT NULL, dollar_cumsum NUMERIC NOT NULL, UNIQUE(datetime, id));'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC);'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC, dollar_cumsum);'
                f" SELECT create_hypertable ('{_table_name}', 'datetime');")
        self.sql_execute(_sql)
        
    def get_latest_dollarbar(self, exchange='ftx', symbol='BTC-PERP', interval=10_000_000):
        _table_name = self.get_dollarbar_table_name(exchange, symbol, interval)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == True:
            return None
        
        _df = self.read_sql_query(f'SELECT * FROM "{_table_name}" ORDER BY datetime DESC, id DESC LIMIT 1', dtype={'open': str, 'high': str, 'low': str, 'close': str, 'amount': str, 'dollar_volume': str, 'dollar_buy_volume': str, 'dollar_sell_volume': str, 'dollar_cumsum': str})
        if len(_df) > 0:
            _to_decimal = lambda x: Decimal(x)
            _df['open'] = _df['open'].apply(_to_decimal)
            _df['high'] = _df['high'].apply(_to_decimal)
            _df['low'] = _df['low'].apply(_to_decimal)
            _df['close'] = _df['close'].apply(_to_decimal)
            _df['amount'] = _df['amount'].apply(_to_decimal)
            _df['dollar_volume'] = _df['dollar_volume'].apply(_to_decimal)
            _df['dollar_buy_volume'] = _df['dollar_buy_volume'].apply(_to_decimal)
            _df['dollar_sell_volume'] = _df['dollar_sell_volume'].apply(_to_decimal)
            _df['dollar_liquidation_buy_volume'] = _df['dollar_liquidation_buy_volume'].apply(_to_decimal)
            _df['dollar_liquidation_sell_volume'] = _df['dollar_liquidation_sell_volume'].apply(_to_decimal)
            _df['dollar_cumsum'] = _df['dollar_cumsum'].apply(_to_decimal)
            return _df.iloc[0]
        
        return None
