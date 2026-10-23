"""Interpolate any normalized comparison, independently of topic or source."""
import math

def snapshot(data,year):
    anchors=sorted(int(y) for y in data['tables'])
    year=max(anchors[0],min(anchors[-1],year))
    lo=max(y for y in anchors if y<=year)
    hi=min(y for y in anchors if y>=year)
    a=data['tables'][str(lo)];b=data['tables'][str(hi)]
    fraction=(year-lo)/(hi-lo) if hi!=lo else 0
    values={c:(math.floor(a[c]+(b[c]-a[c])*fraction) if data.get('interpolation')=='integer' else a[c]+(b[c]-a[c])*fraction) for c in a.keys() & b.keys()}
    return values,lo,hi,fraction
