;; totalpnl deliberately off by $100 vs trades.csv sum (panel-golden-class bug).
((start_date 2024-01-02) (end_date 2024-04-20) (universe_size 3)
 (n_steps 80) (initial_cash 1000000.00) (final_portfolio_value 1001500.00)
 (n_round_trips 3)
 (metrics
  ((metric_types.metric_type.t.totalpnl 1500.00)
   (metric_types.metric_type.t.wincount 3)
   (metric_types.metric_type.t.losscount 0))))
