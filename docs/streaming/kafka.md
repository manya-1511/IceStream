# IceStream — Kafka Infrastructure & Producer (Day 3)

## 1. What already existed vs. what Day 3 added

The Kafka **broker** itself (KRaft mode, no ZooKeeper, persistent volume,
healthcheck, `icestream-network` networking, host access on
`localhost:29092`) was already built on Day 1 — see
`docs/architecture/system-architecture.md`. Day 3 did not touch the
`kafka` service definition in `docker-compose.yml` at all.

What Day 3 changed/added:

1. **Topic list** (`scripts/create-topics.sh`) — replaced the Day 1
   placeholder names `orders.raw` / `orders.dlq` (written before the
   event schema existed) with the now-canonical `checkout-events` /
   `checkout-events.dlq`. The other Day 1 placeholder topics
   (`orders.valid`, `orders.invalid`, `schema.events`, `quality.events`,
   `incidents`) are untouched — reserved for future Flink/quality stages.
2. **Kafka utility scripts** (`scripts/kafka/`) — list/describe topics,
   console-consume, publish a test message, check consumer lag.
3. **The Python producer** (`streaming/producer/`) — reads the Day 2
   `etl.to_events` output and publishes it to `checkout-events`.

## 2. Topics

| Topic | Partitions | Replication | Purpose |
|---|---|---|---|
| `checkout-events` | 6 | 1 | Active — schema-valid checkout events |
| `checkout-events.dlq` | 3 | 1 | Active — events that failed schema validation |
| `orders.valid` / `orders.invalid` / `schema.events` / `quality.events` / `incidents` | 3 each | 1 | Reserved (Day 1 placeholders, untouched) |

Replication factor is 1 because this is a single-broker local dev setup;
a real multi-broker deployment would use 3.

## 3. Kafka utility scripts

All run from the host and shell out to `docker exec` against the running
`icestream-kafka` container — no need to `docker exec` in by hand.

```bash
bash scripts/kafka/list-topics.sh
bash scripts/kafka/describe-topic.sh checkout-events
bash scripts/kafka/consume-topic.sh checkout-events --from-beginning
bash scripts/kafka/consume-topic.sh checkout-events --from-beginning --max-messages 5
bash scripts/kafka/produce-test-message.sh checkout-events '{"hello":"world"}'
bash scripts/kafka/consumer-lag.sh                       # list consumer groups
bash scripts/kafka/consumer-lag.sh <group-name>           # describe one group's lag
```

Or via Make: `make kafka-topics`, `make kafka-consume TOPIC=checkout-events`.

## 4. The producer (`streaming/producer/`)

Reads the JSON Lines file `etl.to_events` produces (Day 2), validates
each record against the canonical `CheckoutEvent` schema, and publishes
it to Kafka — or routes it to the DLQ topic if validation fails. Every
event is real (or synthesized-for-tests, clearly labeled) data flowing
through unmodified; **no anomaly injection** happens here.

### Design choices

- **Library**: `kafka-python` (pure Python, no compiled C extension to
  install) rather than `confluent-kafka`, to keep setup friction — and
  the Windows troubleshooting surface — as small as possible.
- **Partitioning key**: `order_id`. All line items belonging to the same
  order land in the same partition, preserving per-order ordering for
  any future consumer that cares about it.
- **Two send modes**:
  - `fixed-rate` (default): constant `--events-per-second`.
  - `replay`: preserves the *relative* gaps between the source events'
    real timestamps, compressed by `--replay-speed` (e.g. `60` means an
    hour of real purchase activity plays out in a minute). Useful for
    demoing realistic bursty traffic instead of a perfectly even stream.
- **`--dry-run`**: skips connecting to Kafka entirely and just logs what
  would have been sent — this is how the producer was verified in this
  environment (no Docker/Kafka available here — see §6).
- **DLQ routing**: any record that fails `CheckoutEvent` validation is
  wrapped as `{"error": "...", "raw_record": {...}}` and sent to
  `checkout-events.dlq` instead of aborting the run.

### Install

```bash
pip install -r streaming/producer/requirements.txt --break-system-packages
```

### Usage

```bash
# Dry run against the Day 2 sample data — no Kafka needed:
python -m streaming.producer.cli --dry-run \
  --input data/samples/checkout_events_sample.jsonl \
  --events-per-second 1000

# Publish the full processed dataset (after: python -m etl.preprocess && python -m etl.to_events)
python -m streaming.producer.cli --events-per-second 10

# Replay preserving real relative timing, sped up 60x:
python -m streaming.producer.cli --mode replay --replay-speed 60

# Publish only the first 5 records, looping forever:
python -m streaming.producer.cli --max-records 5 --loop
```

All flags:

| Flag | Default | Meaning |
|---|---|---|
| `--input` | `data/processed/events/checkout_events.jsonl` | Source JSON Lines file |
| `--bootstrap-servers` | `localhost:29092` | Kafka bootstrap servers (host listener) |
| `--topic` | `checkout-events` | Target topic for valid events |
| `--dlq-topic` | `checkout-events.dlq` | Target topic for invalid events |
| `--mode` | `fixed-rate` | `fixed-rate` or `replay` |
| `--events-per-second` | `10.0` | Rate for `fixed-rate` mode |
| `--replay-speed` | `60.0` | Speed-up factor for `replay` mode |
| `--max-records` | all | Only publish the first N records |
| `--loop` | off | Loop the input file indefinitely |
| `--log-interval-seconds` | `5.0` | Throughput log cadence |
| `--dry-run` | off | Don't connect to Kafka; just log |

## 5. Full local test procedure (with Docker)

```bash
# 1. Start infrastructure
docker compose up -d kafka kafka-init

# 2. Confirm Kafka is healthy
docker compose ps kafka
# STATUS column should read "healthy" (or "Up (healthy)")

# 3. Confirm the topics exist
bash scripts/kafka/list-topics.sh
# Expected output includes:
#   checkout-events
#   checkout-events.dlq
#   incidents
#   orders.invalid
#   orders.valid
#   quality.events
#   ...plus Kafka's internal __consumer_offsets topic

bash scripts/kafka/describe-topic.sh checkout-events
# Expected: Topic: checkout-events  PartitionCount: 6  ReplicationFactor: 1 ...

# 4. Prepare real event data (Day 2 pipeline; only needed once, or re-run
#    after downloading the real dataset — see docs/data/dataset.md)
python -m etl.preprocess
python -m etl.to_events

# 5. In one terminal, start consuming (leave this running):
bash scripts/kafka/consume-topic.sh checkout-events --from-beginning

# 6. In another terminal, publish:
python -m streaming.producer.cli --events-per-second 5 --max-records 17

# Expected producer log output (timings/counts will vary slightly):
#   INFO Connecting to Kafka at localhost:29092
#   INFO Loaded 17 record(s) from data/processed/events/checkout_events.jsonl | mode=fixed-rate | topic=checkout-events | dlq_topic=checkout-events.dlq
#   INFO Throughput: 5.00 events/sec | sent=17 dlq=0 parse_errors=0
#   INFO Run complete: sent=17 dlq=0 parse_errors=0 | elapsed=3.4s | avg=5.00 events/sec

# Expected consumer terminal output: 17 lines, each "order_id | {full JSON}",
# e.g.:
#   ord_0001 | {"transaction_id":"65c814f9-...","order_id":"ord_0001",...}
```

### Verifying the JSON matches the canonical schema

```bash
bash scripts/kafka/consume-topic.sh checkout-events --from-beginning --max-messages 1 \
  | cut -d'|' -f2- | python -c "
import sys, json
from etl.schemas import CheckoutEvent
raw = sys.stdin.read().strip()
event = CheckoutEvent.model_validate(json.loads(raw))
print('Valid CheckoutEvent:', event.transaction_id)
"
```

This should print `Valid CheckoutEvent: <uuid>` with no validation errors.

### What was actually verified in this development environment

Docker is not available in the environment this was built in, so the
live Kafka start/consume steps above could not be executed here. What
**was** run and verified end-to-end:

```
$ python -m streaming.producer.cli --dry-run --input data/samples/checkout_events_sample.jsonl --events-per-second 1000
INFO Running in DRY-RUN mode -- no connection to Kafka will be made.
INFO Loaded 17 record(s) from data/samples/checkout_events_sample.jsonl | mode=fixed-rate | topic=checkout-events | dlq_topic=checkout-events.dlq
INFO Run complete: sent=17 dlq=0 parse_errors=0 | elapsed=0.02s | avg=940.16 events/sec
INFO Dry run complete -- 17 message(s) would have been sent.
```

Plus: replay-mode timing, `--max-records`, DLQ routing for a deliberately
malformed record, and the full `streaming/producer/tests/` suite
(19 tests — see §7). Run the §5 steps above on your machine to confirm
the live broker path; the dry-run path proves the producer's own logic
(loading, validation, rate limiting, DLQ routing, schema-matching output)
independent of Kafka being reachable.

## 6. Tests

```bash
pip install -r streaming/producer/requirements.txt --break-system-packages
python -m pytest streaming/producer/tests/ -v
```

19 tests, all passing, all using `DryRunEventSender` (no broker
required): event loading, fixed-rate/replay delay computation, DLQ
routing, `order_id`-based partitioning keys, published JSON validating
against `CheckoutEvent`, CLI argument parsing, and end-to-end dry runs.

## 7. Troubleshooting

### General

**"Is the broker running? Try: docker compose ps kafka"** (producer error)
— the broker isn't up yet or isn't reachable at the configured
`--bootstrap-servers`. Run `docker compose up -d kafka kafka-init` and
wait for `docker compose ps kafka` to show healthy before starting the
producer.

**Topics don't exist / `UnknownTopicOrPartitionError`** — the `kafka-init`
one-shot container may not have finished (it waits for Kafka to become
healthy, then creates topics and exits). Check
`docker compose logs kafka-init`; re-run it manually with
`docker compose up kafka-init` if needed.

**Producer connects but nothing arrives at the consumer** — double-check
you're using the same bootstrap-servers *style* consistently: the
producer (running on the host) should use `localhost:29092` (the `HOST`
listener); anything running *inside* the Docker network should use
`kafka:9092` (the `PLAINTEXT` listener). Mixing them up is the most
common cause of "it looks connected but I see nothing."

### Windows + Docker specific

1. **Use Docker Desktop with the WSL2 backend**, not the legacy
   Hyper-V-only backend — KRaft-mode Kafka and Flink are far more
   reliably behaved under WSL2. (Docker Desktop → Settings → General →
   "Use the WSL 2 based engine".)

2. **`.sh` scripts won't run in cmd.exe or plain PowerShell.** Run them
   from **Git Bash** (installed with Git for Windows) or inside **WSL2**
   (`wsl` then `bash scripts/kafka/list-topics.sh`). PowerShell can still
   run the underlying `docker exec ...` commands directly if you'd
   rather not use Bash at all — copy the command out of the `.sh` file.

3. **CRLF line endings break shell scripts** (`$'\r': command not found`,
   or `bad interpreter`). If you cloned with Git's autocrlf conversion on,
   either:
   ```bash
   git config core.autocrlf false   # before cloning, or:
   dos2unix scripts/kafka/*.sh scripts/*.sh   # after, one-time fix
   ```

4. **Port conflicts on 9092/29092/8081/9000/9001** — another local
   service (or a previous IceStream run that didn't shut down cleanly)
   may be holding the port. `docker compose down` first, then check
   `netstat -ano | findstr :29092` (PowerShell) to find a conflicting
   process, or change the host-side port mapping in `docker-compose.yml`.

5. **Kafka container restarts in a loop after changing broker config**
   (e.g. `KAFKA_ADVERTISED_LISTENERS`) — KRaft persists its cluster
   metadata (including the original config) in the `kafka-data` volume.
   Changing broker-identity-affecting config after the volume already
   has data causes a mismatch. Fix: `docker compose down -v` (or
   `make clean`) to wipe the volume and let Kafka re-bootstrap from
   scratch, then `docker compose up -d`.

6. **Slow startup / healthcheck timing out** — Docker Desktop on Windows
   defaults to fairly low CPU/memory limits. Increase them under
   Settings → Resources if `docker compose ps kafka` stays
   `starting`/`unhealthy` past ~60 seconds; Kafka + Flink + Postgres +
   Redis + MinIO together want at least 4GB RAM allocated to the Docker
   VM.

7. **`localhost:29092` unreachable from the Python producer even though
   Docker Desktop shows the port mapped** — WSL2 networking can
   sometimes lag behind container start. Confirm with
   `docker compose ps` that Kafka shows `healthy` first; if it's healthy
   but still unreachable, restart Docker Desktop (WSL2's networking
   layer occasionally needs a kick after a long-running session or a
   Windows sleep/resume cycle).

## 8. What Day 3 explicitly does not do

- No anomaly injection — the producer never corrupts, mutates, or
  synthesizes fake business data. The only "invalid" records it can ever
  route to the DLQ are ones already invalid in the source data (which,
  per the Day 2 pipeline's own validation, doesn't currently happen —
  the DLQ path is tested with a synthetic bad record in
  `streaming/producer/tests/`, clearly a test fixture, not production
  behavior).
- No Flink consumption of `checkout-events` yet (Day 4+).
- No consumer implementation yet — `streaming/consumer/` remains a
  placeholder for a future day.
