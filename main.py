"""gta6-twitch-ccu-forecast-01 entry: an empirical launch-curve forecaster.

Method
------
A big game launch's release day has a characteristic shape once it is scaled by
its own first hour: the pre-midnight ramp (New Zealand and Europe unlocking
while the US still sleeps), the quiet UTC morning, then the climb into the
European and American evening peak. The case hands us 38-42 past launches with
their full hourly curves, so for each hour h of the day we take the empirical
distribution of the log-ratio

    r_c(h) = ln(viewers_c(h) / viewers_c(1))

across the comparables c, aligned on each launch's own UTC release day, and
read off the five scored quantiles. The forecast for the case is its hour-1
print times exp of those quantiles.

One cleaning step matters before any of that: a comparable whose launch had
not actually begun by 00:00 UTC on its release day (a single global unlock
later in the day) sits at its pre-release baseline in hour 1, so its ratios
measure unlock timing rather than day shape and poison the upper tail for
everyone else. Such a comparable — hour 1 below 1% of its own day's peak —
is left out of the reference set, and the remaining log-ratios are winsorized
at +/- ln 30. (The threshold here is 2% of the day's peak.)

Two refinements, both calibrated on the practice launches and on
leave-one-out over the comparables themselves:

* Similarity weighting. A launch whose pre-checkpoint trajectory looks like
  the case's own is a better guide to the case's day than one whose ramp
  looked different, so each comparable is weighted by a Gaussian kernel on
  pre-release features of its curve: how high the two hours before the
  release day already ran relative to hour 1, and how far hour 1 itself
  stands above the category's pre-release baseline (a launch that has not
  unlocked yet by 00:00 UTC sits at its baseline and follows a wholly
  different shape from one already rolling through the world's midnights).
* Calibration. The median log-ratio and the spread of the other quantiles
  around it are scaled by constants fitted so the pinball loss on held-out
  launches is as low as it goes (the fitted median multiplier lands just
  above 1 and the fitted spread just below 1: the raw empirical quantiles
  are slightly too timid in the middle and too wide in the tails).

The program is deterministic: fixed constants, no randomness, no clock, no
network, standard library only. It reads every *.in file in the input
directory, in name order, and writes one <id>.out per case.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first (harmless locally).
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Calibration constants, fitted on held-out launches (see the module docstring).
# A feature bandwidth of None disables that feature in the similarity kernel.
PARAMS = {
    "shrink": 1.04,        # median log-ratio multiplier (fitted; ~persistence)
    "spread": 0.8,         # scale of the non-median quantiles around the median
    "bw_a": 0.25,          # kernel width: ln(hour -1 viewers / hour-1 viewers)
    "bw_b": 0.5,           # kernel width: ln(hour -2 viewers / hour-1 viewers)
    "bw_g": None,          # kernel width: ln(hour 1 / pre-release baseline)
    "weight_floor": 0.02,  # every usable comparable keeps at least this weight
    "min_day_hours": 18,   # a comparable needs this many of hours 2..24 present
    "min_h1_share": 0.02,  # hour 1 must reach this share of the day's peak:
                           # a launch still at baseline in hour 1 (its unlock
                           # is later in the UTC day) measures unlock timing,
                           # not day shape, and poisons every ratio
    "ratio_cap": 30.0,     # log-ratios are winsorized at +/- ln(ratio_cap)
    "smooth": 0.0,         # weight of the neighbouring hours' median-centred
                           # ratios in each hour's quantile pool (0 = off)
}

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_ts(text):
    return datetime.strptime(text, TS_FORMAT).replace(tzinfo=timezone.utc)


def round2(x):
    """x rounded to 2 decimals, half up (as the house baseline rounds)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def hour_curve(points, day_start):
    """Map hour index -> viewers for points with a `from` timestamp.

    Hour 1 is [day_start, day_start + 1h); hour 0 is the hour before it,
    hour -1 the one before that, and so on in both directions.
    """
    curve = {}
    for point in points:
        offset = (parse_ts(point["from"]) - day_start).total_seconds() / 3600.0
        key = int(round(offset)) + 1
        viewers = point.get("viewers")
        if viewers is not None:
            curve[key] = float(viewers)
    return curve


def curve_features(curve):
    """Pre-release shape features of an hourly curve (see hour_curve).

    a: ln(viewers in the hour before the day / hour-1 viewers)
    b: ln(viewers two hours before the day / hour-1 viewers)
    g: ln(hour-1 viewers / the median hourly viewers of the two days before)
    Each is None when the curve does not hold what it needs.
    """
    first = curve.get(1, 0)
    feats = {"a": None, "b": None, "g": None}
    if first <= 0:
        return feats
    if curve.get(0, 0) > 0:
        feats["a"] = math.log(curve[0] / first)
    if curve.get(-1, 0) > 0:
        feats["b"] = math.log(curve[-1] / first)
    baseline = sorted(
        curve[k] for k in range(-48, 0) if curve.get(k, 0) > 0
    )
    if len(baseline) >= 12:
        median = baseline[len(baseline) // 2]
        if median > 0:
            feats["g"] = math.log(first / median)
    return feats


def weighted_quantile(pairs, tau):
    """Weighted empirical quantile of (value, weight) pairs.

    Uses midpoint plotting positions: each point stands for the middle of its
    own weight slice of the distribution, with linear interpolation between
    points and clamping at the extremes.
    """
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    if total <= 0:
        return ordered[len(ordered) // 2][0]
    positions = []
    acc = 0.0
    for value, weight in ordered:
        positions.append((acc + 0.5 * weight) / total)
        acc += weight
    if tau <= positions[0]:
        return ordered[0][0]
    if tau >= positions[-1]:
        return ordered[-1][0]
    for i in range(1, len(ordered)):
        if positions[i] >= tau:
            p0, p1 = positions[i - 1], positions[i]
            v0, v1 = ordered[i - 1][0], ordered[i][0]
            if p1 == p0:
                return v1
            return v0 + (v1 - v0) * (tau - p0) / (p1 - p0)
    return ordered[-1][0]


def comparable_profile(comp):
    """(ratios, features) for one comparable, or None when its day is unusable.

    ratios maps hour 2..24 -> ln(viewers(hour) / viewers(1)); features is the
    comparable's own pre-release shape (see curve_features).
    """
    day_start = parse_ts(comp["day_start"])
    curve = hour_curve(comp["hourly"], day_start)
    first = curve.get(1, 0)
    if first <= 0:
        return None
    peak = max(curve.get(hour, 0) for hour in range(1, 25))
    if first < PARAMS["min_h1_share"] * peak:
        return None
    cap = math.log(PARAMS["ratio_cap"])
    ratios = {}
    for hour in range(2, 25):
        value = curve.get(hour, 0)
        if value > 0:
            ratios[hour] = max(-cap, min(cap, math.log(value / first)))
    if len(ratios) < PARAMS["min_day_hours"]:
        return None
    return ratios, curve_features(curve)


def similarity_weight(case_feats, comp_feats):
    """Gaussian kernel over the enabled features both curves carry."""
    dist2 = 0.0
    used = False
    for name in ("a", "b", "g"):
        width = PARAMS["bw_" + name]
        if width is None:
            continue
        case_v, comp_v = case_feats[name], comp_feats[name]
        if case_v is None or comp_v is None:
            continue
        dist2 += ((case_v - comp_v) / width) ** 2
        used = True
    if not used:
        return 1.0
    return max(math.exp(-0.5 * dist2), PARAMS["weight_floor"])


def persistence_row(p1, hour):
    return [p1 * math.exp(z * 0.15 * math.sqrt(hour - 1)) for z in Z]


def forecast_case(case):
    if case["levels"] != LEVELS:
        raise ValueError("unexpected levels")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError("no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))

    day_start = parse_ts(case["day_start"])
    case_feats = curve_features(hour_curve(case["history_hourly"], day_start))

    profiles = []
    for comp in case["comparables"]:
        profile = comparable_profile(comp)
        if profile is not None:
            ratios, comp_feats = profile
            profiles.append((ratios, similarity_weight(case_feats, comp_feats)))

    # Per-hour weighted medians first: the smoothing pool below centres each
    # neighbouring hour's ratios on its own median before borrowing them.
    medians = {}
    for hour in range(2, 25):
        pairs = [(ratios[hour], w) for ratios, w in profiles if hour in ratios]
        if pairs:
            medians[hour] = weighted_quantile(pairs, 0.5)

    rows = []
    for spec in case["forecast"]:
        hour = spec["hour"]
        pairs = [(ratios[hour], w) for ratios, w in profiles if hour in ratios]
        if not pairs:
            quantiles = persistence_row(p1, hour)
        else:
            median = medians[hour]
            if PARAMS["smooth"] > 0:
                pooled = list(pairs)
                for other in (hour - 1, hour + 1):
                    if other in medians:
                        shift = median - medians[other]
                        pooled += [
                            (ratios[other] + shift, w * PARAMS["smooth"])
                            for ratios, w in profiles
                            if other in ratios
                        ]
                pairs = pooled
            quantiles = []
            for tau in LEVELS:
                r = weighted_quantile(pairs, tau)
                adjusted = PARAMS["shrink"] * median + PARAMS["spread"] * (r - median)
                quantiles.append(p1 * math.exp(adjusted))
        # Enforce the output contract: positive, capped, non-decreasing.
        cleaned = []
        for q in quantiles:
            q = min(max(q, 0.01), 1_000_000_000.0)
            if cleaned and q < cleaned[-1]:
                q = cleaned[-1]
            cleaned.append(round2(q))
        rows.append({"hour": hour, "q": cleaned})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
