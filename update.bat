@echo off
rem LOL dashboard data update (local only; publish.bat pushes to GitHub)
cd /d "%~dp0"

set LOG=update_log.txt
echo ==== %date% %time% ==== > "%LOG%"

python scripts\fetch_promo.py >> "%LOG%" 2>&1
python scripts\fetch_data.py >> "%LOG%" 2>&1
python scripts\fetch_patches.py >> "%LOG%" 2>&1
python scripts\fetch_patches_en.py >> "%LOG%" 2>&1
rem patch-text cleanup (drop skin-sale lines / translate prefixes / AP AD / EN-name mapping; idempotent)
python scripts\clean_patch_text.py >> "%LOG%" 2>&1
python scripts\fetch_skills.py >> "%LOG%" 2>&1
python scripts\fetch_items.py >> "%LOG%" 2>&1
rem item no-store list (CDragon inStore=false = items DDragon still keeps but game removed; codex filters these out)
python scripts\fetch_item_nostore.py >> "%LOG%" 2>&1
python scripts\fetch_jungle.py >> "%LOG%" 2>&1
python scripts\fetch_release.py >> "%LOG%" 2>&1
rem Historical asset index (icons per year + zh/en names); cached, only current year is refetched
python scripts\fetch_assets.py >> "%LOG%" 2>&1
rem objectives (towers/dragons/baron/jungle) patch history from wiki; cached, skips if present
python scripts\fetch_wiki_objectives.py >> "%LOG%" 2>&1
rem obj stats (towers/monsters/minions HP AD etc from CommunityDragon bins, cached 20h)
python scripts\fetch_obj_stats.py >> "%LOG%" 2>&1
rem old masteries (pre Runes Reforged) zh/en names + icons + yearly trees for 2014-2017
python scripts\fetch_masteries.py >> "%LOG%" 2>&1
rem old runes (pre Runes Reforged red/yellow/blue/purple 2014-2017): DDragon rune.json tier3
python scripts\fetch_old_runes.py >> "%LOG%" 2>&1
rem rune icon truth table (CDragon perks.json, incl. removed runes)
python scripts\fetch_rune_icons.py >> "%LOG%" 2>&1
rem tier1 regions = leagues with Worlds seats that year (lol.fandom Worlds page, cached)
python scripts\fetch_worlds_tier1.py >> "%LOG%" 2>&1
rem league promotion/qualifier supplement table (reads Leaguepedia cache, no API calls)
python scripts\build_league_struct.py >> "%LOG%" 2>&1
rem OBGG pro-account list refresh (LPL/LCK primary; drops accounts inactive ~2 months; routing merge with dpm)
python scripts\fetch_obgg_accounts.py >> "%LOG%" 2>&1
rem dpm pro-account refresh: /v1/pros per player (LCS/LEC/CBLOL primary=replace, others=union); only match-data players; puuid included
python scripts\fetch_dpm_soloq_accounts.py --apply >> "%LOG%" 2>&1
rem resolve dpmPuuid for newly added accounts via dpm search (best-effort; needed for per-game)
python scripts\resolve_obgg_dpmpuuid.py >> "%LOG%" 2>&1
rem soloq per-game: incremental update (dpm, no key), only fetches games newer than existing
python scripts\fetch_soloq_update.py >> "%LOG%" 2>&1
rem soloq per-game: backfill brand-new players that have no file yet (dpm)
python scripts\fetch_soloq_year.py --missing >> "%LOG%" 2>&1
rem rank ladder auto-update: uses the locally saved key from the dashboard "add API" button; skips if expired
python scripts\fetch_soloq_auto.py >> "%LOG%" 2>&1
rem Text corpus lint: reports leftovers/broken sentences into the log (never blocks the update)
python scripts\lint_text.py --quiet >> "%LOG%" 2>&1

type "%LOG%"
