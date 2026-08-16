# -*- coding: utf-8 -*-
"""國旗下載：flagcdn 的 https://flagcdn.com/w40/{iso2}.png → img/flags/{IOC三碼}.png

用途：國家隊（ENC 電競國家盃那種）沒有隊徽，改用國旗（使用者定案 2026-08-16）。
**不能用 emoji 國旗**——Windows 的 Segoe UI Emoji 不含國旗，🇯🇵 會被畫成「JP」兩個字母方塊
（2026-08-16 實測），所以只能用圖檔。

檔名用 **IOC 三碼**（與 index.html 的 NAT_ABBR 一致），前端 `img/flags/{縮寫}.png` 直接取用；
沒有的檔案 onerror 會退回文字縮寫，不算錯誤。
已存在就跳過（國旗不會變；要重抓刪檔案再跑）。

用法：  python scripts\\fetch_flags.py
"""
import io
import os
import sys
import time
import urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "img", "flags")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

# IOC 三碼 → ISO 3166-1 alpha-2（只收 index.html 的 NAT_ABBR 會產出的那些）
IOC2ISO = {
    "CHN": "cn", "KOR": "kr", "JPN": "jp", "VIE": "vn", "TPE": "tw", "HKG": "hk",
    "MGL": "mn", "PHI": "ph", "THA": "th", "SGP": "sg", "MAS": "my", "INA": "id",
    "IND": "in", "AUS": "au", "NZL": "nz",
    "USA": "us", "CAN": "ca", "MEX": "mx", "GUA": "gt", "BRA": "br", "ARG": "ar",
    "CHI": "cl", "PER": "pe", "COL": "co",
    "FRA": "fr", "GER": "de", "ESP": "es", "POR": "pt", "ITA": "it", "GRE": "gr",
    "POL": "pl", "DEN": "dk", "SWE": "se", "NOR": "no", "FIN": "fi", "BEL": "be",
    "NED": "nl", "CZE": "cz", "SVK": "sk", "HUN": "hu", "AUT": "at", "SUI": "ch",
    "ROU": "ro", "BUL": "bg", "CRO": "hr", "SRB": "rs", "SLO": "si",
    "LTU": "lt", "LAT": "lv", "EST": "ee", "IRL": "ie", "ISL": "is",
    "GBR": "gb", "UKR": "ua", "RUS": "ru", "TUR": "tr",
    "KSA": "sa", "UAE": "ae", "QAT": "qa", "KUW": "kw", "ISR": "il",
    "ALG": "dz", "TUN": "tn", "MAR": "ma", "EGY": "eg", "RSA": "za",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    got = skip = fail = 0
    for ioc, iso in sorted(IOC2ISO.items()):
        dst = os.path.join(OUT, ioc + ".png")
        if os.path.exists(dst) and os.path.getsize(dst) > 60:
            skip += 1
            continue
        try:
            req = urllib.request.Request(f"https://flagcdn.com/w40/{iso}.png", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            # ⚠ 不要用「檔案大小」當有效性判準：橫條/純色國旗(法國、荷蘭…)壓縮後只有 100 多 bytes，
            #   第一版設 200 bytes 門檻直接誤殺 35 面旗。改成驗 PNG 檔頭。
            if data[1:4] != b"PNG":          # PNG 檔頭 PNG
                raise ValueError("不是 PNG")
            with open(dst, "wb") as f:
                f.write(data)
            got += 1
        except Exception as e:
            fail += 1
            print(f"  {ioc}({iso}) 失敗：{type(e).__name__} {str(e)[:60]}")
        time.sleep(0.15)
    print(f"國旗：新增 {got}、既有 {skip}、失敗 {fail} → {OUT}")


if __name__ == "__main__":
    main()
