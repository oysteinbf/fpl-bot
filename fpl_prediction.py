# -*- coding: utf-8 -*-
import fpl_utils
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn import linear_model
import configparser
import psycopg2
from psycopg2.extras import execute_values
pd.options.mode.chained_assignment = None  # default='warn'

"""Create table {main_schema}.prediction with predictions for each player"""

##Obtain data ********************************************************************
config = configparser.ConfigParser()
config.read('../config/fpl-bot.ini')
stage_dir = config.get('FILES', 'STAGE_DIR')
main_schema = config.get('DATABASE', 'MAIN_SCHEMA')

conn = psycopg2.connect(
    host=config.get('DATABASE', 'HOST'),
    database=config.get('DATABASE', 'DB'),
    user=config.get('DATABASE', 'USER'),
    password=config.get('DATABASE', 'PASSWORD'))

# TODO: Only select relevant columns
df = pd.read_sql(f'select * from {main_schema}.player_history order by element, round', conn)

##Generate features for prediction **************************************************************
#Try to map total_cost to categories to reduce the variance
df['cat_cost'] = df['value'].apply(fpl_utils.categorise_cost)

EMA_columns=['influence', 'creativity', 'threat', 'ict_index', 'bps', 'total_points']
# FPL has removed all the other information, so it is a bit scarce now..
for c in EMA_columns:
    df['EMA_'+c]=fpl_utils.EMA(df,column=c,span=2,min_periods=2,threshold_minutes=30)
features=['EMA_'+c for c in EMA_columns] + ['was_home','strength_own_team',
                    'strength_opponent_team']#,'cat_cost'] #use now_cost or cat_cost?!

##Prediction **********************************************************************************
#Might here add more training data from previous seasons
#The models have been fine-tuned in another notebook (train_test_split etc.)
ridge = Pipeline([('scl', StandardScaler()),
                  ('clf', linear_model.Ridge(alpha = 0.5))])

rf = RandomForestRegressor(n_estimators=200,n_jobs=-1, max_depth=5, 
         min_samples_leaf=100,min_samples_split=300)

df_prediction=pd.DataFrame()
for pos in ['GKP','DEF','MID','FWD']:
    pos_features=features  # May use different features for the different positions
    prediction_model = ridge  # May vary

    df['predict']=~df[pos_features].T.isnull().any()  # True if the features are non-NaN
    df.loc[df['total_points'].isnull(),'predict']=False  # False if total_points is Nan
    df.loc[df['round'].isnull(),'predict']=False  # False if round is Nan (non-assigned matches)
    df.loc[df['minutes']==0,'predict']=False # False if not played
    X=df[(df['position']==pos) & (df['predict']==True)][pos_features].values.astype('float64')
    y=df[(df['position']==pos) & (df['predict']==True)]['total_points'].values
    #print('X.shape: ',X.shape)
    #print('y.shape: ',y.shape)
    
    #Train:
    prediction_model.fit(X,y)

    #Predict:
    df['prediction']=~df[pos_features].T.isnull().any() ##Predict on everything that has all features
    #Do not include finished matches or other positions:
    df.loc[(df['finished']!=False) | (df['position']!=pos),'prediction']=False
    X_prediction=df[df['prediction']==True][pos_features].values
    y_prediction=prediction_model.predict(X_prediction.astype('float64'))
    foo=pd.DataFrame(data=y_prediction, index=df[df['prediction']==True].index)
    df['points']=foo #Overwrite with the actual predictions

    prediction=df[(df['finished']==False) & (df['position']==pos)] \
        [['round','element','web_name','name_own_team','position','points']]
        #'value','prediction']]
    df_prediction=df_prediction.append(prediction)

df_prediction['points_cumulative'] = df_prediction.groupby(['element'])['points']. \
    apply(lambda x: x.cumsum())
#df_prediction['value']=df_prediction['value']/10.

#Due to potential double gameweeks, get last score from each round
#TODO: Ensure 'prediction' are doubled for these GWs, not only 'pred_cumulative' (done below with .last())
remaining_rounds=df_prediction['round'].unique()
df_prediction=df_prediction.groupby(['element','round']).last().reset_index()
# TODO: Ensure double GWs are handled correctly (does the above work?). Also check blank GWs

with conn.cursor() as cur:
    cur.execute(f"truncate table {main_schema}.prediction")
    values = df_prediction[['element', 'round', 'points', 'points_cumulative']].values
    columns = ['element', 'round', 'points', 'points_cumulative']
    query = "INSERT INTO {}.prediction ({}) VALUES %s".format(main_schema, ','.join(columns))
    execute_values(cur, query, values)
conn.commit()
conn.close()
