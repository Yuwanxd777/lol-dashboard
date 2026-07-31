/* 技能名人工別名表（DDragon 沒有、只出現在 wiki 改動文字裡的舊譯名／變身子技能名）
   來源：掃描 wiki_patches.js 全部「技能名｜」前綴，扣掉 SKILL_KEYS（含 trim 與「A／B」拆分）
   仍對不到的高頻名稱，由人工逐一判定（2026-07-31）。
   格式 英雄id: { 名稱: [按鍵, 併入的現行技能名(可省略)] }
     ‧ 只有按鍵     → 保留原名，後面補上（Q/W/E/R/被動）
     ‧ 有第二個元素 → 直接換成現行名，讓同一顆技能的改動併成一塊
       （2026-07-31 使用者回報：2013 希維爾 13.13 的 R 被拆成「狩獵」與「狩獵號令」兩塊）
   ⚠ 只收有把握的；拿不準的寧可不標，錯的按鍵比沒有按鍵更誤導。 */
window.SKILL_ALIAS = {
  // ── 同一顆技能的舊譯名 → 換成現行名（會併塊）──
  Sivir: { "狩獵號令": ["R", "狩獵"] },                       // On the Hunt
  Belveth: { "薰衣草之死": ["被動", "魂斷紫海"] },             // Death in Lavender
  Skarner: { "碎裂大地": ["Q", "翻天覆地"] },                  // Shattered Earth
  Nidalee: { "擲標槍": ["Q", "標槍投擲"], "美洲獅化身": ["R", "美洲獅之形"] },                    // Javelin Toss
  Gnar: { "迴力鏢投擲": ["Q", "迴力鏢投擲"] },                 // Boomerang Throw
  Shaco: { "傑克玩具盒": ["W", "盒中傑克"], "惡魔玩偶": ["W", "盒中傑克"] },

  // ── 變身／多形態英雄的子技能名 → 只標按鍵（各形態效果不同，不能併塊）──
  Nidalee2: {},
  Elise: { "垂降": ["E"], "蜘蛛型態": ["R"], "人類型態": ["R"], "爆裂蜘蛛": ["W", "爆裂毒蛛"] },
  TwistedFate: { "金牌": ["W", "選牌"], "藍牌": ["W", "選牌"], "紅牌": ["W", "選牌"] },  // 逆命 W＝選牌
  Leblanc: { "Mimic：Distortion": ["W", "移行瞬影"], "Mimic：Sigil of Malice": ["Q", "沉默封印"],
             "Mimic：Ethereal Chains": ["E", "幻影鎖鍊"], "模仿：虛無鎖鏈": ["E", "幻影鎖鍊"] },
  Rengar: { "Savagery 2": ["Q", "兇殘打擊"], "野蠻 2": ["Q", "兇殘打擊"], "野蠻": ["Q", "兇殘打擊"],
            "Battle Roar 2": ["W", "怒獅戰吼"] },
  RekSai: { "破土而出": ["W"], "地道": ["W"], "鑽地": ["W"], "潛地": ["W"], "鑽出": ["W", "破土而出"],
            "Unburrow": ["W", "破土而出"], "獵物搜尋": ["Q", "尋找獵物"], "Prey Seeker": ["Q", "尋找獵物"],
            "狂怒撕咬": ["E", "狂食"], "Furious Bite": ["E", "狂食"], "Tremor Sense": ["被動", "震波感應"] },
  Kled: { "膽小蜥蜴斯卡爾": ["被動"], "斯卡爾": ["被動"] },
  Jayce: { "電磁脈衝": ["Q"], "超頻導體": ["W"], "中子加速裝置": ["E"],
           "浩瀚無垠": ["Q"], "離子領域": ["W"], "風馳電掣": ["E"],
           "型態轉換：水星砲": ["R", "水星加農"], "變身：水星加農砲": ["R", "水星加農"],
           "Transform Mercury Hammer": ["R", "水星戰鎚"], "Transform Mercury Cannon": ["R", "水星加農"] },
  Khazix: { "進化巨爪": ["Q"], "進化尖刺": ["W"], "進化翅膀": ["E"], "進化活性迷彩": ["R"] },
  LeeSin: { "守護": ["W"], "鋼鐵意志": ["W"], "疾風": ["E"], "天音波": ["Q"], "迴音擊": ["Q"] },
  Heimerdinger: { "H-28Q 尖端炮臺": ["Q"], "H-28G 進化砲台": ["Q"], "H-28Q Apex Turret": ["Q", "H-28Q 尖端炮臺"] },
  TahmKench: { "反芻": ["W"] },
  Rell: { "鍛鐵術：上馬": ["W"], "鍛鐵術：下馬": ["W"], "Ferromancy：Mount Up": ["W", "馭鐵之術：上馬"] },
  Yunara: { "裁決之弧": ["W"], "毀滅弧光": ["W"] },
  Hwei: { "熔岩裂縫": ["Q"], "Devastating Fire": ["Q"], "Pool of Reflection": ["W"],
          "Grim Visage": ["E"], "猙獰面容": ["E"], "Severing Bolt": ["E"] },
  Briar: { "血之狂亂": ["W"] },
  Mordekaiser: { "悲傷收割者": ["W", "憂傷蔓延"], "Harvester of Sorrow": ["W", "憂傷蔓延"],
                 "Dragon Force": ["R", "屠龍之力"] },
  Pyke: { "深海降臨": ["R"], "深海處決": ["R"] },
  Rengar: { "骨牙項鍊": ["被動"] },
  Swain: { "惡魔閃焰": ["R"], "惡魔烈焰": ["R", "惡魔閃焰"], "Demonflare": ["R", "惡魔閃焰"] },
  AurelionSol: { "天穹墜落": ["R"] },
  // ── 2026-08-01 全面稽核批次（依 DDragon 該年代正名對回）──
  Quinn: { "Skystrike": ["R", "絕命殺戮"], "天襲": ["R", "絕命殺戮"] },
  Karma: { "Defiance": ["E", "蔑視"], "蔑視": ["E"], "Renewal": ["W", "復甦"], "復甦": ["W"],
           "Soulflare": ["Q", "靈魂閃焰"], "靈魂閃焰": ["Q"] },
  Rumble: { "Junkyard Titan 2": ["被動", "泰坦熱能"] },
  Elise2: {},
  Gnar: { "巨石投擲": ["Q", "巨岩拋擲"], "Boulder Toss": ["Q", "巨岩拋擲"], "迴力鏢投擲": ["Q", "骨頭迴力鏢"] },
  Viktor: { "放電": ["E"] },
  Corki: { "特別配送": ["W"], "Special Delivery": ["W", "特別配送"] },
  Jinx: { "大魚骨": ["Q"] },
  Riven: { "Wind Slash": ["R", "風斬"] },
  Sylas2: {},
  Camille: { "Wall Dive": ["E", "鋼鐵鉤射"] },
  Hwei2: {},
  Zeri: { "Basic Attack": ["", "普攻"] },
  // 亞菲利歐：五把武器屬於被動軍械體系、武器主動技視為 Q（DDragon 的 Q 就叫「武器技能」）
  Aphelios: { "Calibrum": ["被動", "通碧"], "Severum": ["被動", "斷魄"], "Gravitum": ["被動", "墜明"],
              "Infernum": ["被動", "熾焰"], "Crescendum": ["被動", "折鏡"], "熾焰": ["被動"],
              "Moonshot": ["Q", "月神箭"], "Onslaught": ["Q", "猛攻"], "Binding Eclipse": ["Q", "引力蝕縛"],
              "Binding 星蝕": ["Q", "引力蝕縛"], "Duskwave": ["Q", "暮光波動"], "Sentry": ["Q", "哨兵砲塔"] },
  // 特朗德 3.6 重做：wiki 混用英文原名與舊譯名（2026-08-01 使用者點名）
  Trundle: { "Rabid Bite": ["Q", "狂野撕咬"], "Contaminate": ["W", "極凍領地"],
             "Pillar of Filth": ["E", "狡詰冰柱"], "汙穢之柱": ["E", "狡詰冰柱"],
             "劇痛": ["R", "盛怒霸體"] },
};
