TASK 5 DATA - Mining production

1. Generator
Weyland_Yutani_Mining_Simulator.xlsx has four sheets and two charts. It supports
1-12 mines, 1-180 days, Normal/Uniform, smoothing, weekly factors, a trend and
four probabilistic events. The original workbook is preserved.

Import it as a native Google spreadsheet. Enable editing for anyone with the
link. Keep the Data sheet's first three headers: Date, Mine, Production.
The source has one row per mine per day. Internal helper columns may stay.

2. Dashboard
Create a Python 3.11+ virtual environment and run:
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5065

Paste the Google Sheets URL into the source field and click Refresh data.
Alternatively, set the SHEET_URL environment variable before starting the app.
The server fetches Data!A:C on every dashboard refresh. Without a source URL,
it uses data/sample.csv, a clearly labelled 120-row workbook snapshot.
It never silently substitutes the sample when a Google Sheets request fails.

Use Apply to change the chart, series, polynomial degree or detection settings.
Charts and PDF links use the same in-memory snapshot as the displayed statistics.
Snapshots expire after 30 minutes or a server restart; refresh to create one.

Statistics and algorithms
- Mean, sample standard deviation (n-1), median and linearly interpolated IQR.
- IQR rule: outside [Q1-k*IQR, Q3+k*IQR].
- Z-score: absolute deviation from the mean divided by sample standard deviation.
- Moving average: full preceding window, excluding the current observation.
  The first window observations have no test result. A nonzero value compared
  with a zero baseline has unbounded percentage distance.
- Grubbs: two-sided, single most-extreme outlier test using Student's t quantile.
  It reports at most one observation per series. Trends and weekly cycles can
  violate its normality assumption; a flag does not prove an operational incident.
- Total output is the per-date sum, followed by the same statistical analysis.
- Missing/duplicate records and invalid values produce errors instead of zeroes.

3. PDF
Download PDF report creates statistics, settings, one chart per series and a
separate short section for every flagged observation. Unicode mine names are
supported by the embedded DejaVu font. A sample report is provided separately.

4. Deployment
The included render.yaml defines a free Python web service. Import this folder
as the root of a Git repository and use New > Blueprint in Render. Supply the
Google Sheets link as SHEET_URL. HOST is set to 0.0.0.0 for cloud hosting.
For manual deployment, build: pip install -r requirements.txt; start: python app.py.
Check /health and test the final URL from a separate browser before submission.
Reference: https://render.com/docs/deploy-flask

5. Demonstration checklist (no narration)
- Open the Google spreadsheet and change a generation parameter.
- Refresh the dashboard and show changed values and charts.
- Change anomaly thresholds, chart type and polynomial degree.
- Download and open the PDF, including anomaly details.

Submit a separate email to p.lebedev@itransition.com with full name, editable
spreadsheet link, deployed dashboard link, public code link and video link.
The instructor's later announcement says remaining tasks can be submitted
after project defense. No email is sent by this package.

Requirements source:
https://discord.com/channels/950701840901746708/1557625024754483230/1562044206334218261
https://discord.com/channels/950701840901746708/1557625024754483230/1562044532961579072
https://discord.com/channels/950701840901746708/1557625024754483230/1562044591937425572
