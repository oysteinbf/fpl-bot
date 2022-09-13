import os
import sys
import requests
import io
import json
import configparser

"""Import data from the FPL API to the staging area"""

config = configparser.ConfigParser()
config.read('../config/fpl-bot.ini')

stage_dir = config.get('FILES', 'STAGE_DIR')

def get_static_data(stage_dir):
    r=requests.get('https://fantasy.premierleague.com/api/bootstrap-static/').json()
    with io.open(os.path.join(stage_dir,'bootstrap_static.json'), 'w') as outfile:
        json.dump(r, outfile)

def get_fixtures(stage_dir):
    r=requests.get('https://fantasy.premierleague.com/api/fixtures/').json()
    with io.open(os.path.join(stage_dir,'fixtures.json'), 'w') as outfile:
        json.dump(r, outfile)

def get_individual_player_data(player_id, stage_dir):
    r = requests.get(f'https://fantasy.premierleague.com/api/element-summary/{player_id}/').json()
    with io.open(os.path.join(stage_dir,'player_id_{}.json'.format(player_id)), 'w') as outfile:
        json.dump(r, outfile)

def main():
    get_static_data(stage_dir)
    get_fixtures(stage_dir)
    with io.open(os.path.join(stage_dir,'bootstrap_static.json'), encoding='utf-8') as f:
        bootstrap_static = json.loads(f.read())
    n_players = len(bootstrap_static['elements'])
    for player_id in range(1, n_players):
        get_individual_player_data(player_id, stage_dir)

if __name__ == '__main__':
    sys.exit(main())

