# Scientific figures for the data article

These figures explain the dataset and BikeshareGPT framework. They are separate from the ten retired LLM visualization tasks.

| Figure | Content | Formats |
| --- | --- | --- |
| 1 | Source/derived composition and corrected task coverage | [PNG](figures/figure_1_data_overview.png), [PDF](figures/figure_1_data_overview.pdf), [SVG](figures/figure_1_data_overview.svg) |
| 2 | Station coordinates and availability, including missing capacity | [PNG](figures/figure_2_station_snapshot.png), [PDF](figures/figure_2_station_snapshot.pdf), [SVG](figures/figure_2_station_snapshot.svg) |
| 3 | Prompting, model response, execution/repair, grading and saved results | [PNG](figures/figure_3_framework.png), [PDF](figures/figure_3_framework.pdf), [SVG](figures/figure_3_framework.svg) |

After installing `requirements.txt`, regenerate from the repository root:

```bash
python scripts/make_paper_figures.py
```

[captions.json](figures/captions.json) contains full captions, statistics and source hashes. [station_figure_data.csv](figures/station_figure_data.csv) contains plotted station data. PNGs are 300 dpi; PDF/SVG provide vector versions. Generation needs no network or model calls.

The framework shows the actual 30-second subprocess, up to two repair retries, text fallback without code, separate execution/correctness outcomes and optional ungraded summary. v1.1 null targets additionally require successful execution. It distinguishes the historical 2,100-record study from v1.1, for which no fresh model results are claimed.

The editable Data in Brief manuscript remains a local draft pending author declarations, archival identifier and final licensing decisions.
