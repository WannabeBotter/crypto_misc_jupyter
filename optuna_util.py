import pandas as pd
import numpy as np
import lightgbm as lgb
import optuna
import optuna.integration.lightgbm as lgb_optuna
import joblib

# LightGBM単体のCVとOptunaを使ったCVを手軽に使い分けるためのユーティリティクラス
class LightGBMRegressionUtil:
    # デフォルトのLightGBM用パラメータ
    DEFAULT_LGBM_PARAMS = {
        'objective':'regression',
        'metric': 'rmse',
        'verbosity': -1,
        'boosting_type': 'gbdt',
        'extra_trees': True,
        'deterministic': True,
        'force_row_wise': True,
        'num_threads': 8
    }
    
    def __init__(self):
        self.cvbooster = None
        return
    
    def train_cv(self, df_train = None, df_target = None, folds = None, use_optuna = False, **params):
        if len(params) == 0:
            self.params = self.DEFAULT_LGBM_PARAMS
        
        # データセットを作成        
        lgb_train_data = lgb.Dataset(df_train, df_target, free_raw_data=False)
        
        if use_optuna == True:
            tuner = optuna.integration.LightGBMTunerCV(self.params,
                                                            train_set = lgb_train_data,
                                                            folds = folds,
                                                            early_stopping_rounds = 100,
                                                            verbose_eval = 0,
                                                            show_progress_bar = False,
                                                            optuna_seed = 47,
                                                            return_cvbooster = True)
            tuner.run()
            self.cvbooster = tuner.get_best_booster()
        else:
            _eval_hist = lgb.cv(self.params,
                                train_set = lgb_train_data,
                                folds = folds,
                                early_stopping_rounds = 100,
                                verbose_eval = 0,
                                return_cvbooster = True)
            self.cvbooster = _eval_hist['cvbooster']
    
    def predict(self, df = None, folds = None, predict_training = False):
        df_predict = pd.DataFrame(self.cvbooster.predict(df, num_iteration=self.cvbooster.best_iteration))
        df_predict = df_predict.transpose()
        df_predict.index = df.index
        
        # foldsが与えられた場合、与えられたdfが学習時に使ったものと同一と仮定し、必要のないセクションの予測値をnanで上書きする
        if folds is not None:
            for index, fold in enumerate(folds):
                if predict_training == True:
                    set_necessary = set(fold[0])
                else:
                    set_necessary = set(fold[1])
                list_unwanted_index = [e for e in df_predict.index if e not in set_necessary]
                df_predict.iloc[list_unwanted_index, index] = np.nan
        return df_predict.mean(axis=1) # 残った予測値を使って平均値を計算する
    
    def save_model(self, filename = 'model.xz', compress=True):
        joblib.dump(self.cvbooster, filename, compress)
    
    def get_cvbooster(self):
        return self.cvbooster
