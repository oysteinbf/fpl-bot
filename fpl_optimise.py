from argparse import ArgumentParser
import pandas as pd
import numpy as np
import requests
import pulp
import configparser
import psycopg2
pd.options.mode.chained_assignment = None  # default='warn'
pd.set_option('display.precision', 1)

"""Optimise team and suggest transfers based on predictions"""

parser = ArgumentParser()
parser.add_argument("-i", "--team_id", type=int, dest="team_id", help="Team ID, e.g. 5977880")
parser.add_argument("-t", "--n_transfers", type=int, dest="n_transfers", help="Number of transfers to suggest")
parser.add_argument("-r", "--n_round", type=int, dest="n_round", help="Number of rounds (game weeks) ahead to predict")
args = parser.parse_args()

team_id = args.team_id
n_transfers = args.n_transfers
n_round = args.n_round

config = configparser.ConfigParser()
config.read('../config/fpl-bot.ini')
stage_dir = config.get('FILES', 'STAGE_DIR')
main_schema = config.get('DATABASE', 'MAIN_SCHEMA')

conn = psycopg2.connect(
    host=config.get('DATABASE', 'HOST'),
    database=config.get('DATABASE', 'DB'),
    user=config.get('DATABASE', 'USER'),
    password=config.get('DATABASE', 'PASSWORD'))

# Get prediction data together with the latest cost for each player
sql = f"""with ranked_value as (
           select element, round, value,
           row_number() over (partition by element order by round desc) as rn 
           from {main_schema}.player_history where value is not null)
         select p.*, ph."position", ph.web_name, ph.name_own_team, rv.value/10.0 as now_cost
          from {main_schema}.prediction p join {main_schema}.player_history ph
           on ph."element" = p."element" and  ph.round = p.round
           left join ranked_value rv on ph."element" = rv.element
           where rv.rn=1;"""
df_prediction = pd.read_sql(sql, conn)
conn.close()


## Optimize team *************************************
previous_round = int(df_prediction['round'].min() - 1) # The gameweek must be completely finished

team_picks=requests.get('https://fantasy.premierleague.com/api/entry/'+str(team_id)+ \
    '/event/'+str(previous_round)+'/picks/').json()
df_team=pd.DataFrame(team_picks['picks'])
my_team_list=list(df_team.element)
#my_team_list=[400, 247, 28, 267, 40, 276, 433, 253, 22, 45, 280, 445, 149, 142, 427] #If testing
money_bank = team_picks['entry_history']['bank']/10.

df_prediction['next_fixture'] = df_prediction.groupby(by=['element'])['round'].transform(lambda x: x.rank())

# Should perhaps only use 1 round ahead here? Or compare several rounds ahead?
my_team=df_prediction[(df_prediction.element.isin(my_team_list)) & \
     (df_prediction.next_fixture==n_round)]
my_team=pd.concat([my_team,pd.get_dummies(my_team[['position', 'name_own_team']])],axis=1)
my_team['points_cumulative']=my_team['points_cumulative'].fillna(0)

#Okay then optimize:
print('Finding the optimal formation (without making transfers):')
possible_formations=['1-4-4-2','1-4-3-3','1-4-5-1','1-3-5-2','1-3-4-3', \
    '1-5-4-1','1-5-3-2','1-5-2-3']
max_score=0
for i, formation in enumerate(possible_formations):
    #### Initialise the problem and define the objective function
    fpl_problem = pulp.LpProblem('FPL', pulp.LpMaximize)
    players=my_team.element
    # create a dictionary of pulp variables with keys from names
    x = pulp.LpVariable.dict('x % s', players, lowBound=0, upBound=1,cat=pulp.LpInteger)
    # player score data
    player_points = dict(zip(my_team.element, np.array(my_team.points_cumulative)))
    # objective function
    fpl_problem += sum([player_points[i] * x[i] for i in players])
    #### Set and apply constraints
    position_names = ['GKP', 'DEF', 'MID', 'FWD']
    position_constraints = [int(i) for i in formation.split('-')]
    constraints = dict(zip(position_names, position_constraints))
    #constraints['total_cost'] = 100 #Not needed here?
    constraints['total_players'] = 11 #Select 11 out of 15
    player_cost = dict(zip(my_team.element, my_team.now_cost))
    player_gkp=my_team[my_team.position_GKP==1]['element'].values
    player_def=my_team[my_team.position_DEF==1]['element'].values
    player_mid=my_team[my_team.position_MID==1]['element'].values
    player_fwd=my_team[my_team.position_FWD==1]['element'].values

    #apply the constraints
    #fpl_problem += sum([player_cost[i] * x[i] for i in players]) <= float(constraints['total_cost'])
    fpl_problem += sum([x[i] for i in player_gkp]) == constraints['GKP']
    fpl_problem += sum([x[i] for i in player_def]) == constraints['DEF']
    fpl_problem += sum([x[i] for i in player_mid]) == constraints['MID']
    fpl_problem += sum([x[i] for i in player_fwd]) == constraints['FWD']
    fpl_problem += sum([x[i] for i in players]) == constraints['total_players']
    #print(fpl_problem)

    ####Solve
    fpl_problem.solve(pulp.PULP_CBC_CMD(msg=0))
    #print("Status:", pulp.LpStatus[fpl_problem.status])
    #for v in fpl_problem.variables(): print(v.name, "=", v.varValue)
    maximised_points=pulp.value(fpl_problem.objective)
    print("{} round(s) ahead with formation {}, the optimal team predicts {:.1f} points".format(n_round,\
         formation,maximised_points))
    if maximised_points>=max_score:
        max_score=maximised_points
        best_formation=formation
        foo=[[int(v.name[2:]), v.varValue] for v in fpl_problem.variables()]
        chosen_players=[v[0] for v in foo if v[1]==1]
        optimal_my_team=my_team[my_team.element.isin(chosen_players)][['element','web_name',\
            'name_own_team','position','now_cost','points_cumulative']]
        bench_my_team=my_team[~my_team.element.isin(chosen_players)][['element','web_name',\
            'name_own_team','position','now_cost','points_cumulative']]

sort_order = {'GKP': 0, 'DEF': 1, 'MID': 2, 'FWD': 3}
print("{} round(s) ahead with formation {}, the optimal team predicts {:.1f} points (the highest score)\n".format(n_round, \
    best_formation,max_score))
print('Optimal team (without making any transfers):')
print(optimal_my_team.drop('element',axis=1).sort_values(by=['position'], key=lambda x: x.map(sort_order)).to_string(index=False))
print("\nBench:\n", bench_my_team.drop('element',axis=1).sort_values(by=['position'], key=lambda x: x.map(sort_order)).to_string(index=False))

### Find optimal transfers
# Note: There are some issues with blank GWs, the points should perhaps be set to zero where there are no matches
available_players=df_prediction[(df_prediction.next_fixture==n_round) & \
    (df_prediction.points_cumulative.notnull())].reset_index(drop=True)
available_players=pd.concat([available_players,pd.get_dummies(\
    available_players[['position', 'name_own_team']])],axis=1)
available_players.loc[available_players['element'].isin(my_team.element),'my_team']=1

team_value = optimal_my_team.now_cost.sum()
available_budget = team_value + money_bank
print("\nTeam value (11 players): {:,.1f}\nMoney in bank: {}".format(team_value, money_bank))

fpl_problem = pulp.LpProblem('FPL', pulp.LpMaximize)
players=available_players.element
# create a dictionary of pulp variables with keys from names
x = pulp.LpVariable.dict('x % s', players, lowBound=0, upBound=1,cat=pulp.LpInteger)
# player score data
player_points = dict(zip(available_players.element, np.array(available_players.points_cumulative)))
# objective function
fpl_problem += sum([player_points[i] * x[i] for i in players])

#### Set and apply constraints
formation=best_formation
position_names = ['GKP', 'DEF', 'MID', 'FWD']
position_constraints = [int(i) for i in formation.split('-')]
constraints = dict(zip(position_names, position_constraints))
constraints['total_cost'] = available_budget
constraints['team'] = 3
constraints['total_players'] = 11 #Select 11 out of all available (skip the bench)
constraints['players_previous_team'] = 11-n_transfers

player_cost = dict(zip(available_players.element, available_players.now_cost))
player_gkp=available_players[available_players.position_GKP==1]['element'].values
player_def=available_players[available_players.position_DEF==1]['element'].values
player_mid=available_players[available_players.position_MID==1]['element'].values
player_fwd=available_players[available_players.position_FWD==1]['element'].values

#apply the constraints
fpl_problem += sum([player_cost[i] * x[i] for i in players]) <= float(constraints['total_cost'])
fpl_problem += sum([x[i] for i in player_gkp]) == constraints['GKP']
fpl_problem += sum([x[i] for i in player_def]) == constraints['DEF']
fpl_problem += sum([x[i] for i in player_mid]) == constraints['MID']
fpl_problem += sum([x[i] for i in player_fwd]) == constraints['FWD']
fpl_problem += sum([x[i] for i in players]) == constraints['total_players'] #Choose 11 players
fpl_problem += sum([x[i] for i in optimal_my_team.element.values]) == constraints['players_previous_team']
#Ok? But what about the bench? Remove or what?

# Try to fix team constraint
for t in available_players.name_own_team:
    player_team = dict(
        zip(available_players.element, available_players['name_own_team_' + str(t)]))
    fpl_problem += sum([player_team[i] * x[i] for i in players]) <= constraints['team']
# What about cost?

###Solve
fpl_problem.solve(pulp.PULP_CBC_CMD(msg=0))
#print("Status:", pulp.LpStatus[fpl_problem.status])
#for v in fpl_problem.variables(): print(v.name, "=", v.varValue)
maximised_points=pulp.value(fpl_problem.objective)

foo=[[int(v.name[2:]), v.varValue] for v in fpl_problem.variables()]
chosen_players=[v[0] for v in foo if v[1]==1]
new_team=available_players[available_players.element.isin(chosen_players)][['element','web_name',\
    'name_own_team','position','now_cost','points_cumulative']]

set1=set(optimal_my_team.element.values) #Original team
set2=set(new_team.element.values)
players_out=df_prediction[(df_prediction.element.isin(set1.difference(set2))) & \
    (df_prediction.next_fixture==n_round)]
players_in=df_prediction[(df_prediction.element.isin(set2.difference(set1))) & \
    (df_prediction.next_fixture==n_round)]
print("\nSuggested transfers (using formation {}):\n Out:\n {}\n\n In:\n {}".format(best_formation, players_out[['web_name', 'name_own_team', 'position', 'now_cost', 'points_cumulative']].to_string(index=False), players_in[['web_name', 'name_own_team', 'position', 'now_cost', 'points_cumulative']].to_string(index=False)))

print("\n{} round(s) ahead with formation {}, the optimal team predicts {:.1f} points with the following team:".\
    format(n_round, formation,maximised_points))
print(new_team.drop('element',axis=1).sort_values(by=['position'], key=lambda x: x.map(sort_order)).to_string(index=False))
