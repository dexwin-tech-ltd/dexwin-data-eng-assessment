# Dexwin Data Engineer assessment

This repository is the overnight batch that loads **DexMart** marketplace orders into a small Postgres warehouse. Treat it as a production job you have just inherited.

Finance opened a ticket after last week's close:

- Ghana-week GMV does not match the source files.
- Re-running the job changes the numbers.
- Monday's export (new column names) "mostly loaded."
- A few paid orders appear as `0.00` revenue.

There is no published defect count. Prioritize restoring trustworthy warehouse numbers, then harden the job so a second run is safe.

## Scenario

Every night the job should:

1. Read the raw CSVs under `data/raw/`.
2. Transform them into customer / product dimensions and an order fact table.
3. Load Postgres (`warehouse`).
4. Rebuild the `daily_gmv` mart Finance uses.

**Reporting contract**

| Rule | Value |
| --- | --- |
| Reporting timezone | `Africa/Nairobi` (EAT, UTC+3) |
| Reporting currency | `GHS` |
| Grain of `fact_orders` | one row per `order_id` |
| Restatements | a later file wins |
| Invalid amounts (`""`, `N/A`) | must not become `0` revenue |
| `refunded` | keep the fact row; exclude from GMV |
| Unknown `product_id` | still load the order |
| Reloads | idempotent |

Naive timestamps in the exports are source-local Nairobi time. Offsets and `Z` must be honored.

Work through the stages below and keep `FINDINGS.md` current.

## The assessment

Work through these stages in order:

1. **Read before you run.** Skim `data/raw/`, `pipeline/`, and `sql/init.sql`. Create `FINDINGS.md` and record issues or material risks you can see from the code and files.
2. **Run and investigate.** Bring the stack up, run the pipeline, query Postgres, and run the tests. Add every runtime issue you observe. Distinguish observed behaviour from suspicions.
3. **Propose before you patch.** For each finding, record impact, priority, a proposed fix, and how you would verify it. You may defer lower-priority work.
4. **Fix the highest-priority defects.** Make focused changes. Re-run the pipeline and tests. Watch for regressions (especially a second load).

You may use AI in the final step of this session if the interviewer allows it. You own every finding and change. Keep the AI interaction visible, give it bounded context, review its output, and verify everything you accept.

We care more about how you reason and prioritise than about catching every last item. Call out anything you would do with more time.

> There is no fixed bug count given to you on purpose. Treat it like a real codebase.

### Suggested `FINDINGS.md` format

```markdown
## Finding: concise title

- Location:
- Status: observed | suspected | confirmed | fixed | deferred
- Evidence:
- Impact:
- Priority:
- Proposed solution:
- Verification:
- Implementation notes:
```

## Timebox (60–75 minutes)

| Clock | Stage |
| --- | --- |
| 0:00–0:10 | Open the repo, read this README, start Postgres, first pipeline run |
| 0:10–0:25 | Investigate files + SQL + failing tests; write findings |
| 0:25–0:50 | Fix the defects that corrupt grain, reloads, or Monday's file |
| 0:50–0:65 | Timezones, null amounts, FX, mart refresh order |
| 0:65–0:75 | Re-run tests, note remaining risk, walk through `FINDINGS.md` |

A strong session gets the warehouse reload-safe and Monday's rows dated correctly, with a clear list of what was deferred.

## Open this repo in Cursor

1. Clone the branch your interviewer gave you.
2. Install [Cursor](https://cursor.com) if needed.
3. **File → Open Folder** on the clone (or `cursor .` from the repo root).
4. Open the integrated terminal (`Ctrl+`` / `Cmd+``).
5. Follow **Running the stack** below. Do not start coding until the interviewer starts the clock.

GitHub Codespaces also works if you prefer a browser: create a codespace on the supplied branch, then use the same `make` targets.

## Running the stack

You need **Docker** (Docker Desktop or equivalent) and **Python 3.11+**.

```bash
cp .env.example .env
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
make setup
make wait-db
make pipeline
make test
```

Useful extras:

```bash
make doctor      # toolchain + database sanity
make sql         # psql inside the warehouse container
make status      # row counts, duplicate keys, fact dump, daily_gmv
make reset       # wipe the volume and staging files
make test-unit   # transform tests only (no Postgres)
```

Or without Make:

```bash
docker compose up -d
python -m pip install -r requirements.txt
python -m pipeline
python -m pytest -q
```

The first pipeline run is expected to **exit 0** and still be wrong. Run it a second time and note what happens. Several tests fail on purpose. Do not "fix" a test by weakening the assertion unless you can explain why the contract is wrong.

### What should come up

| Piece | How you reach it |
| --- | --- |
| Postgres 16 | `localhost:5432`, db/user/password `warehouse` / `dexmart` / `dexmart` |
| Pipeline CLI | `python -m pipeline` or `make pipeline` |
| Tests | `make test` |

`docker compose down -v` resets the database. Init schema lives in `sql/init.sql` and is applied only on a fresh volume.

## Repository structure

| Path | Purpose |
| --- | --- |
| `data/raw/` | Source CSVs (customers, products, FX, two order exports) |
| `pipeline/` | Extract, transform, load, CLI |
| `sql/init.sql` | Warehouse tables as inherited |
| `tests/` | Smoke tests (pass) and contract tests (mostly fail) |
| `docker-compose.yml` | Local Postgres |
| `Makefile` | `setup`, `db`, `pipeline`, `test`, `reset` |

## Data notes

All people and emails are fictional (`@example.com`). There is no real PII. The job is meant to run **offline** once the Postgres image and Python packages are cached.

Order exports:

- `orders_2026-03-10.csv` — original vendor layout (`created_at`)
- `orders_2026-03-11.csv` — newer vendor layout (`order_ts`, extra `channel`)

`fx_rates.csv` is USD→GHS (and GHS→GHS) by calendar date.

## Submission

Leave your changes and `FINDINGS.md` on the branch the interviewer supplied. Be ready to walk through:

- The evidence you collected
- The root causes you identified
- The changes you made, and why you chose that order
- How you verified a second run
- Remaining risks and what you would do next

Good luck.
