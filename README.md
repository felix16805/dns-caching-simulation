# Lightweight DNS Resolution-Caching Algorithm (HRFC)

## Layout
project/
  src/        # source code
  analysis/   # plot generation
  results/    # output CSV + PNG

## Setup
pip install matplotlib

## Run the verification tests first
cd src
python test_stack.py

## Run the demo (200 queries, prints metrics)
python run_experiment.py --mode demo

## Run the full TTL sweep (144 configurations)
python run_experiment.py --mode sweep

## Run the outage / serve-stale test
python run_experiment.py --mode outage

## Generate plots and summary table
cd ..
python analysis/analyze.py

## Outputs
results/sweep.csv            144 rows, one per configuration
results/outage.csv           outage test results
results/hit_vs_ttl.png       hit rate vs TTL
results/latency_bars.png     mean and p95 latency by policy
results/upstream_vs_ttl.png  upstream load vs TTL
results/summary.md           best config per policy