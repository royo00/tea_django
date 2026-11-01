"""把 IANA 时区数据导入 MySQL 的 mysql.time_zone* 系统表。

为什么需要这个脚本
------------------
MySQL 的 CONVERT_TZ()、以及 Django 在 USE_TZ=True 时对 DateTimeField 做的
Trunc/Extract（例如 admin 的 date_hierarchy、`__date`/`__year` 查询），都依赖
mysql.time_zone* 四张表里的时区数据。Windows 版 MySQL 不预装这些数据，
mysql_tzinfo_to_sql.exe 在 Windows 上又跑不通（会把每个时区文件都报成
"not regular file"），于是 CONVERT_TZ 一律返回 NULL，Django 便抛出：

    Database returned an invalid datetime value.
    Are time zone definitions for your database installed?

本脚本直接解析 Python tzdata 包（venv 里已有）自带的 TZif 二进制，生成并写入
mysql.time_zone / time_zone_name / time_zone_transition /
time_zone_transition_type 四张表，等价于 Linux 上的：

    mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root mysql

比 mysql_tzinfo_to_sql 多做了一步：tzdata 发布的是 slim 格式，显式 transition
只写到 2007 年左右，之后的规则放在文件尾部的 POSIX TZ 字符串里
（如 "EST5EDT,M3.2.0,M11.1.0"）。脚本会解析该字符串并把未来的夏令时切换
展开成真实 transition（默认到 2037 年，与 glibc 的 fat 格式一致），
否则 2008 年以后的时间换算会全部错乱。

用法（在项目根目录）：
    .venv/Scripts/python.exe scripts/import_mysql_timezones.py
    .venv/Scripts/python.exe scripts/import_mysql_timezones.py --only Asia/Shanghai UTC

注意：需要 root 权限；会先清空这四张表再重新写入，可重复执行。
"""

from __future__ import annotations

import argparse
import calendar
import os
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import django

# 允许直接以脚本方式运行：把项目根目录放进 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# 第一个 transition 之前生效的类型，用一个更早的 transition 表达，
# 让 MySQL 处理很早的时间也有正确偏移。
PREHISTORIC_TIME = -2208988800  # 1900-01-01 00:00:00 UTC
DEFAULT_UNTIL_YEAR = 2037  # 与 glibc fat 格式的 transition 覆盖范围对齐
# MySQL 的时区代码用 32 位时间戳处理 transition：只要某个时区存在超过
# 2038-01-19 03:14:07 UTC 的 transition，整个时区都会加载失败，
# CONVERT_TZ 直接返回 NULL（实测 Asia/Gaza、Asia/Hebron 就是这样）。
MAX_TRANSITION_TIME = 2147483647


# ---------------------------------------------------------------------------
# TZif 解析
# ---------------------------------------------------------------------------
def tzif_dir() -> Path:
    """定位 tzdata 包自带的 zoneinfo 目录。"""
    try:
        import tzdata  # type: ignore

        candidate = Path(tzdata.__file__).parent / "zoneinfo"
        if candidate.is_dir():
            return candidate
    except ImportError:
        pass

    from zoneinfo import TZPATH

    for entry in TZPATH:
        path = Path(entry)
        if path.is_dir():
            return path
    raise SystemExit("找不到 IANA 时区数据，请先 `pip install tzdata`。")


def parse_tzif(raw: bytes) -> tuple[list[tuple[int, int]], list[tuple[int, int, str]], str]:
    """解析 TZif 文件。

    返回 (transitions, types, footer)：
        transitions: [(unix 时间戳, 类型下标), ...] 按时间升序
        types:       [(UTC 偏移秒数, 是否夏令时, 缩写), ...]
        footer:      v2+ 尾部的 POSIX TZ 字符串，可能为空
    """

    def read_header(offset: int) -> tuple[bytes, tuple[int, ...], int]:
        if raw[offset : offset + 4] != b"TZif":
            raise ValueError("不是 TZif 文件")
        version = raw[offset + 4 : offset + 5]
        counts = struct.unpack(">6I", raw[offset + 20 : offset + 44])
        return version, counts, offset + 44

    def block_len(counts: tuple[int, ...], time_size: int) -> int:
        isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts
        return (
            timecnt * time_size
            + timecnt
            + typecnt * 6
            + charcnt
            + leapcnt * (time_size + 4)
            + isstdcnt
            + isutcnt
        )

    version, counts, offset = read_header(0)
    time_size = 4
    if version in (b"2", b"3", b"4"):
        # 跳过体积较小的 v1 数据块，改用 64 位时间戳的 v2+ 数据块
        offset += block_len(counts, 4)
        version, counts, offset = read_header(offset)
        time_size = 8

    isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts
    if typecnt == 0:
        raise ValueError("TZif 没有类型记录")

    fmt = ">%d%s" % (timecnt, "q" if time_size == 8 else "l")
    times = struct.unpack(fmt, raw[offset : offset + timecnt * time_size]) if timecnt else ()
    offset += timecnt * time_size

    indexes = raw[offset : offset + timecnt]
    offset += timecnt

    raw_types = []
    for _ in range(typecnt):
        utoff, isdst, abbr_index = struct.unpack(">ibB", raw[offset : offset + 6])
        offset += 6
        raw_types.append((utoff, isdst, abbr_index))

    chars = raw[offset : offset + charcnt]
    offset += charcnt
    # 跳过 leap second 与 std/wall、ut/local 指示表
    offset += leapcnt * (time_size + 4) + isstdcnt + isutcnt

    types: list[tuple[int, int, str]] = []
    for utoff, isdst, abbr_index in raw_types:
        end = chars.find(b"\0", abbr_index)
        if end == -1:
            end = len(chars)
        abbr = chars[abbr_index:end].decode("ascii", "replace")[:8]  # 列宽 char(8)
        types.append((utoff, isdst, abbr))

    footer = ""
    if version in (b"2", b"3", b"4"):
        footer = raw[offset:].strip(b"\n").decode("ascii", "replace").strip()

    # tzfile(5)：第一个 transition 之前生效的是「第一个非夏令时类型」
    initial_type = 0
    for i, (_, isdst, _) in enumerate(types):
        if not isdst:
            initial_type = i
            break

    transitions = list(zip(times, indexes))
    return transitions, types, footer


# ---------------------------------------------------------------------------
# 尾部 POSIX TZ 字符串展开（slim 格式必需）
# ---------------------------------------------------------------------------
def _parse_name(text: str, i: int) -> tuple[str, int]:
    if text[i] == "<":
        end = text.index(">", i)
        return text[i + 1 : end], end + 1
    end = i
    while end < len(text) and text[end].isalpha():
        end += 1
    return text[i:end], end


def _parse_hms(text: str, i: int) -> tuple[int, int]:
    """解析 [+|-]hh[:mm[:ss]]，返回 (秒数, 新下标)。"""
    sign = 1
    if i < len(text) and text[i] in "+-":
        if text[i] == "-":
            sign = -1
        i += 1
    end = i
    while end < len(text) and (text[end].isdigit() or text[end] == ":"):
        end += 1
    parts = [int(p) for p in text[i:end].split(":") if p != ""] or [0]
    seconds = parts[0] * 3600 + (parts[1] * 60 if len(parts) > 1 else 0) + (parts[2] if len(parts) > 2 else 0)
    return sign * seconds, end


def _parse_rule(text: str) -> tuple:
    """解析 M3.2.0/2、J60/2、59/2 这类切换规则。"""
    if "/" in text:
        rule, time_text = text.split("/", 1)
        seconds, _ = _parse_hms(time_text, 0)
    else:
        rule, seconds = text, 7200  # POSIX 默认 02:00
    if rule.startswith("M"):
        month, week, weekday = (int(x) for x in rule[1:].split("."))
        return ("M", month, week, weekday, seconds)
    if rule.startswith("J"):
        return ("J", int(rule[1:]), seconds)
    return ("D", int(rule), seconds)


def _rule_datetime(year: int, rule: tuple) -> datetime:
    """把切换规则换算成该年的本地日期时间（不含时间部分）。"""
    if rule[0] == "M":
        _, month, week, weekday, seconds = rule
        first = datetime(year, month, 1)
        # POSIX 里 0=周日；datetime.weekday() 里 0=周一
        first_posix_weekday = (first.weekday() + 1) % 7
        day = 1 + (weekday - first_posix_weekday) % 7 + (week - 1) * 7
        last_day = calendar.monthrange(year, month)[1]
        while day > last_day:
            day -= 7
        base = datetime(year, month, day)
    elif rule[0] == "J":
        _, day_of_year, _ = rule
        offset_days = day_of_year - 1
        if calendar.isleap(year) and day_of_year >= 60:
            offset_days += 1  # J 规则跳过 2 月 29 日
        base = datetime(year, 1, 1) + timedelta(days=offset_days)
    else:
        _, offset_days, _ = rule
        base = datetime(year, 1, 1) + timedelta(days=offset_days)
    return base + timedelta(seconds=rule[-1])


def _type_id(types: list[tuple[int, int, str]], offset: int, is_dst: int, abbr: str) -> int:
    """复用已有的等价类型，没有则追加。"""
    for index, (existing_offset, existing_dst, _) in enumerate(types):
        if existing_offset == offset and existing_dst == is_dst:
            return index
    types.append((offset, is_dst, abbr[:8]))
    return len(types) - 1


def expand_footer(
    footer: str,
    transitions: list[tuple[int, int]],
    types: list[tuple[int, int, str]],
    until_year: int = DEFAULT_UNTIL_YEAR,
) -> None:
    """把 POSIX TZ 字符串描述的切换规则展开成真实 transition（原地修改）。"""
    if not footer:
        return

    std_name, i = _parse_name(footer, 0)
    std_west, i = _parse_hms(footer, i)
    std_offset = -std_west  # POSIX 的正数表示西经，取反才是 UTC 偏移

    if i >= len(footer):
        # 无夏令时（如 "CST-8"），显式 transition 之后偏移不再变化，无需补
        return

    dst_name, i = _parse_name(footer, i)
    if i < len(footer) and footer[i] != ",":
        dst_west, i = _parse_hms(footer, i)
        dst_offset = -dst_west
    else:
        dst_offset = std_offset + 3600

    if i >= len(footer) or footer[i] != ",":
        return
    rule_text = footer[i + 1 :]
    if "," not in rule_text:
        return
    start_text, end_text = rule_text.split(",", 1)
    start_rule = _parse_rule(start_text)
    end_rule = _parse_rule(end_text)

    std_type = _type_id(types, std_offset, 0, std_name)
    dst_type = _type_id(types, dst_offset, 1, dst_name)

    last_explicit = transitions[-1][0] if transitions else None
    start_year = until_year - 1
    if last_explicit is not None:
        start_year = datetime.fromtimestamp(last_explicit, timezone.utc).year

    generated: list[tuple[int, int]] = []
    for year in range(start_year, until_year + 1):
        # 进入夏令时：切换时刻按切换前的标准时间解释
        dst_start = _rule_datetime(year, start_rule)
        dst_start_utc = calendar.timegm((dst_start - timedelta(seconds=std_offset)).timetuple())
        # 退出夏令时：切换时刻按切换前的夏令时间解释
        dst_end = _rule_datetime(year, end_rule)
        dst_end_utc = calendar.timegm((dst_end - timedelta(seconds=dst_offset)).timetuple())
        generated.append((dst_start_utc, dst_type))
        generated.append((dst_end_utc, std_type))

    generated.sort()
    if last_explicit is not None:
        generated = [row for row in generated if row[0] > last_explicit]
    transitions.extend(generated)


# ---------------------------------------------------------------------------
# 采集与写入
# ---------------------------------------------------------------------------
def collect_zones(root: Path, only: list[str] | None) -> dict[str, Path]:
    zones: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        # posix/ 与 right/ 是 tzdata 的镜像副本，导入后名字对不上，跳过
        if name.startswith(("posix/", "right/")):
            continue
        if only and name not in only:
            continue
        try:
            with path.open("rb") as fh:
                if fh.read(4) != b"TZif":
                    continue
        except OSError:
            continue
        zones[name] = path
    return zones


def build_rows(zones: dict[str, Path], until_year: int):
    zone_rows: list[tuple[int]] = []
    name_rows: list[tuple[str, int]] = []
    type_rows: list[tuple[int, int, int, int, str]] = []
    transition_rows: list[tuple[int, int, int]] = []

    for zone_id, (name, path) in enumerate(sorted(zones.items()), start=1):
        transitions, types, footer = parse_tzif(path.read_bytes())
        expand_footer(footer, transitions, types, until_year)

        # 第一个 transition 之前生效的类型，用一个更早的 transition 表达
        initial_type = 0
        for i, (_, is_dst, _) in enumerate(types):
            if not is_dst:
                initial_type = i
                break
        first_time = transitions[0][0] if transitions else PREHISTORIC_TIME
        transitions = [(min(PREHISTORIC_TIME, first_time - 1), initial_type)] + transitions

        zone_rows.append((zone_id,))
        name_rows.append((name, zone_id))
        for type_id, (offset, is_dst, abbr) in enumerate(types):
            type_rows.append((zone_id, type_id, offset, is_dst, abbr))

        seen: set[int] = set()
        for timestamp, type_id in sorted(transitions):
            if timestamp > MAX_TRANSITION_TIME:  # 超出 2038 会让整个时区失效
                continue
            if timestamp in seen:  # 主键是 (Time_zone_id, Transition_time)
                continue
            seen.add(timestamp)
            transition_rows.append((zone_id, timestamp, type_id))

    return zone_rows, name_rows, type_rows, transition_rows


def verify(connection, zones: list[str], until_year: int) -> None:
    """拿 MySQL 的 CONVERT_TZ 与 Python zoneinfo 逐点比对。"""
    from zoneinfo import ZoneInfo

    probes = [f"{year}-{month:02d}-15 12:00:00" for year in (2025, 2026, 2027, until_year - 1) for month in (1, 4, 7, 10)]
    mismatches = 0
    checked = 0
    with connection.cursor() as cursor:
        for name in zones:
            try:
                zone = ZoneInfo(name)
            except Exception:
                continue
            for probe in probes:
                cursor.execute("SELECT CONVERT_TZ(%s, 'UTC', %s)", [probe, name])
                got = cursor.fetchone()[0]
                if got is None:
                    mismatches += 1
                    print(f"  [NULL] {name} {probe}")
                    continue
                expected = (
                    datetime.strptime(probe, "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=ZoneInfo("UTC"))
                    .astimezone(zone)
                    .replace(tzinfo=None)
                )
                checked += 1
                if got != expected:
                    mismatches += 1
                    if mismatches <= 10:
                        print(f"  [差异] {name} {probe} -> MySQL {got} / 期望 {expected}")
    print(f"校验：{checked} 个采样点，差异 {mismatches} 处")


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 IANA 时区数据到 MySQL 系统表")
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="ZONE",
        help="只导入指定时区，例如 --only Asia/Shanghai UTC；不传则导入全部",
    )
    parser.add_argument("--until-year", type=int, default=DEFAULT_UNTIL_YEAR, help="夏令时规则展开到哪一年")
    parser.add_argument("--dry-run", action="store_true", help="只解析统计，不写数据库")
    args = parser.parse_args()

    django.setup()
    from django.db import connection

    root = tzif_dir()
    zones = collect_zones(root, args.only)
    if not zones:
        raise SystemExit("没有找到可导入的时区文件。")
    print(f"时区数据目录：{root}")
    print(f"待导入时区：{len(zones)} 个")

    zone_rows, name_rows, type_rows, transition_rows = build_rows(zones, args.until_year)
    print(
        f"解析结果：时区 {len(zone_rows)} 条，类型 {len(type_rows)} 条，"
        f"transition {len(transition_rows)} 条"
    )
    if args.dry_run:
        return 0

    def chunks(rows, size=5000):
        for i in range(0, len(rows), size):
            yield rows[i : i + size]

    with connection.cursor() as cursor:
        # 四张表之间没有外键，清空顺序无所谓；保证脚本可重复执行
        for table in (
            "time_zone_transition",
            "time_zone_transition_type",
            "time_zone_name",
            "time_zone",
        ):
            cursor.execute(f"DELETE FROM mysql.{table}")

        cursor.executemany(
            "INSERT INTO mysql.time_zone (Time_zone_id, Use_leap_seconds) VALUES (%s, 'N')",
            zone_rows,
        )
        for batch in chunks(name_rows):
            cursor.executemany(
                "INSERT INTO mysql.time_zone_name (Name, Time_zone_id) VALUES (%s, %s)", batch
            )
        for batch in chunks(type_rows):
            cursor.executemany(
                "INSERT INTO mysql.time_zone_transition_type "
                "(Time_zone_id, Transition_type_id, `Offset`, Is_DST, Abbreviation) "
                "VALUES (%s, %s, %s, %s, %s)",
                batch,
            )
        for batch in chunks(transition_rows):
            cursor.executemany(
                "INSERT INTO mysql.time_zone_transition "
                "(Time_zone_id, Transition_time, Transition_type_id) VALUES (%s, %s, %s)",
                batch,
            )

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM mysql.time_zone_name")
        print(f"已写入时区名：{cursor.fetchone()[0]} 条")
        for zone, probe in (
            ("Asia/Shanghai", "2026-01-01 00:00:00"),
            ("America/New_York", "2026-01-01 12:00:00"),
            ("America/New_York", "2026-07-01 12:00:00"),
        ):
            cursor.execute("SELECT CONVERT_TZ(%s, 'UTC', %s)", [probe, zone])
            print(f"  CONVERT_TZ('{probe}' UTC -> {zone}) = {cursor.fetchone()[0]}")

    sample = sorted(zones)[:: max(1, len(zones) // 40)][:40]
    verify(connection, sample, args.until_year)

    print("完成。Django 侧 has_zoneinfo_database 将在下一个数据库连接变为 True。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
