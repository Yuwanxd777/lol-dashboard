@echo off
rem LOL dashboard data update (local only; publish.bat pushes to GitHub)
cd /d "%~dp0"

set LOG=update_log.txt
echo ==== %date% %time% ==== > "%LOG%"

python scripts\fetch_promo.py >> "%LOG%" 2>&1
python scripts\fetch_data.py >> "%LOG%" 2>&1
python scripts\fetch_patches.py >> "%LOG%" 2>&1
python scripts\fetch_patches_en.py >> "%LOG%" 2>&1
rem 改版文本清理（售價行刪除/前綴翻中/AP AD/英名對照；冪等，重抓後保持乾淨）
python scripts\clean_patch_text.py >> "%LOG%" 2>&1
python scripts\fetch_skills.py >> "%LOG%" 2>&1
python scripts\fetch_items.py >> "%LOG%" 2>&1
python scripts\fetch_jungle.py >> "%LOG%" 2>&1
python scripts\fetch_release.py >> "%LOG%" 2>&1
rem Historical asset index (icons per year + zh/en names); cached, only current year is refetched
python scripts\fetch_assets.py >> "%LOG%" 2>&1
rem 物件(塔/龍/巴龍/野區…)歷年改動：抓 Wiki Patch history，已快取跳過
python scripts\fetch_wiki_objectives.py >> "%LOG%" 2>&1
rem obj stats (towers/monsters/minions HP AD etc from CommunityDragon bins, cached 20h)
python scripts\fetch_obj_stats.py >> "%LOG%" 2>&1
rem 舊天賦(Runes Reforged 前)中英名＋圖＋各年天賦樹：給 2014-2017 版本焦點與圖鑑符文分區
python scripts\fetch_masteries.py >> "%LOG%" 2>&1
rem 舊符文(Runes Reforged 前 紅黃藍紫，2014-2017)：DDragon rune.json tier3 官方圖與數值
python scripts\fetch_old_runes.py >> "%LOG%" 2>&1
rem 符文圖正解表(CDragon perks.json，含已移除符文如天界之身/掠食者)
python scripts\fetch_rune_icons.py >> "%LOG%" 2>&1
rem 一級賽區＝該年有世界賽席位(lol.fandom Worlds 頁，快取)
python scripts\fetch_worlds_tier1.py >> "%LOG%" 2>&1
rem 聯賽升降賽/資格賽補充表(讀 Leaguepedia 快取，不打 API)
python scripts\build_league_struct.py >> "%LOG%" 2>&1
rem 積分逐場：增量更新(dpm、免金鑰)，只補比現有更新的 Solo/Duo 戰績
python scripts\fetch_soloq_update.py >> "%LOG%" 2>&1
rem rank ladder auto-update: uses the locally saved key from the dashboard "add API" button; skips if expired
python scripts\fetch_soloq_auto.py >> "%LOG%" 2>&1
rem Text corpus lint: reports leftovers/broken sentences into the log (never blocks the update)
python scripts\lint_text.py --quiet >> "%LOG%" 2>&1

type "%LOG%"
