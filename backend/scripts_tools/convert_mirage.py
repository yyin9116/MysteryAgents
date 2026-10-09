#!/usr/bin/env python3
"""Convert MIRAGE benchmark scripts into the platform ScriptPack format.

Handles three source irregularities:
1. 人物剧本.json may be flat ({角色: {fields}}) or act-nested ({幕: {角色: {fields}}});
   in act-nested scripts act2 may rename characters (真名（妖名）) — matched via parenthetical.
2. 线索.json groups may be lists of strings, or nested dicts / single-char lists
   (character-by-character reveal) — joined into one clue each.
3. 《大明星最后的演出》 is a 2-actor audition env without a murderer — skipped.

Usage:
    .venv/bin/python scripts_tools/convert_mirage.py /tmp/MIRAGE-main/dataset/Zh backend/scripts
"""
import json
import re
import sys
from pathlib import Path

CHAR_FIELDS = ("Story", "Script", "Relationship", "Performance", "Purpose", "Ability")

# script_id -> (dir name, culprit[act1-style name], tags)
SCRIPTS = {
    "mirage_bride_in_mourning":   ("孝衣新娘",         "方医生",        ["MIRAGE", "本格", "多角色", "硬核"]),
    "mirage_eastern_star":        ("东方之星号游轮事件", "修经理",        ["MIRAGE", "本格", "短篇", "新手友好"]),
    "mirage_museum_night":        ("博物馆奇妙夜",      "撒干事",        ["MIRAGE", "变格", "中篇"]),
    "mirage_raging_sea":          ("怒海余生",          "约翰",          ["MIRAGE", "本格", "多幕"]),
    "mirage_lichuan_tales":       ("漓川怪谈簿",        "衣衫褴褛的老人", ["MIRAGE", "变格", "中篇"]),
    "mirage_fox_hotel":           ("狐狸旅馆",          "滑头鬼",        ["MIRAGE", "变格", "多幕", "中篇"]),
    "mirage_school_rules_22":     ("第二十二条校规",     "皇甫青",        ["MIRAGE", "变格", "多幕", "硬核"]),
}


def first_sentence(text: str, limit: int = 90) -> str:
    text = re.sub(r"\s+", "", text or "")
    for sep in ["。", "！", "？", "；"]:
        idx = text.find(sep)
        if 0 < idx < limit:
            return text[: idx + 1]
    return text[:limit]


def _name_tokens(name: str) -> set:
    """Extract comparable name tokens: full name + parenthetical alias.
    e.g. '桐生一郎（滑头鬼）' -> {'桐生一郎', '滑头鬼'}"""
    tokens = {name}
    m = re.match(r"^(.+?)（(.+)）$", name)
    if m:
        tokens |= {m.group(1), m.group(2)}
    return tokens


def load_characters(raw_chars: dict):
    """Return {canonical_name: merged_fields_dict} from flat or act-nested source."""
    def is_char_body(v):
        return isinstance(v, dict) and "Story" in v and "Script" in v

    if any(is_char_body(v) for v in raw_chars.values()):
        acts = [raw_chars]  # flat
    else:
        acts = [v for k, v in raw_chars.items() if isinstance(v, dict)]
    acts = [a for a in acts if a]

    name_map = {}   # later-act name -> earlier-act name (via parenthetical)
    merged = {}

    def ensure(name):
        return merged.setdefault(name, {k: [] if k in ("Story", "Script", "Purpose") else "" for k in CHAR_FIELDS})

    for act in acts:
        act_keys = list(act.keys())
        # build mapping for renamed characters in this act
        rename = {}
        for key in act_keys:
            m = re.match(r"^(.+?)（(.+)）$", key)
            if m and m.group(2) in merged:
                rename[key] = m.group(2)
        for key, body in act.items():
            if not is_char_body(body):
                continue
            base = rename.get(key, key)
            slot = ensure(base)
            canonical = key if rename.get(key) else key
            slot["_canonical"] = canonical if rename.get(key) else slot.get("_canonical", base)
            for k in ("Story", "Script", "Purpose"):
                if str(body.get(k) or "").strip():
                    slot[k].append(str(body[k]).strip())
            for k in ("Relationship", "Performance", "Ability"):
                v = str(body.get(k) or "").strip()
                if v and "均有提及" not in v and len(v) > 2:
                    slot[k] = (slot[k] + "\n" + v).strip()

    for slot in merged.values():
        slot["Story"] = "\n\n——下一幕——\n\n".join(slot["Story"])
        slot["Script"] = "\n\n——下一幕——\n\n".join(slot["Script"])
        slot["Purpose"] = "\n\n".join(slot["Purpose"])
    return merged


def clue_entries(raw_clues: dict):
    """Yield (group_name, content) for every clue, normalizing nested structures."""
    for act_name, groups in raw_clues.items():
        pairs = groups.items() if isinstance(groups, dict) else [(act_name, groups)]
        for group_name, entries in pairs:
            if isinstance(entries, dict):
                # nested dict: {线索名: [char, char, ...]} — character-by-character reveal
                for sub_name, chars in entries.items():
                    if all(isinstance(c, str) and len(c) <= 1 for c in chars):
                        content = "".join(chars)
                    else:
                        content = "\n".join(str(c).strip() for c in chars if str(c).strip())
                    if content.strip():
                        yield f"{group_name}·{sub_name}", content
            else:
                if all(isinstance(c, str) and len(c) <= 1 for c in entries):
                    # single-char list at group level (e.g. 小暖): join into one clue
                    content = "".join(entries)
                    if content.strip():
                        yield str(group_name), content
                else:
                    for j, entry in enumerate(entries):
                        parts = entry if isinstance(entry, list) else [entry]
                        content = "\n（续）".join(str(p).strip() for p in parts if str(p).strip())
                        if content:
                            suffix = f"（第{j + 1}条）" if len(entries) > 1 else ""
                            yield f"{group_name}{suffix}", content


def convert(script_id: str, src_dir: Path, culprit: str | None, tags: list) -> dict:
    raw_chars = json.loads((src_dir / "人物剧本.json").read_text(encoding="utf-8"))
    raw_clues = json.loads((src_dir / "线索.json").read_text(encoding="utf-8"))
    title = next(v[0] for k, v in SCRIPTS.items() if k == script_id)

    merged = load_characters(raw_chars)
    opening_show = str(raw_chars.get("show") or "").strip()

    # canonical name lookup for culprit (act1-style name may be renamed later)
    canonical_of = {k: v.get("_canonical", k) for k, v in merged.items()}
    murderer_canonical = None
    if culprit:
        murderer_canonical = canonical_of.get(culprit) or culprit

    characters = []
    for i, (name, slot) in enumerate(merged.items()):
        display_name = slot.get("_canonical") or name
        characters.append({
            "char_id": f"mg_{script_id[7:]}_{i:02d}",
            "name": display_name,
            "public_profile": first_sentence(slot["Story"]) or display_name,
            "script": slot["Script"],
            "mission": slot["Purpose"] or "找出真凶，为自己洗清嫌疑。",
            "camp": "murderer" if display_name == murderer_canonical else "civilian",
            "secret_knowledge": ([slot["Relationship"]] if slot["Relationship"] else []),
        })

    clues = []
    for idx, (group_name, content) in enumerate(clue_entries(raw_clues), start=1):
        # pool semantics: comma-separated char_id list; omit -> public pool.
        # A clue group whose name mentions a character (their room / memory) becomes
        # that character's private pool so they can draw it during investigation.
        pool_ids = [
            c["char_id"] for c in characters
            if _name_tokens(c["name"]) & _name_tokens(group_name)
        ]
        clues.append({
            "clue_id": f"clue_{idx:03d}",
            "title": group_name,
            "content": content,
            "distribution": {"round": 1, "pool": ",".join(pool_ids) or None},
        })

    total_words = sum(len(c["script"]) for c in characters)
    agents = len(characters)

    stages = [
        {"stage_id": "reading", "type": "reading", "rounds": 1, "note": "阅读角色本并依次自我介绍"},
        {"stage_id": "clue_round_1", "type": "clue_round", "rounds": 1, "clues_per_player": 1, "note": "第一轮搜证（按线索组随机发放）"},
        {"stage_id": "discussion_1", "type": "discussion", "rounds": 2, "note": "自由讨论与质询"},
        {"stage_id": "clue_round_2", "type": "clue_round", "rounds": 1, "clues_per_player": 1, "note": "第二轮搜证"},
        {"stage_id": "discussion_2", "type": "discussion", "rounds": 2, "note": "最终讨论"},
        {"stage_id": "vote", "type": "vote", "rounds": 1, "note": "指认投票"},
    ]

    return {
        "script_id": script_id,
        "schema_version": 1,
        "meta": {
            "title": title,
            "player_count": agents,
            "difficulty": "hard" if total_words > 20000 else "standard",
            "estimated_minutes": max(40, min(150, total_words // 800 + agents * 5)),
            "tags": tags,
            "language": "zh",
            "source": "MIRAGE-benchmark",
        },
        "truth": {
            "murderer": next((c["char_id"] for c in characters if c["camp"] == "murderer"), None),
            "timeline": [],
            "case_replay": "",
        },
        "host_manual": {
            "intro": (opening_show[:600] or "本剧本源自 MIRAGE 社会推理基准。"),
            "stages": stages,
        },
        "characters": characters,
        "clues": clues,
    }


def main() -> None:
    src_root = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    from models.jubensha import validate_script_pack

    for script_id, (dirname, culprit, tags) in SCRIPTS.items():
        pack = convert(script_id, src_root / dirname, culprit, tags)
        result = validate_script_pack(pack)
        out = out_dir / f"{script_id}.json"
        out.write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
        size_kb = out.stat().st_size / 1024
        status = "OK" if result["ok"] else "FAIL"
        print(f"{status} {script_id} ({dirname}) chars={len(pack['characters'])} clues={len(pack['clues'])} "
              f"murderer={pack['truth']['murderer']} {size_kb:.0f}KB errors={result['errors'][:2]}")


if __name__ == "__main__":
    main()
