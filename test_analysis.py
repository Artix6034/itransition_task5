from datetime import date, timedelta

import numpy as np
import pytest

from analysis import analyze, split_series, TOTAL
from app import app

SETTINGS={'iqr':1.5,'z':3.,'window':3,'percent':40.,'alpha':.05,'chart':'line','degree':1,'method':'Any test'}


def test_known_spike_detected_by_each_test():
    values=np.array([10.]*10+[100.])
    days=[date(2026,1,1)+timedelta(days=i) for i in range(len(values))]
    result=analyze(days,values,SETTINGS)
    assert all(flags[-1] for flags in result['flags'].values())
    assert result['median']==10 and result['iqr']==0
    assert result['moving'][-1]==10


def test_constant_and_short_series_are_well_defined():
    days=[date(2026,1,1)]
    result=analyze(days,np.array([0.]),SETTINGS)
    assert result['std']==0 and result['anomalies']==[]
    assert np.isnan(result['moving'][0])


def test_daily_total_and_missing_records():
    d1,d2=date(2026,1,1),date(2026,1,2)
    rows=[(d1,'A',1),(d2,'A',2),(d1,'B',3),(d2,'B',4)]
    assert split_series(rows)[TOTAL][1].tolist()==[4,6]
    with pytest.raises(ValueError,match='Missing dates'):
        split_series(rows[:-1])


def test_routes_charts_pdf_and_bad_arguments():
    client=app.test_client()
    assert client.get('/').status_code==200
    for chart in ['line','bar','stacked']:
        response=client.get('/chart.png',query_string={'chart':chart,'degree':4})
        assert response.status_code==200 and response.data.startswith(b'\x89PNG')
    report=client.get('/report.pdf')
    assert report.status_code==200 and report.data.startswith(b'%PDF')
    assert client.get('/?window=0').status_code==400
    assert client.get('/?sheet=https://example.com/secret').status_code==400


def test_sheet_is_read_again_on_refresh(monkeypatch):
    import analysis
    class Response:
        content=b'Date,Mine,Production\n2026-01-01,A,1\n'
        def raise_for_status(self):
            pass
    response=Response()
    monkeypatch.setattr(analysis.requests,'get',lambda *a,**kw:response)
    url='https://docs.google.com/spreadsheets/d/test_sheet/edit'
    first,_=analysis.read_source(url)
    response.content=b'Date,Mine,Production\n2026-01-01,A,7\n'
    second,_=analysis.read_source(url)
    assert first[0][2]==1 and second[0][2]==7
