# Decisions

## 1. What does a good schedule mean?

A good schedule maximizes interview coverage and weighted coverage while keeping hard conflicts at zero. It also keeps student waiting time reasonable, uses rooms and panels efficiently, and preserves stability during replans. For replans, churn and shifted minutes are first-class quality metrics.

## 2. What happens when infeasible?

The system never silently drops interviews. If an interview cannot be placed, it remains visible as `unscheduled` with a reason code, human explanation, and suggested action. The validator remains separate from scheduling so infeasible or partially feasible results can still be audited.

## 3. Who decides which constraint bends?

Hard resource constraints never bend. Soft business priorities are configured in code and explained in the UI. When tradeoffs are unavoidable, the coordinator decides whether to add panels, extend windows, accept unresolved interviews, or manually override priorities.

## 4. How much reshuffling is acceptable?

The system measures reshuffling with churn percentage, changed appointment count, total shifted minutes, average shift, maximum shift, and stability. A 30-minute freeze horizon protects near-term appointments unless they are directly invalidated.

## 5. Why not regenerate everything?

Regenerating everything ignores operational reality: students may already be walking to rooms, company panels have been briefed, rooms are prepared, and coordinators are communicating live changes. Minimal-churn replanning protects that real-world context.

## 6. Algorithm choice

The implementation uses a hybrid deterministic candidate-slot scheduler. It has CP-SAT-style variables conceptually--interview, start, panel, room choices--but uses forward panel queues and occupancy bitsets so the default dataset remains demoable. OR-Tools is a natural future upgrade for bounded repair windows.

## 7. Complexity/scalability

The main bottleneck is candidate slot search under high shortlist pressure. The current engine uses 5-minute occupancy bitsets, company capacity diagnostics, and minimal repair scopes. At production scale, the next step would be partitioning by company/day, incremental solver windows, normalized database storage, and asynchronous scheduling jobs.

