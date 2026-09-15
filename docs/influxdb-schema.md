# InfluxDB schema

Measurement **`bee_traffic`**, one point per hive per `FLUSH_S` (default 60 s).

| | name | type | meaning |
|---|---|---|---|
| tag | `hive` | string | `hive2`, `hive3`, … — the `HIVE=` value from the env file |
| field | `bees_in` | int | line crossings in the `IN_DIRECTION` during the interval |
| field | `bees_out` | int | line crossings the other way |
| field | `bees_visible` | int | tracked bees in the last processed frame (an instantaneous sample, not a mean) |

Written with the InfluxDB 2.x client, org `beehive-org`, bucket `beehive` by default.

## Example Flux

Hourly traffic per hive, last 24 h:

```flux
from(bucket: "beehive")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "bee_traffic" and r.hive == "hive2")
  |> filter(fn: (r) => r._field == "bees_in" or r._field == "bees_out")
  |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
```

Daily totals and the peak hour (useful for an AI briefing prompt):

```flux
import "date"
from(bucket: "beehive")
  |> range(start: -1d)
  |> filter(fn: (r) => r._measurement == "bee_traffic" and r._field == "bees_in")
  |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
  |> group(columns: ["hive"])
  |> top(n: 1, columns: ["_value"])
```

Net flow (in − out) over a day should hover near zero for a healthy foraging
colony. A large sustained positive number on a hot afternoon is usually the line
sitting on the wrong side of a bearding cluster, not bees. A sudden large negative
excursion in the middle of a warm day is worth walking out to look at.

## Reading it from a dashboard

Any Flask/Grafana panel that already reads the `beehive` bucket can add these
queries as-is. This repo does not ship a dashboard patch; the Dusk Apiary
Observatory's own briefing dashboard reads the same bucket.
