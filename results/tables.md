### trajectory signs

| | Models | No negative circuit | No positive circuit | No filtered positive circuit |
|---|---|---|---|---|
| reference 24 | 506 | 70 (14%) | 48 (9%) | 105 (21%) |
| all usable | 613 | 82 (13%) | 43 (7%) | 96 (16%) |
| with reactions | 540 | 71 (13%) | 27 (5%) | 80 (15%) |
| with reactions, no events | 455 | 62 (14%) | 23 (5%) | 71 (16%) |

| Definition | 0 loops | 1 | 2 | 3 | 4 to 10 | over 10 | over budget |
|---|---|---|---|---|---|---|---|
| Thomas circuits | 23 | 40 | 34 | 37 | 106 | 234 | 139 |
| reference 24 filters | 48 | 67 | 67 | 45 | 86 | 198 | 102 |
| reference 24 filters plus rank condition | 63 | 67 | 65 | 43 | 84 | 189 | 102 |

| Definition | Row | Models | Loops share no arrow | essay's (k, j) | Sontag's k with j | per-loop types | only negative loops integrate |
|---|---|---|---|---|---|---|---|
| Thomas circuits | 1 | 40 | 40 | 2 of 4 | 2 of 4 | 2 of 4 | 2 of 3 |
| Thomas circuits | 2 | 34 | 29 | 4 of 9 | 4 of 9 | 4 of 10 | 4 of 6 |
| Thomas circuits | 3 | 37 | 14 | 3 of 16 | 3 of 16 | 3 of 20 | 3 of 10 |
| reference 24 filters | 1 | 67 | 67 | 2 of 4 | 2 of 4 | 2 of 4 | 2 of 3 |
| reference 24 filters | 2 | 67 | 43 | 5 of 9 | 5 of 9 | 5 of 10 | 4 of 6 |
| reference 24 filters | 3 | 45 | 20 | 5 of 16 | 5 of 16 | 5 of 20 | 5 of 10 |
| reference 24 filters plus rank condition | 1 | 67 | 67 | 2 of 4 | 2 of 4 | 2 of 4 | 2 of 3 |
| reference 24 filters plus rank condition | 2 | 65 | 45 | 5 of 9 | 5 of 9 | 5 of 10 | 4 of 6 |
| reference 24 filters plus rank condition | 3 | 43 | 17 | 5 of 16 | 5 of 16 | 5 of 20 | 5 of 10 |

Theorem checks: {"forced models excluded": 178, "multistable": 12, "multistable without refined positive circuit": [], "oscillating": 101, "oscillating without negative circuit": []}

Integrators: {"models with any integrating loop (ref24_rank, complete)": 13, "models with complete ref24_rank enumeration": 511}

The essay's test, kinds of behaviour per row (reference 24 filters plus rank condition):

| Row | Predicted | Behaviours and mixtures | Merged into four | Not settled |
|---|---|---|---|---|
| 1 | 4 | 6 | 4 | 4 |
| 2 | 9 | 9 | 5 | 5 |
| 3 | 16 | 6 | 4 | 2 |

Running-total readings on the main definition (occupancy of (k, j) cells):

| Row | Predicted | Strict | Loose | Paired |
|---|---|---|---|---|
| 1 | 4 | 2 | 4 | 3 |
| 2 | 9 | 5 | 9 | 5 |
| 3 | 16 | 5 | 9 | 5 |

Paired running totals: 6 models have one; small models with a loop through one: ['BIOMD0000000639']


Amplifying loops after the filters, braking loops as drawn: {"rows": {"1": 42, "2": 52, "3": 33}, "patterns": {"1": 2, "2": 3, "3": 4}, "moved": 85, "clocks without a brake": [], "cells": {"(1, 0)": 21, "(1, 1)": 21, "(2, 0)": 4, "(2, 1)": 36, "(2, 2)": 12, "(3, 0)": 2, "(3, 1)": 6, "(3, 2)": 20, "(3, 3)": 5}}

### random signs

| | Models | No negative circuit | No positive circuit | No filtered positive circuit |
|---|---|---|---|---|
| reference 24 | 506 | 70 (14%) | 48 (9%) | 105 (21%) |
| all usable | 613 | 82 (13%) | 42 (7%) | 93 (15%) |
| with reactions | 540 | 71 (13%) | 30 (6%) | 81 (15%) |
| with reactions, no events | 455 | 62 (14%) | 25 (5%) | 71 (16%) |

| Definition | 0 loops | 1 | 2 | 3 | 4 to 10 | over 10 | over budget |
|---|---|---|---|---|---|---|---|
| Thomas circuits | 24 | 37 | 36 | 35 | 107 | 236 | 138 |
| reference 24 filters | 49 | 64 | 70 | 38 | 92 | 199 | 101 |
| reference 24 filters plus rank condition | 64 | 64 | 68 | 36 | 90 | 190 | 101 |

| Definition | Row | Models | Loops share no arrow | essay's (k, j) | Sontag's k with j | per-loop types | only negative loops integrate |
|---|---|---|---|---|---|---|---|
| Thomas circuits | 1 | 37 | 37 | 3 of 4 | 3 of 4 | 3 of 4 | 3 of 3 |
| Thomas circuits | 2 | 36 | 30 | 3 of 9 | 3 of 9 | 3 of 10 | 3 of 6 |
| Thomas circuits | 3 | 35 | 12 | 3 of 16 | 3 of 16 | 3 of 20 | 3 of 10 |
| reference 24 filters | 1 | 64 | 64 | 3 of 4 | 3 of 4 | 3 of 4 | 3 of 3 |
| reference 24 filters | 2 | 70 | 45 | 4 of 9 | 4 of 9 | 4 of 10 | 4 of 6 |
| reference 24 filters | 3 | 38 | 14 | 5 of 16 | 5 of 16 | 5 of 20 | 5 of 10 |
| reference 24 filters plus rank condition | 1 | 64 | 64 | 3 of 4 | 3 of 4 | 3 of 4 | 3 of 3 |
| reference 24 filters plus rank condition | 2 | 68 | 47 | 4 of 9 | 4 of 9 | 4 of 10 | 4 of 6 |
| reference 24 filters plus rank condition | 3 | 36 | 11 | 5 of 16 | 5 of 16 | 5 of 20 | 5 of 10 |

Theorem checks: {"forced models excluded": 178, "multistable": 12, "multistable without refined positive circuit": [], "oscillating": 101, "oscillating without negative circuit": []}

Integrators: {"models with any integrating loop (ref24_rank, complete)": 13, "models with complete ref24_rank enumeration": 512}

The essay's test, kinds of behaviour per row (reference 24 filters plus rank condition):

| Row | Predicted | Behaviours and mixtures | Merged into four | Not settled |
|---|---|---|---|---|
| 1 | 4 | 6 | 4 | 5 |
| 2 | 9 | 9 | 5 | 4 |
| 3 | 16 | 6 | 4 | 2 |

Running-total readings on the main definition (occupancy of (k, j) cells):

| Row | Predicted | Strict | Loose | Paired |
|---|---|---|---|---|
| 1 | 4 | 3 | 4 | 4 |
| 2 | 9 | 4 | 9 | 4 |
| 3 | 16 | 5 | 8 | 5 |

Paired running totals: 6 models have one; small models with a loop through one: ['BIOMD0000000639']


Amplifying loops after the filters, braking loops as drawn: {"rows": {"1": 39, "2": 55, "3": 29}, "patterns": {"1": 2, "2": 3, "3": 4}, "moved": 85, "clocks without a brake": [], "cells": {"(1, 0)": 19, "(1, 1)": 20, "(2, 0)": 5, "(2, 1)": 37, "(2, 2)": 13, "(3, 0)": 2, "(3, 1)": 6, "(3, 2)": 17, "(3, 3)": 4}}

