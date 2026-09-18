# Calibration of the length instruction

Every phrasing of rule 2 of `page-writer.md` that has been tried, in order, with the share of pages whose first attempt failed the length check.

Ceiling: **20.0%**. Stop condition now: **running**.

| Variant | Flows | Mean rate | Mean bias | Instruction |
|---|---|---|---|---|
| [`v1`](v1.md) | 3 | 0.0% | 0.988 | **Write to the target length, not past it.** Aim at the target and stop. |

Each file is a rendering of the calibration observations held in the workspaces under `paths.stories_root`; nothing here is a source of truth, and `python -m calibration.cli report` rebuilds all of it.
