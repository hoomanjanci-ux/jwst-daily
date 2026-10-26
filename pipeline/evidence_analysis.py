"""Compute a real, reproducible image-data analysis. No invented astrophysics.
Statistics are from the SCI HDU in its native units (not the stretched PNG).
An above-threshold pixel fraction is NOT a source detection or discovery claim.
"""
import math
import re
import numpy as np
from astropy.io import fits

REVISION=3

def measure(path,hdu_index):
    with fits.open(path,memmap=False) as hdul:
        data=hdul[hdu_index].data
        if data.ndim!=2:raise ValueError('Only 2D science planes are supported')
        height,width=data.shape
        stride=max(1,int(math.ceil(math.sqrt(data.size/500_000))))
        sample=np.asarray(data[::stride,::stride],dtype=np.float64).ravel()
        valid=np.isfinite(sample)
        if 'DQ' in hdul and hdul['DQ'].data.shape==data.shape:
            flags=np.asarray(hdul['DQ'].data[::stride,::stride]).ravel()
            valid &= (flags & 3)==0  # JWST DO_NOT_USE and SATURATED
        finite=sample[valid]
        if finite.size<1000:raise ValueError('Insufficient valid science pixels')
        p16,med,p84,p99=np.percentile(finite,[16,50,84,99])
        mad=float(np.median(np.abs(finite-med)))
        scatter=1.4826*mad
        if not np.isfinite(scatter) or scatter<=0 or p99<=med:raise ValueError('Blank or degenerate image')
        return {'width':width,'height':height,'sample_stride':stride,'sample_count':int(finite.size),
                'finite_fraction':round(float(finite.size/sample.size),6),
                'median':float(med),'robust_scatter':scatter,
                'above_5scatter_percent':round(float(np.mean(finite>med+5*scatter)*100),4),
                'p99_above_median_scatter':round(float((p99-med)/scatter),3),
                'bunit':str(hdul[hdu_index].header.get('BUNIT','native FITS units'))}

def wavelength(filter_name):
    match=re.fullmatch(r'F(\d{3})(?:W2|[WMN])',str(filter_name or '').upper())
    return int(match.group(1))/100 if match else None

def research(meta,stats):
    required=['width','height','sample_count','median','robust_scatter','above_5scatter_percent']
    if not stats or not all(k in stats for k in required):raise ValueError('Measured evidence is required')
    if str(meta.get('TELESCOP','JWST')).upper()!='JWST':raise ValueError('Not JWST data')
    target=str(meta.get('TARGNAME') or 'JWST field');f=str(meta.get('FILTER') or 'unknown')
    wave=wavelength(f) if str(meta.get('INSTRUME','')).upper()=='NIRCAM' else None
    n=stats['sample_count'];pct=stats['above_5scatter_percent']
    shape=f"{stats['width']} × {stats['height']}"
    # These sentences are derived from values once, then rendered in two languages.
    # A target label is never guessed to be a galaxy, star or planet.
    fa=(f"این بار به‌جای حدس‌زدن دربارهٔ ماهیت «{target}»، خودِ دادهٔ جیمز وب را اندازه گرفتیم. "
        f"صفحهٔ علمی این فایل {shape} پیکسل دارد. در نمونهٔ منظم {n:,} پیکسل معتبر، "
        f"حدود {pct:g} درصد پیکسل‌ها از میانهٔ تصویر به‌اندازهٔ پنج برابر پراکندگیِ مقاوم روشن‌ترند. "
        "این عدد نشان می‌دهد بخش‌های روشن چه سهمی از نمونه دارند؛ به‌تنهایی تعداد ستاره‌ها، کشف جرم یا میزان روشنایی فیزیکی را تعیین نمی‌کند.")
    en=(f"For {target}, we measured the JWST data rather than guessing the target's nature. "
        f"The science plane contains {shape} pixels. In a regular sample of {n:,} valid pixels, "
        f"{pct:g}% lie above the image median by more than five robust-scatter units. "
        "This describes the bright tail of the sampled pixels; it is not a star count, a source detection, or an absolute brightness measurement.")
    if wave:
        fa+=f" فیلتر {f} نزدیک طول موج {wave:g} میکرومتر را نمونه‌برداری می‌کند؛ این طول موج در محدودهٔ فروسرخ نزدیک است."
        en+=f" Filter {f} samples approximately {wave:g} micrometres, in the near-infrared."
    return {'fa':{'hook':f'از پیکسل تا الگوی روشنایی؛ بررسی دادهٔ {target}',
                  'body':fa,'why':'این روشِ قابل‌تکرار، یک نقطهٔ شروع برای مقایسهٔ داده‌هاست؛ تشخیص ماهیت اجرام به کالیبراسیون و تحلیل علمی بیشتری نیاز دارد.'},
            'en':{'hook':f'From pixels to brightness patterns: {target}',
                  'body':en,'why':'This reproducible measurement is a starting point for comparison, not a substitute for calibrated source analysis.'}}

def validate(meta,stats,heuristic):
    if not stats or stats.get('sample_count',0)<1000:return False
    if stats.get('finite_fraction',0)<0.8:return False
    if stats.get('robust_scatter',0)<=0:return False
    if not math.isfinite(float(heuristic.get('score',0))):return False
    return float(heuristic.get('score',0))>=50
