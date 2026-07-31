from __future__ import annotations

from datetime import date, timedelta
import math
from pathlib import Path

import numpy as np

from .common import Observation, append_observations


def seed_demo(path: str | Path, end: date = date(2026, 7, 24), days: int = 570) -> None:
    rng = np.random.default_rng(42)
    start = end - timedelta(days=days-1)
    rows: list[Observation] = []
    models = ["frontier-reasoning", "frontier-general", "large-open", "small-fast", "other"]
    shares0 = np.array([.07,.30,.20,.25,.18]); shares1 = np.array([.29,.26,.24,.12,.09])
    for i in range(days):
        d = start + timedelta(days=i); t=i/(days-1)
        weekly = 1 + .045*math.sin(2*math.pi*i/7)
        tokens = 0.55e12 * math.exp(math.log(8.8)*t) * weekly * rng.lognormal(0,.035)
        shares = shares0*(1-t)+shares1*t; shares /= shares.sum()
        for m,sh in zip(models,shares):
            rows.append(Observation(str(d),"demo","tokens_total",m,float(tokens*sh),"tokens",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        # Derived-equivalent metrics are included as source series to make the preview complete.
        h100 = 72_000 * math.exp(math.log(11.5)*t) * rng.lognormal(0,.03)
        rows.append(Observation(str(d),"demo","h100_equivalent_hours","all",h100,"H100-hour",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        price = 2.75 - .8*t + .12*math.sin(i/31) + rng.normal(0,.04)
        units = 260 + 1450*t + 80*math.sin(i/23) + rng.normal(0,25)
        rows.append(Observation(str(d),"demo","gpu_price_median","H100_SXM",price,"USD/GPU-hour",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        rows.append(Observation(str(d),"demo","gpu_units_available","H100_SXM",max(units,30),"GPUs",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        ttft = 1.05 + .28*t + .12*math.sin(i/17) + rng.normal(0,.035)
        speed = 115 + 135*t + rng.normal(0,5)
        rows.append(Observation(str(d),"demo","ttft","frontier_median",ttft,"seconds",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        rows.append(Observation(str(d),"demo","output_speed","frontier_median",speed,"tokens/second",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        cap = 650_000 * math.exp(math.log(5.2)*t)
        power = 1450 * math.exp(math.log(3.6)*t)
        rows.append(Observation(str(d),"demo","operational_h100_equivalents","global",cap,"H100-equivalents",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        rows.append(Observation(str(d),"demo","operational_ai_datacenter_power","global",power,"MW",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        if i % 75 == 0:
            train_flop = 1.8e25 * math.exp(math.log(45)*t) * rng.lognormal(0,.22)
            rows.append(Observation(str(d),"demo","training_compute",f"frontier-run-{i//75+1}",train_flop,"FLOP",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
        for region,base,growth,phase in [("DOM",17000,2600,0),("ERCO",47000,4300,1.5),("PACE",7200,900,2.2)]:
            temp = 15 + 12*math.sin(2*math.pi*(i-110)/365+phase) + rng.normal(0,2)
            weather = 70*max(temp-18,0)+48*max(10-temp,0)
            load = base + growth*t + weather + 220*math.sin(2*math.pi*i/7) + rng.normal(0,180)
            rows.append(Observation(str(d),"demo","grid_load",region,load,"MW",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
            rows.append(Observation(str(d),"demo","temperature",region,temp,"C",quality="synthetic_demo",is_estimate=True,collected_at_utc="2026-07-24T20:00:00Z",provenance="synthetic demo"))
    append_observations(path, rows)
