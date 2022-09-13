import os
import psycopg2
from psycopg2.extras import execute_values
import configparser
import io
import json
import re

"""
Populate database tables from files in the staging area with truncate and fill strategy
"""

config = configparser.ConfigParser()
config.read('../config/fpl-bot.ini')
stage_dir = config.get('FILES', 'STAGE_DIR')
stg_schema = config.get('DATABASE', 'STAGE_SCHEMA')
main_schema = config.get('DATABASE', 'MAIN_SCHEMA')
backup_schema = config.get('DATABASE', 'BACKUP_SCHEMA')

conn = psycopg2.connect(
    host=config.get('DATABASE', 'HOST'),
    database=config.get('DATABASE', 'DB'),
    user=config.get('DATABASE', 'USER'),
    password=config.get('DATABASE', 'PASSWORD'))

cur = conn.cursor()

with io.open(os.path.join(stage_dir,'bootstrap_static.json'), encoding='utf-8') as data_file:
    bootstrap_static = json.loads(data_file.read())

with io.open(os.path.join(stage_dir,'fixtures.json'), encoding='utf-8') as data_file:
    fixtures = json.loads(data_file.read())

# Truncate tables
for table in ['stg_element_types', 'stg_fixtures', 'stg_player_static', 'stg_player_history',
                'stg_teams']:
    cur.execute(f"TRUNCATE TABLE {stg_schema}.{table}")
    

# stg_teams
teams = bootstrap_static['teams']
columns = teams[0].keys()
values =  [list(x.values()) for x in teams]
query = "INSERT INTO {}.stg_teams ({}) VALUES %s".format(stg_schema, ','.join(columns))
#print(query)
execute_values(cur, query, values)

# stg_player_static
player_static = bootstrap_static['elements']
columns = player_static[0].keys()
values = [list(x.values()) for x in player_static]
query = "INSERT INTO {}.stg_player_static ({}) VALUES %s".format(stg_schema, ','.join(columns))
execute_values(cur, query, values)

# stg_element_types
element_types = bootstrap_static['element_types']
columns = element_types[0].keys()
values =  [list(x.values()) for x in element_types]
query = "INSERT INTO {}.stg_element_types ({}) VALUES %s".format(stg_schema, ','.join(columns))
execute_values(cur, query, values)

# stg_fixtures (don't include stats for now)
columns = list(fixtures[0].keys())
columns.remove('stats')
values =  [list({i:x[i] for i in x if i!='stats'}.values()) for x in fixtures]
query = "INSERT INTO {}.stg_fixtures ({}) VALUES %s".format(stg_schema, ','.join(columns))
execute_values(cur, query, values)

# stg_player_history
for player_file in os.listdir(stage_dir):
    m = re.search(r'player_id_[0-9]+.json', player_file)
    if m:
        with io.open(os.path.join(stage_dir,player_file), encoding='utf-8') as f:
            player = json.loads(f.read())
        history = player['history']
        try:
            columns = history[0].keys()
        except IndexError:  # No history for this player
            continue
        values =  [list(x.values()) for x in history]
        query = "INSERT INTO {}.stg_player_history ({}) VALUES %s".format(stg_schema, ','.join(columns))
        execute_values(cur, query, values)
        # Add future fixtures
        fixtures = player['fixtures']
        if len(fixtures) > 0:
            included_fixtures = [d['fixture'] for d in history]
            future_fixtures = []
            for f in fixtures:
                if f['id'] not in included_fixtures:  # Some fixtures might overlap
                    future_fixtures.append({
                              'element': history[0]['element'],
                              'fixture': f['id'],
                              'round': f['event'],
                              'opponent_team': f['team_a'] if f['is_home'] else f['team_h'],
                              'kickoff_time': f['kickoff_time'],
                              'was_home': f['is_home']})
            columns = future_fixtures[0].keys()
            values = [list(x.values()) for x in future_fixtures]
            query = "INSERT INTO {}.stg_player_history ({}) VALUES %s".format(stg_schema, ','.join(columns))
            execute_values(cur, query, values)

# Populate tables in the main schema
# First take a backup of existing table (just in case stage data is erroneous), then truncate, then fill
cur.execute(f"truncate table {backup_schema}.player_history")
cur.execute(f"insert into {backup_schema}.player_history select * from {main_schema}.player_history")
cur.execute(f"truncate table {main_schema}.player_history")
with io.open('sql/DML_player_history.sql', encoding='utf-8') as f:
    sql_query = f.read().replace('\n', ' ')
    sql_query = sql_query.replace('{stg_schema}', stg_schema)
    sql_query = sql_query.replace('{main_schema}', main_schema)
cur.execute(sql_query)

conn.commit()
conn.close()
