;; wincount + losscount + n_round_trips deliberately off vs trades.csv.
((start_date 2024-01-02) (end_date 2024-04-20) (universe_size 3)
 (n_steps 80) (initial_cash 1000000.00) (final_portfolio_value 1001600.00)
 (n_round_trips 5)
 (metrics
  ((metric_types.metric_type.t.totalpnl 1600.00)
   (metric_types.metric_type.t.wincount 4)
   (metric_types.metric_type.t.losscount 1))))
