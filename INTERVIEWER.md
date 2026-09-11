# INTERVIEWER ONLY — do not share with candidates

**Remove this file** from any clone, zip, or Codespace you give a candidate. If they open the public repo in Cursor, tell them not to read `INTERVIEWER.md` (or delete it on the candidate branch before the session).

This is a 60–75 minute live Data Engineer screen. Same shape as the fullstack / DevOps assessments: inherited broken system, no published bug count, `FINDINGS.md`, AI only in the last stage if you allow it.

## Setup (under 5 minutes)

```bash
git clone https://github.com/dexwin-tech-ltd/dexwin-data-eng-assessment.git
cd dexwin-data-eng-assessment
rm INTERVIEWER.md          # if this is the candidate worktree
docker compose up -d
python3 -m venv .venv && source .venv/bin/activate
make setup && make wait-db
make pipeline              # exits 0, data is wrong
make test                  # smoke passes; contract tests fail
```

Confirm `make sql` opens `psql` and `SELECT COUNT(*) FROM fact_orders;` returns more than one row for `ORD-1005`.

If port 5432 is taken, either stop the other Postgres or change the published port in `docker-compose.yml` and `DATABASE_URL`.

## What “good” looks like by the clock

| Time | Bar |
| --- | --- |
| 10 min | Stack up, first SQL look, at least one written finding |
| 25 min | Named grain / reload / Monday-file problems with evidence |
| 50 min | Dedup + idempotent load (or a truncate-and-reload with eyes open) and day-2 timestamps populated |
| 65 min | Nairobi reporting dates and/or null amounts not zeroed; mart rebuilt after facts |
| 75 min | Walkthrough: what they shipped, what they deferred, how they would watch this in prod |

Do **not** require every test green. A hire-level candidate makes the key warehouse tests green and can explain the rest.

## Planted defects

Bugs are intentional. The job is written to look confident and finish successfully.

### 1. Schema drift (Monday / day-2 export)

| | |
| --- | --- |
| Symptom | `ORD-1010`–`ORD-1012` load with `created_at` and `reporting_date` null. `ORD-1004` from day 2 is a second row with a null timestamp. |
| Where | `data/raw/orders_2026-03-11.csv` uses `order_ts` (and `channel`) instead of `created_at`. `pipeline/extract.py` concatenates files. `pipeline/transform.py` `transform_orders` only reads `created_at`. |
| Why it is silent | `pd.concat` aligns on column names; missing `created_at` becomes NaT; `errors="coerce"` keeps the job green. |
| Fix | Normalize aliases (`order_ts` → event timestamp) before parse. Do not drop `channel` if you want to keep it; it is optional. |
| Tests | `test_order_ts_alias_is_used_when_created_at_missing`, `test_day2_orders_are_loaded_with_event_times`, `test_full_extract_includes_both_export_days` |

### 2. Silent nulls → zero revenue

| | |
| --- | --- |
| Symptom | `ORD-1006` (blank amount) and `ORD-1007` (`N/A`) become `0` in `fact_orders` and would hit GMV. |
| Where | `clean_amount` in `pipeline/transform.py` — `to_numeric(...).fillna(0)` |
| Fix | Leave invalid amounts as null; write `rejected_rows` (table already exists) or skip facts; never coalesce to 0. |
| Tests | `test_missing_and_invalid_amounts_are_not_coerced_to_zero`, `test_invalid_amounts_do_not_land_as_zero_revenue` |

### 3. Duplicate keys

| | |
| --- | --- |
| Symptom | `ORD-1005` appears twice (copy-paste in day-1 file). `ORD-1004` appears twice (restated on day 2, amount `12.00` → `10.00`). |
| Where | Raw files; `dedupe_orders` is a no-op; `fact_orders.order_id` has no unique constraint (`sql/init.sql`). |
| Fix | Dedupe by `order_id`, later `source_file` / later event time wins; add `UNIQUE (order_id)` and upsert or truncate-partition. |
| Tests | `test_duplicate_order_id_keeps_a_single_latest_row`, `test_fact_orders_has_unique_order_ids`, `test_restated_order_keeps_the_later_amount` |

### 4. Timezone mishandling

| | |
| --- | --- |
| Symptom | `ORD-1009` (`2026-03-10T21:30:00Z`) is reported as **10 Mar** instead of **11 Mar** EAT. Mixed naive / `Z` / `+03:00` strings. |
| Where | `parse_event_ts` / `reporting_date_from_ts` treat values as naive/UTC calendar dates. `REPORTING_TZ` in `pipeline/config.py` is unused. Comment in transform claims “Finance confirmed UTC.” |
| Contract | Naive → `Africa/Nairobi`. Aware / `Z` → convert to Nairobi, then take the date. Store UTC if they add `TIMESTAMPTZ`. |
| Gold cases | `21:30Z` 10 Mar → date **11** Mar. Naive `2026-03-10 23:30:00` → date **10** Mar (not localized as UTC). `21:45+03:00` → date **10** Mar. |
| Tests | `test_utc_evening_lands_on_next_nairobi_date`, `test_naive_timestamp_is_interpreted_as_nairobi_not_utc`, `test_offset_timestamp_uses_the_embedded_offset` |

### 5. Missing idempotency

| | |
| --- | --- |
| Symptom | Second `make pipeline` **crashes** on `dim_customers` PK, or (if they drop the PK) **doubles** facts. No truncate, no upsert, no watermark. |
| Where | `pipeline/load.py` `insert_frame` is append-only. Dims have PKs; facts do not. |
| Fix | `TRUNCATE ...` then load, or `INSERT ... ON CONFLICT`. Facts need a unique key. Dimensions before facts if they add FKs. |
| Tests | `test_reload_is_idempotent` |

### 6. Dependency / refresh order

| | |
| --- | --- |
| Symptom | `daily_gmv` is empty after a successful first load (or stale after a reload). Facts are inserted **before** dimensions. Comments mention a future parallel insert. |
| Where | `load_warehouse`: `refresh_daily_gmv(conn)` runs first; GMV SQL reads `fact_orders` before this run’s rows exist. Insert order is facts → customers → products. |
| Extra | `refresh_daily_gmv` uses `INSERT` into a PK table and sums **all** statuses / raw `amount` (mixed currencies, includes refunds, includes zeros). |
| Fix | Load dims, then facts, then rebuild the mart (`TRUNCATE` + insert or upsert). GMV = `paid` only, in GHS. |
| Tests | `test_daily_gmv_is_refreshed_from_loaded_facts` |

### 7. FX ignored (supporting)

| | |
| --- | --- |
| Symptom | USD amounts are summed as if they were GHS. `apply_fx` assigns `amount_ghs = amount`. |
| Where | `pipeline/transform.py`; `data/raw/fx_rates.csv` is extracted and passed in. |
| Rates | 10 Mar USD→GHS **15.70**; 11 Mar **15.82**. Join on **reporting** date, not file date. |
| Tests | `test_usd_amount_is_converted_to_ghs_for_the_reporting_date` |

### 8. Unknown product (supporting)

| | |
| --- | --- |
| Symptom | Only appears if they `inner` join `dim_products`. Seed: `ORD-1002` / `P-15` is **not** in `products.csv`. |
| Tests | `test_unknown_product_is_not_dropped` |

## Expected first-run shape (broken)

After one successful `make pipeline` on a clean volume:

- `dim_customers`: 6 rows
- `dim_products`: 5 rows
- `fact_orders`: 14 rows (10 from day 1 including the `ORD-1005` dup + 4 from day 2). Day-2 timestamps null.
- `ORD-1005` count = 2; `ORD-1004` count = 2
- `ORD-1006` / `ORD-1007` amount = 0
- `daily_gmv`: 0 rows
- Second run: `refresh_daily_gmv` may insert rows from the *first* load, then the job dies on `dim_customers` PK. Candidates often notice GMV “suddenly appearing” after a failed retry.

## Target numbers (if they finish FX + TZ + dedupe)

Valid fact grain (invalid amounts excluded or quarantined):  
`1001, 1002, 1003, 1004 (restated 10.00 USD), 1005 (once), 1008 (refunded), 1009, 1010, 1011, 1012` → **10** fact rows (or 12 if they keep two rejected rows in facts as NULL amounts — accept either if GMV is clean).

Reporting dates (Nairobi):

| order_id | event | reporting_date |
| --- | --- | --- |
| ORD-1001 | `20:15Z` | 2026-03-10 |
| ORD-1002 | naive `23:30` | 2026-03-10 |
| ORD-1003 | `21:45+03:00` | 2026-03-10 |
| ORD-1004 | restated `09:00Z` 11 Mar | 2026-03-11 |
| ORD-1005 | `10:00Z` | 2026-03-10 |
| ORD-1008 | `08:00Z` refunded | 2026-03-10 |
| ORD-1009 | `21:30Z` | **2026-03-11** |
| ORD-1010 | `07:15+03:00` | 2026-03-11 |
| ORD-1011 | naive `22:40` | 2026-03-11 |
| ORD-1012 | `20:05Z` | 2026-03-11 |

Paid GMV GHS (approximate):

- 10 Mar: 45 + 2.50×15.70 + 80×15.70 + 99×15.70 = **45 + 39.25 + 1256 + 1554.30 = 2894.55**
- 11 Mar: 10×15.82 + 15 + 80×15.82 + 2.50×15.82 + 45 = **158.20 + 15 + 1265.60 + 39.55 + 45 = 1523.35**

Do not treat exact cents as a hire gate if they can show the join and the date rule.

## Rubric

Score each 1–4. **Hire** if average ≥ 3 and they did not leave reload-unsafe facts. **Strong hire** if they also fix TZ or nulls and talk about monitoring.

| Signal | 1 — No | 2 — Weak | 3 — Hire | 4 — Strong |
| --- | --- | --- | --- | --- |
| Diagnosis | Random edits, no SQL | Notices one symptom | Ties symptoms to files + code | Forms hypotheses, disproves them |
| Grain / dups | Ignores `ORD-1005` | Filters ad hoc | Defines `order_id` grain + latest wins | Constraint + restatement story |
| Idempotency | Re-run doubles or crashes, ignored | “Just run once” | Truncate/upsert they can defend | Incremental key / watermark mentioned |
| Schema drift | Never opens day-2 header | Hard-codes new column | Alias map / schema contract | Warns on unexpected columns |
| Data quality | Accepts `0` GMV | Drops bad rows silently | Quarantine or fail-loud | Metrics + sample in `rejected_rows` |
| Time / FX | Unaware | Knows TZ is unused | Implements Nairobi date or FX | Both + DST/offset verbal |
| Tests | Deletes failing tests | Chases green blindly | Uses tests as spec | Adds a case they care about |
| Communication | Silent or rambling | Lists bugs | Prioritises with Finance impact | Clear `FINDINGS.md`, residual risk |
| AI use (if allowed) | Pastes blindly | Some review | Bounded prompts, verifies SQL | Rejects a bad suggestion out loud |

### Red flags

- Changes tests so `fillna(0)` is “correct”
- Drops day-2 file to make timestamps look clean
- `DELETE FROM fact_orders` by hand in `psql` as the only idempotency story
- Cannot explain why `21:30Z` moves the reporting date
- Rewrites the pipeline in a new framework and ships nothing

### Green flags

- Starts with `SELECT order_id, COUNT(*)` and a raw-file diff
- Calls out `REPORTING_TZ` sitting unused
- Mentions late-arriving / restated facts without being prompted
- Asks whether GMV is booked on event date vs settlement date
- Adds a unique constraint and a failing test they wrote themselves

## Facilitator prompts

Use when they stall. Do not point at the line.

- “How would you know if Monday’s file actually landed?”
- “What is the grain of that fact table?”
- “What happens if ops runs this twice after a page?”
- “Which calendar is Finance using for ‘10 March GMV’?”
- “Show me a row you do not trust, and why.”
- “If you only had fifteen more minutes, what would you lock in?”

## AI policy (align with the other Dexwin screens)

Open-book docs and search are fine. **No AI** for stages 1–3 unless you decide otherwise. If you allow AI in stage 4, they must keep the chat visible and re-run `make pipeline && make test`.

## After the session

Keep their branch. Glance at `FINDINGS.md` before the debrief — the write-up is part of the signal. Reset with `make reset` before the next candidate.
