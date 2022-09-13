Extract data from the FPL API, predict future points for each player and optimise transfers for your own team.

[Pulp](https://coin-or.github.io/pulp/) is used for the optimisation.


Usage
---

First create the Postgres tables as defined in `sql/DDL_create_tables.sql` and set up a venv with requirements.txt.

Then set up the config file and run the scripts in the following order:

1. Import the data from the API
 `python import_data.py`

2. Populate the postgres tables
 `python populate_tables.py`

3. Perform the prediction
 `python fpl_prediction.py`

4. Optimise team and suggest transfers
 `python fpl_optimise.py --team_id {{ team id }} --n_transfers 2 --n_round 3`

Example output:

```
(venv) fpl-bot $ python fpl_optimise.py teamid 5977880 n_transfers 2 n_round 3
Finding the optimal formation (without making transfers):
3 round(s) ahead with formation 1-4-4-2, the optimal team predicts 139.2 points
3 round(s) ahead with formation 1-4-3-3, the optimal team predicts 129.9 points
3 round(s) ahead with formation 1-4-5-1, the optimal team predicts 124.1 points
3 round(s) ahead with formation 1-3-5-2, the optimal team predicts 131.6 points
3 round(s) ahead with formation 1-3-4-3, the optimal team predicts 131.6 points
3 round(s) ahead with formation 1-5-4-1, the optimal team predicts 129.3 points
3 round(s) ahead with formation 1-5-3-2, the optimal team predicts 135.2 points
3 round(s) ahead with formation 1-5-2-3, the optimal team predicts 123.7 points
3 round(s) ahead with formation 1-4-4-2, the optimal team predicts 139.2 points (the highest score)

Optimal team (without making any transfers):
         web_name name_own_team position  now_cost  points_cumulative
        Henderson           NFO      GKP       4.7               11.8
            James           CHE      DEF       6.0                7.6
 Alexander-Arnold           LIV      DEF       7.5                9.8
           Walker           MCI      DEF       5.1               12.3
          Cancelo           MCI      DEF       7.1               10.1
       Martinelli           ARS      MID       6.5               12.6
            Salah           LIV      MID      13.0               13.9
        Luis Díaz           LIV      MID       8.2               11.5
          Andreas           FUL      MID       4.6                9.2
            Jesus           ARS      FWD       8.2               15.1
          Haaland           MCI      FWD      11.9               25.3

Bench:
    web_name name_own_team position  now_cost  points_cumulative
    Iversen           LEI      GKP       3.9                0.0
 N.Williams           NFO      DEF       4.1                5.3
    Colback           NFO      MID       4.4                0.0
  Greenwood           LEE      FWD       4.4                0.0

Team value (11 players): 82.8
Money in bank: 1.6

Suggested transfers (note: using only formation 1-4-4-2):
 Out:
   web_name name_own_team position  now_cost  points_cumulative
     Jesus           ARS      FWD       8.2               15.1
 Luis Díaz           LIV      MID       8.2               11.5

 In:
       web_name name_own_team position  now_cost  points_cumulative
       Firmino           LIV      FWD       8.1               22.9
 Saint-Maximin           NEW      MID       6.5               15.2

3 round(s) ahead with formation 1-4-4-2, the optimal team predicts 150.7 points with the following team:
         web_name name_own_team position  now_cost  points_cumulative
        Henderson           NFO      GKP       4.7               11.8
            James           CHE      DEF       6.0                7.6
 Alexander-Arnold           LIV      DEF       7.5                9.8
           Walker           MCI      DEF       5.1               12.3
          Cancelo           MCI      DEF       7.1               10.1
       Martinelli           ARS      MID       6.5               12.6
            Salah           LIV      MID      13.0               13.9
          Andreas           FUL      MID       4.6                9.2
    Saint-Maximin           NEW      MID       6.5               15.2
          Firmino           LIV      FWD       8.1               22.9
          Haaland           MCI      FWD      11.9               25.3
```

### Future work
Get more data/features from somewhere.
Improve the prediction algorithm (though it will nevertheless be hard to obtain decent predictions).


Overview of API endpoints
---
NB: Dette gjaldt for 2021/2022-sesongen, så kan være endringer i nyere sesonger.

### Spiller- og laginformasjon
20 lag, 10 kamper per runde, 38 runder.

https://fantasy.premierleague.com/api/bootstrap-static/
`events`: Div info om alle 38 runder, f.eks. antall chips spilt, hvem oftest er valgt til kaptein osv.
`game_settings`: Diverse settings (maks antall ligaer man kan være med i og slik)
`phases`: Informasjon om faser, f.eks. "Overall", "September" osv.
`teams`: Informasjon om lagene, f.eks. navn, styrke hjemme, styrke borte osv.
`elements`: Informasjon om alle spillerne (mer detaljer finnes i endepunktet element-summary).
  Inneholder navn, lag, pris, antall mål, transfer-info og slik. 
  Tallet for "id" er det som linker til endepunktet /api/element-summary/{id}
`element_stats`: Key-value pairs (16 stk), neppe nyttig
`element_types`: Nøkler for posisjonene med litt info (GKP, DEF, MID, FWD). Constraints kan hentes herfra.

https://fantasy.premierleague.com/api/element-summary/42/
Inneholder spillerinformasjon:
`fixtures`: Informasjon om gjenstående fixtures
`history`: Informasjon om hvordan spilleren har gjort det hver runde. Brukes i prediksjonen.
`history_past`: Historikk fra tidligere sesonger

https://fantasy.premierleague.com/api/fixtures/
All fixtures (380 total): code, event, finished, kickoff time, team h, team a etc.
Har lagd tabell for denne, men dropper feltet stats (som viser hvem som scorte, hvem som fikk gule kort osv.)


### Informasjon om FPL-deltakere

https://fantasy.premierleague.com/api/entry/{{ team id }}/

https://fantasy.premierleague.com/api/entry/{{ team id }}/history/

https://fantasy.premierleague.com/api/entry/{{ team id }}/event/2/picks/
Antall poeng, poeng på benk, transfers, verdi i banken osv. Inneholder også picks, med referanse
til element (hvilken spiller). Inneholder også kapteinsinformasjon.

https://fantasy.premierleague.com/api/entry/{{ team id }}/transfers/
Informasjon om bytter (og når de er gjort)

### Liga-informasjon
https://fantasy.premierleague.com/api/leagues-classic/{{ league id }}/standings/
https://fantasy.premierleague.com/api/leagues-h2h/{{ league id }}/standings/
Må nok være logget inn for å hente ut dette
