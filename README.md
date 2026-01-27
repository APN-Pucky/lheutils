# lheutils v0.0.6

A collection of utilities for working with LHE files.

## Installation

```bash
pip install lheutils
```

## CLI Programs

| Program | Description |
|---------|-------------|
| `lhe2lhe` | Convert LHE files with different compression and weight format options. |
| `lhecheck` | Validate LHE files and check momentum conservation. |
| `lhediff` | Compare two LHE files and report differences. |
| `lhefilter` | Filter LHE files based on process ID, particle PDG IDs, and event numbers.  |
| `lheinfo` | Display information about LHE files. |
| `lhemerge` | Merge LHE files with identical initialization sections (inverse of lhesplit). |
| `lheshow` | Display specific events or init block from LHE files. |
| `lhesplit` | Split LHE events from input file into multiple output files. |
| `lhestack` | Stack multiple LHE files into a single file.  |
| `lheunstack` | Split a single LHE file by process ID into separate files (inverse of lhestack).  |

## Examples

Get the first event with two gluons in the initial state:

```console
$ lhefilter  pwgevents-0001.lhe --incoming-a 21 --incoming-b 21 --max-events 1
<LesHouchesEvents version="3.0">
<init>
   2212   2212  4.0000000e+03  4.0000000e+03    -1    -1    -1    -1    -4     1
 1.3255800e+01  5.9743900e-01  1.0000000e+00  10001
<initrwgt /></init>
<event>
  5  10001 -1.9892700000e+01  3.8913200000e+00 -1.0000000000e+00  2.5869900000e-01
   21  -1   0   0 503 501  0.00000000e+00  0.00000000e+00  2.20685469e+02  2.20685469e+02  0.00000000e+00  0.0000e+00  9.0000e+00
   21  -1   0   0 502 512  0.00000000e+00  0.00000000e+00 -4.74395615e+02  4.74395615e+02  0.00000000e+00  0.0000e+00  9.0000e+00
   25   1   1   2   0   0  8.07980331e-01  3.58616348e+00  2.02904340e+02  2.38346235e+02  1.25000972e+02  0.0000e+00  9.0000e+00
   21   1   1   2 502 501 -4.44099588e+00 -2.19203006e+00 -1.25758039e+02  1.25855520e+02  2.33601546e-06  0.0000e+00  9.0000e+00
   21   1   1   2 503 512  3.63301555e+00 -1.39413342e+00 -3.30856446e+02  3.30879329e+02  3.81469727e-06  0.0000e+00  9.0000e+00
</event>
</LesHouchesEvents>
```

Display general information about an LHE file:

```console
$ lheinfo pwgevents-0500.lhe
------------------------------------------------------------
File: pwgevents-0500.lhe
Beam A: 2212 (PDF: -1) @ 4000.0 GeV
Beam B: 2212 (PDF: -1) @ 4000.0 GeV
Number of events: 100000 (negative: 16.72%)
Process 10001 cross-section: (1.326e+01 +- 5.974e-01) pb
  [21, 21] -> [21, 21, 25]: 65,542 events (65.5%, negative: 18.83%)
  [2, 21] -> [2, 21, 25]: 13,076 events (13.1%, negative: 14.51%)
  [1, 21] -> [1, 21, 25]: 6,934 events (6.9%, negative: 13.37%)
  [-1, 21] -> [-1, 21, 25]: 2,232 events (2.2%, negative: 14.83%)
  [-2, 21] -> [-2, 21, 25]: 1,944 events (1.9%, negative: 13.01%)
  [3, 21] -> [3, 21, 25]: 1,286 events (1.3%, negative: 12.44%)
  [-3, 21] -> [-3, 21, 25]: 1,265 events (1.3%, negative: 11.15%)
  [-4, 21] -> [-4, 21, 25]: 807 events (0.8%, negative: 12.27%)
  [4, 21] -> [4, 21, 25]: 796 events (0.8%, negative: 12.19%)
...
```

Remove negative weight events from an LHE file and display summary information:

```console
$ lhefilter --negative-weights pwgevents-0500.lhe | lheinfo
------------------------------------------------------------
File: <stdin>
Beam A: 2212 (PDF: -1) @ 4000.0 GeV
Beam B: 2212 (PDF: -1) @ 4000.0 GeV
Number of events: 83276 (negative: 0.00%)
Process 10001 cross-section: (1.326e+01 +- 5.974e-01) pb
  [21, 21] -> [21, 21, 25]: 53,203 events (63.9%, negative: 0.00%)
  [2, 21] -> [2, 21, 25]: 11,179 events (13.4%, negative: 0.00%)
  [1, 21] -> [1, 21, 25]: 6,007 events (7.2%, negative: 0.00%)
  [-1, 21] -> [-1, 21, 25]: 1,901 events (2.3%, negative: 0.00%)
  [-2, 21] -> [-2, 21, 25]: 1,691 events (2.0%, negative: 0.00%)
  [3, 21] -> [3, 21, 25]: 1,126 events (1.4%, negative: 0.00%)
  [-3, 21] -> [-3, 21, 25]: 1,124 events (1.3%, negative: 0.00%)
...
```
