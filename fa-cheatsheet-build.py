#!/usr/bin/env python3
"""
从本地 metadata/ 生成 fa-cheatsheet-data.js（fa-cheatsheet.html 的数据源）。
升级 Font Awesome 版本后，用新包的 metadata 覆盖本包，再重新运行：
    python3 fa-cheatsheet-build.py
数据来自：metadata/icons.json（图标、unicode、别名、关键词）
          metadata/categories.yml（官方分类）
          metadata/shims.json（v4 旧类名 -> 新类名 对照）
"""
import json
import re
import datetime
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
META = ROOT / "metadata"

# 68 个官方分类的中文翻译（id -> 中文）
CAT_ZH = {
    "accessibility": "无障碍", "alert": "警告提醒", "alphabet": "字母",
    "animals": "动物", "arrows": "箭头方向", "astronomy": "天文",
    "automotive": "汽车", "buildings": "建筑", "business": "商务办公",
    "camping": "露营户外", "charity": "慈善捐助", "charts-diagrams": "图表图示",
    "childhood": "儿童亲子", "clothing-fashion": "服饰穿搭", "coding": "编程开发",
    "communication": "通讯交流", "connectivity": "网络连接", "construction": "工程施工",
    "design": "设计", "devices-hardware": "设备硬件", "disaster": "灾害预警",
    "editing": "编辑", "education": "教育学术", "emoji": "表情符号",
    "energy": "能源", "files": "文件", "film-video": "影视视频",
    "food-beverage": "美食饮品", "fruits-vegetables": "果蔬", "gaming": "游戏",
    "gender": "性别", "halloween": "万圣节", "hands": "手势",
    "holidays": "节日", "household": "家居生活", "humanitarian": "人道救援",
    "logistics": "物流仓储", "maps": "地图定位", "maritime": "航海船舶",
    "marketing": "市场营销", "mathematics": "数学", "media-playback": "媒体播放",
    "medical-health": "医疗健康", "money": "金融财务", "moving": "搬迁移动",
    "music-audio": "音乐声音", "nature": "自然", "numbers": "数字",
    "photos-images": "照片图像", "political": "政治", "punctuation-symbols": "标点符号",
    "religion": "宗教信仰", "science": "科学", "science-fiction": "科幻",
    "security": "安全", "shapes": "形状", "shopping": "购物",
    "social": "社交", "spinners": "加载指示", "sports-fitness": "体育健身",
    "text-formatting": "文字排版", "time": "时间日期", "toggle": "开关切换",
    "transportation": "交通出行", "travel-hotel": "旅行酒店", "users-people": "人物",
    "weather": "天气", "writing": "书写",
}


def parse_categories():
    """解析 categories.yml：顶层 key 分类，里面含 label 与 icons 列表。"""
    text = (META / "categories.yml").read_text(encoding="utf-8")
    cats, cur, mode = [], None, None
    for line in text.splitlines():
        m = re.match(r"^([a-z0-9-]+):\s*$", line)
        if m:
            cur = {"id": m.group(1), "label": None, "icons": []}
            cats.append(cur)
            mode = None
            continue
        if cur is None:
            continue
        m = re.match(r"^  label:\s*(.+?)\s*$", line)
        if m:
            cur["label"] = m.group(1)
            continue
        m = re.match(r"^  icons:\s*$", line)
        if m:
            mode = "icons"
            continue
        if mode == "icons":
            m = re.match(r"^\s+-\s*(\S+)\s*$", line)
            if m:
                cur["icons"].append(m.group(1))
                continue
            if re.match(r"^  \S", line):
                mode = None
    return cats


def main():
    version_match = re.search(
        r"Font Awesome Free (\d+\.\d+\.\d+)",
        (ROOT / "css" / "all.css").read_text(encoding="utf-8")[:300],
    )
    version = version_match.group(1) if version_match else "unknown"

    icons_src = json.loads((META / "icons.json").read_text(encoding="utf-8"))
    cats = parse_categories()
    shims = json.loads((META / "shims.json").read_text(encoding="utf-8"))

    cat_of_icon = defaultdict(list)
    for c in cats:
        for name in c["icons"]:
            cat_of_icon[name].append(c["id"])

    out_icons = []
    for name, info in icons_src.items():
        styles = [s for s in info.get("styles", []) if s in ("solid", "regular", "brands")]
        if not styles:
            continue
        cats_for_icon = cat_of_icon.get(name, [])
        # 仅品牌字体且官方未归类 -> 归入合成分类 brands
        if styles == ["brands"] and not cats_for_icon:
            cats_for_icon = ["brands"]
        aliases = info.get("aliases", {})
        alias_names = aliases.get("names", [])
        alias_unicodes = []
        uni = aliases.get("unicodes", {})
        for key in ("primary", "composite"):
            for u in uni.get(key, []):
                if u not in alias_unicodes:
                    alias_unicodes.append(u)
        out_icons.append({
            "n": name,
            "u": info.get("unicode", ""),
            "l": info.get("label") or name,
            "s": styles,
            "c": cats_for_icon,
            "k": (info.get("search", {}).get("terms") or [])[:14],
            "a": alias_names,
            "au": alias_unicodes,
        })

    # v4 旧类名对照：[旧名, 风格(null=fa/solid), 新名]
    v4 = {old: {"s": style or "", "n": new} for old, style, new in shims}

    # 组装分类（yml 顺序 + brands + uncategorized），统计数量
    cat_ids_used = {cid for o in out_icons for cid in o["c"]}
    out_cats = []
    for c in cats:
        if c["id"] in cat_ids_used or True:
            out_cats.append({
                "id": c["id"],
                "label": c["label"] or c["id"],
                "zh": CAT_ZH.get(c["id"], c["label"] or c["id"]),
            })
    out_cats.append({"id": "brands", "label": "Brands", "zh": "品牌Logo"})
    out_cats.append({"id": "uncategorized", "label": "Uncategorized", "zh": "未分类"})
    count_by_cat = defaultdict(int)
    for o in out_icons:
        for cid in o["c"]:
            count_by_cat[cid] += 1
    for c in out_cats:
        c["count"] = count_by_cat.get(c["id"], 0)
    out_cats = [c for c in out_cats if c["count"] > 0 or c["id"] not in ("brands", "uncategorized")]

    data = {
        "v": version,
        "gen": datetime.date.today().isoformat(),
        "cats": out_cats,
        "icons": out_icons,
        "v4": v4,
    }

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    target = ROOT / "fa-cheatsheet-data.js"
    target.write_text(
        "/* 本文件由 fa-cheatsheet-build.py 自动生成，请勿手改；"
        "升级 Font Awesome 后重新运行脚本即可。 */\n"
        "window.FA_DATA = " + payload + ";\n",
        encoding="utf-8",
    )

    style_count = defaultdict(int)
    for o in out_icons:
        for s in o["s"]:
            style_count[s] += 1
    print(f"Font Awesome {version}")
    print(f"图标 {len(out_icons)} 个：" + ", ".join(f"{k} {v}" for k, v in sorted(style_count.items())))
    print(f"分类 {len(out_cats)} 个，v4 对照 {len(v4)} 条")
    print(f"已生成 {target}（{target.stat().st_size // 1024} KB）")


if __name__ == "__main__":
    main()
