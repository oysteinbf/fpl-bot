import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

"""Util functions for the various fpl scripts"""

def EMA(df, column, span, min_periods, threshold_minutes):
    """Returns a new column with the Exponentially Weighted moving average of
    the input column. Note that df must be sorted on element, round
    Parameters
    ----------
    df : dataframe
    column: string with column name
    span, min_periods:
    threshold_minutes: minumum number of minutes played to be included in the average
    """
    df['EMA_column']=(df[df.minutes>threshold_minutes].groupby('element')[column]
                 .apply(lambda x: x.ewm(span=span,min_periods=min_periods,ignore_na=True)
                 .mean()))
    df['EMA_column']=df.groupby('element').ffill()['EMA_column'] #Replace nan which were due to minutes>threshold_minutes
    df['EMA_column']=df.groupby('element').shift(1)['EMA_column'] #Then shift within the groups
    
    return df['EMA_column']


def preprocess_data(df, bootstrap_static):
    elements=pd.DataFrame(bootstrap_static['elements']) #Player info
    team_list=pd.DataFrame(bootstrap_static['teams']) #Team info
    df=pd.merge(df,elements[['id','web_name','element_type','team','now_cost']],left_on='element',right_on='id')
    #elements['now_cost'] may be from the future, but does not matter much
    
    df=(pd.merge(df,team_list[['id','name','strength']],left_on='team',right_on='id',how='left')
        .rename(columns={'strength': 'strength_own_team', 'name': 'name_own_team'}))
    df=(pd.merge(df,team_list[['id','strength']],left_on='opponent_team',right_on='id', how='left')
        .rename(columns={'strength': 'strength_opponent_team'}))
    df=(pd.merge(df,team_list[['id','name']],left_on='opponent_team',right_on='id', how='left')
        .rename(columns={'name': 'name_opponent_team'}))
    
    df=df.drop(columns=['id','id_x', 'id_y','loaned_in', 'loaned_out']) #Remove leftovers from the merging etc.
    
    player_positions = {1 : 'GKP', 2 : 'DEF', 3 : 'MID', 4 : 'FWD' }
    df['position']=df['element_type'].apply(player_positions.get)
    return df

def categorise_cost(row):
    """Map total_cost to categories to reduce the variance in the predicion
       Return categorical or numerical values?!
       Or skip using cost as a feature?!
    """
    if row < 60:
        #return 'S'
        return 1
    elif row >= 60 and row < 80:
        #return 'M'
        return 2
    elif row >= 80 and row < 100:
        #return 'L'
        return 3
    elif row >= 100:
        #return 'XL'
        return 4

#Not used:    

def plot_y_predicted_vs_y_true(y_predicted,y_true,model_title):
    """Scatter plot of y_predicted vs y_true"""
    ymin=np.ceil(min(min(y_true), min(y_predicted)))
    ymax=np.ceil(max(max(y_true), max(y_predicted)))
    plt.plot([0, 25], [0, 25], color='r', linestyle='-', linewidth=2)
    plt.scatter(y_true, y_predicted)
    plt.xlabel('observed')
    plt.ylabel('predicted')
    plt.title('total_points'+', '+model_title)
    plt.xlim(ymin,ymax)
    plt.ylim(ymin,ymax)
    plt.show()


def rolling_mean(df, column, window):
    """Returns a new column with the rolling mean of
    the input column.\n
    Parameters
    ----------
    df : dataframe
    column: string with column name
    window: size of the moving window
    min_periods: also include this as a parameter?
    """
    new_column=(df.groupby('element')[column]
                 .shift(1)
                 .rolling(window)
                 .mean())
    return new_column


def print_player_features(df, features, playerID):
    foo=features.copy()
    foo.insert(0,'round')
    foo.insert(1,'total_points')
    print(df[df.element==playerID][foo])


#def print_metrics(y_true, y_predicted):
#    """Print various metrics"""
#    ma_error = mean_absolute_error(y_true, y_predicted)
#    mse = mean_squared_error(y_true, y_predicted)
#    test_score = r2_score(y_true, y_predicted)
#    spearman = spearmanr(y_true, y_predicted)
#    pearson = pearsonr(y_true, y_predicted)
#    print("Mean absolute error: {:.2f}".format(ma_error))
#    print("Mean squared error: {:.2f}".format(mse))
#    print("R-2 score: {:.2f}".format(test_score))
#    print("Spearman correlation: {:.2f}".format(spearman[0]))
#    print("Pearson correlation: {:.2f}".format(pearson[0]))
