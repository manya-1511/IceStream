# Streaming Engine (Day 2)

This folder will hold the Python streaming replay engine: it reads
`data/processed/orders_clean.csv`, sorts rows by `invoice_date`, and emits
them one at a time (or in small batches) at a configurable speed —
simulating a live order feed from real historical data.

Not built yet. Empty on purpose so Day 1 stays focused and reviewable.
