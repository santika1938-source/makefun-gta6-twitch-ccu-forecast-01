# makefun-gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/santika1938-source/makefun-gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/santika1938-source/makefun-gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

A release-day Twitch viewership forecaster. For each hour of the launch day it takes the empirical distribution of log-ratios ln(viewers_h / viewers_1) across the case's comparable past launches — aligned on each launch's own UTC release day — and reads off the 5/25/50/75/95% quantiles, scaled by the case's hour-1 print. Comparables whose launch had not begun by their hour 1 (a single global unlock later in the UTC day) are left out, since their ratios measure unlock timing rather than day shape; the rest are weighted by how closely their pre-release ramp matches the case's own, and the median and spread are calibrated on held-out launches. On the four practice launches it scores a mean pinball loss of 0.197 against the house persistence baseline's 0.387. Pure Python 3 standard library, deterministic, no network.

## Run it

```sh
MAKEFUN_INPUT_DIR=/input MAKEFUN_OUTPUT_DIR=/output python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=1c6jcmp6&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
