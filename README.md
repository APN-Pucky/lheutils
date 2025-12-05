# lheutils v0.0.2

A collection of utilities for working with LHE files.

## CLI Programs

| Program | Description |
|---------|-------------|
| `lhecheck` | Validate LHE files and check momentum conservation. |
| `lhefilter` | Filter LHE files based on process ID, particle PDG IDs, and event numbers.  |
| `lheinfo` | Display information about LHE files. |
| `lheshow` | Display specific events or init block from LHE files. |
| `lhesplit` | Split LHE events from input file into multiple output files. |
| `lhemerge` | Merge LHE files with identical initialization sections (inverse of lhesplit). |
| `lhestack` | Stack multiple LHE files into a single file.  |
| `lheunstack` | Split a single LHE file by process ID into separate files (inverse of lhestack).  |
| `lhe2lhe` | Convert LHE files with different compression and weight format options. |
