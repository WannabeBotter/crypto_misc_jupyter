import pandas as pd
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TimeScaleDBUtil:
    """
    TimeScaleDBを使って約定履歴とドルバー情報を保存、読み込むユーティリティクラス    
    パラメータ
    ----------
    user : str, 必須
        TimeScaleDBのユーザー名。
    password : str, 必須
        TimeScaleDBのパスワード。
    host : str, 必須
        TimeScaleDBのホスト名。
    port : str, 必須
        TimeScaleDBのポート番号。
    database : str, 必須
        TimeScaleDBのデータベース名。
    """
    def __init__(self, user = None, password = None, host = None, port = None, database = None):
        if user == None:
            raise ValueError(f'TimeScaleDBのユーザー名を指定してください')
        if password == None:
            raise ValueError(f'TimeScaleDBのパスワードを指定してください')
        if host == None:
            raise ValueError(f'TimeScaleDBのホスト名を指定してください')
        if port == None:
            raise ValueError(f'TimeScaleDBのポート番号を指定してください')
        if database == None:
            raise ValueError(f'TimeScaleDBのデータベース名を指定してください')
        
        _sqlalchemy_config = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
        self._engine = create_engine(_sqlalchemy_config)
        
        # enum_side型がデータベース上に存在することを確認し、ない場合は作成する
        _df = self.read_sql_query("SELECT * from pg_type WHERE typname='enum_side'")
        if _df.empty == True:
            self.sql_execute("CREATE TYPE enum_side AS ENUM ('buy', 'sell')")

    def read_sql_query(self, sql = None, index_column = '', dtype={}):
        """
        指定されたSQLを実行し、結果をデータフレームで返す関数
        パラメータ
        ----------
        sql : str, 必須
            実行するSQL文。
        index_column : str, default = ''
            出力するデータフレームのインデックスにする列名。
        dtype : dict, default = {}

        返り値
        -------
        df : pandas.DataFrame
            SQLクエリ結果を含んだデータフレーム。
        """
        if sql == None:
            raise ValueError(f'実行するSQL文を指定してください')
        if hasattr(self, '_engine') == False:
            raise UnboundLocalError('SQLAlchemyが初期化されていません')
        
        df = pd.read_sql_query(sql, self._engine, dtype=dtype)
        if len(index_column) > 0:
            df = df.set_index(index_column)
        return df
    
    def sql_execute(self, sql = None):
        """
        指定されたSQLを実行し、結果をlistで返す関数
        パラメータ
        ----------
        sql : str, 必須
            実行するSQL文。

        返り値
        -------
        SQLクエリ結果を含んだdict。
        """
        if sql == None:
            raise ValueError(f'実行するSQL文を指定してください')
        if hasattr(self, '_engine') == False:
            raise UnboundLocalError('SQLAlchemyが初期化されていません')
        
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
                f' CREATE TABLE IF NOT EXISTS "{_table_name}" (datetime TIMESTAMP WITH TIME ZONE NOT NULL, id text, side enum_side NOT NULL, liquidation BOOL NOT NULL, price NUMERIC NOT NULL, amount NUMERIC NOT NULL, dollar NUMERIC NOT NULL, dollar_cumsum NUMERIC NOT NULL, buy_dollar_cumsum NUMERIC NOT NULL, sell_dollar_cumsum NUMERIC NOT NULL, UNIQUE(datetime, id));'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC);'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC, dollar_cumsum);'
                f" SELECT create_hypertable ('{_table_name}', 'datetime');")
        self.sql_execute(_sql)
        
        # 累積出来高記録用Maerialized viewを作成
        _sql = (f'DROP MATERIALIZED VIEW IF EXISTS "{_table_name}_dollar_cumsum_daily" CASCADE;'
                f'CREATE MATERIALIZED VIEW "{_table_name}_dollar_cumsum_daily" WITH (timescaledb.continuous) AS SELECT time_bucket(INTERVAL "1 day", datetime) AS time, MAX(dollar_cumsum) AS dollar_cumsum, MAX(buy_dollar_cumsum) AS buy_dollar_cumsum, MAX(sell_dollar_cumsum) AS sell_dollar_cumsum, LAST(price, datetime) AS close FROM "{_table_mane}" GROUP BY time WITH NO DATA')
        self.sql_execute(_sql)
        
    def get_latest_trade(self, exchange='ftx', symbol='BTC-PERP'):
        _table_name = self.get_trade_table_name(exchange, symbol)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == True:
            return None
        
        _df = self.read_sql_query(f'WITH time_filtered AS (SELECT * FROM "{_table_name}" ORDER BY datetime DESC LIMIT 1000) SELECT * FROM time_filtered ORDER BY dollar_cumsum DESC LIMIT 1', dtype={'price': str, 'amount': str, 'dollar': str, 'dollar_cumsum': str, 'buy_dollar_cumsum': str, 'sell_dollar_cumsum': str})
        if len(_df) > 0:
            _to_decimal = lambda x: Decimal(x)
            _df['price'] = _df['price'].apply(_to_decimal)
            _df['amount'] = _df['amount'].apply(_to_decimal)
            _df['dollar'] = _df['dollar'].apply(_to_decimal)
            _df['dollar_cumsum'] = _df['dollar_cumsum'].apply(_to_decimal)
            _df['buy_dollar_cumsum'] = _df['buy_dollar_cumsum'].apply(_to_decimal)
            _df['sell_dollar_cumsum'] = _df['sell_dollar_cumsum'].apply(_to_decimal)
            return _df.iloc[0]
        
        return None
    
    def get_first_trade(self, exchange='ftx', symbol='BTC-PERP'):
        _table_name = self.get_trade_table_name(exchange, symbol)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == True:
            return None
        
        _df = self.read_sql_query(f'WITH time_filtered AS (SELECT * FROM "{_table_name}" ORDER BY datetime ASC LIMIT 1000) SELECT * FROM time_filtered ORDER BY dollar_cumsum ASC LIMIT 1', dtype={'price': str, 'amount': str, 'dollar': str, 'dollar_cumsum': str})
        if len(_df) > 0:
            _to_decimal = lambda x: Decimal(x)
            _df['price'] = _df['price'].apply(_to_decimal)
            _df['amount'] = _df['amount'].apply(_to_decimal)
            _df['dollar'] = _df['dollar'].apply(_to_decimal)
            _df['dollar_cumsum'] = _df['dollar_cumsum'].apply(_to_decimal)
            _df['buy_dollar_cumsum'] = _df['buy_dollar_cumsum'].apply(_to_decimal)
            _df['sell_dollar_cumsum'] = _df['sell_dollar_cumsum'].apply(_to_decimal)
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
                f' CREATE TABLE IF NOT EXISTS "{_table_name}" (datetime TIMESTAMP WITH TIME ZONE NOT NULL, datetime_from TIMESTAMP WITH TIME ZONE NOT NULL, id text, id_from text, open NUMERIC NOT NULL, high NUMERIC NOT NULL, low NUMERIC NOT NULL, close NUMERIC NOT NULL, amount NUMERIC NOT NULL, dollar_volume NUMERIC NOT NULL, dollar_buy_volume NUMERIC NOT NULL, dollar_sell_volume NUMERIC NOT NULL, dollar_liquidation_buy_volume NUMERIC NOT NULL, dollar_liquidation_sell_volume NUMERIC NOT NULL, dollar_cumsum NUMERIC NOT NULL, buy_dollar_cumsum NUMERIC NOT NULL, sell_dollar_cumsum NUMERIC NOT NULL, UNIQUE(datetime, id));'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC);'
                f' CREATE INDEX ON "{_table_name}" (datetime DESC, dollar_cumsum);'
                f" SELECT create_hypertable ('{_table_name}', 'datetime');")
        self.sql_execute(_sql)
        
    def get_latest_dollarbar(self, exchange='ftx', symbol='BTC-PERP', interval=5_000_000):
        _table_name = self.get_dollarbar_table_name(exchange, symbol, interval)
        
        _df = self.read_sql_query(f"select * from information_schema.tables where table_name='{_table_name}'")
        if _df.empty == True:
            return None
        
        _df = self.read_sql_query(f'SELECT * FROM "{_table_name}" ORDER BY datetime DESC, id DESC LIMIT 1', dtype={'open': str, 'high': str, 'low': str, 'close': str, 'amount': str, 'dollar_volume': str, 'dollar_buy_volume': str, 'dollar_sell_volume': str, 'dollar_liquidation_buy_volume': str, 'dollar_liquidation_sell_volume': str, 'dollar_cumsum': str})
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
            _df['buy_dollar_cumsum'] = _df['buy_dollar_cumsum'].apply(_to_decimal)
            _df['sell_dollar_cumsum'] = _df['sell_dollar_cumsum'].apply(_to_decimal)
            return _df.iloc[0]
        
        return None

    def load_dollarbars(self, exchange='ftx', symbol='BTC-PERP', interval=5_000_000, from_str=None, to_str=None):
        _table_name = self.get_dollarbar_table_name(exchange, symbol, interval)
        _sql = f"SELECT * FROM \"{_table_name}\" WHERE datetime >= '{from_str}' AND datetime < '{to_str}' ORDER BY dollar_cumsum ASC"
        
        _df = self.read_sql_query(sql = _sql)
        _df = _df[['datetime', 'open', 'high', 'low', 'close', 'dollar_volume', 'dollar_buy_volume', 'dollar_sell_volume', 'dollar_liquidation_buy_volume', 'dollar_liquidation_sell_volume', 'dollar_cumsum', 'buy_dollar_cumsum', 'sell_dollar_cumsum']]
        return _df
