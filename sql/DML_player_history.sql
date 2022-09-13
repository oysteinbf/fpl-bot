WITH stage_data AS (
  SELECT
    sph.*,
    sps.web_name, sps.team,
    et.singular_name_short AS position,
    own_team.short_name AS name_own_team, own_team.strength AS strength_own_team,
    opp_team.short_name AS name_opponent_team, opp_team.strength AS strength_opponent_team,
    sf.finished,
    now() AS time_inserted
  FROM {stg_schema}.stg_player_history sph
    JOIN {stg_schema}.stg_player_static sps ON sph."element" = sps.id
    JOIN {stg_schema}.stg_teams own_team ON sps.team = own_team.id
    JOIN {stg_schema}.stg_teams opp_team ON sph.opponent_team = opp_team.id
    JOIN {stg_schema}.stg_element_types et ON et.id = sps.element_type
    JOIN {stg_schema}.stg_fixtures sf ON sph.fixture = sf.id
  ORDER BY sph."element", sph.round
)
INSERT INTO {main_schema}.player_history 
SELECT * FROM stage_data
