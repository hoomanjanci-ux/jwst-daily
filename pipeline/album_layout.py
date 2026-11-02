"""Concise, complete analysis caption. Never split, slice HTML, or drop footer links."""
import html
import re

def visible_units(text):
    plain=html.unescape(re.sub(r'<[^>]*>','',text))
    return len(plain.encode('utf-16-le'))//2

def caption(bundle,lang):
    post=bundle['translations'][lang];c=bundle['canonical'];m=bundle.get('meta') or {}
    s=c.get('statistics') or {}
    if not all(k in s for k in ('sample_count','above_5scatter_percent')):
        raise ValueError('Measured analysis evidence missing')
    source_text=post['text'];pos=source_text.rfind('———')
    if pos<0:raise ValueError('Analysis footer missing; cannot drop links')
    footer=source_text[pos:]
    links=list(dict.fromkeys(re.findall(r'<a\s+href="[^"]+"[^>]*>.*?</a>',source_text[:pos],re.S)))
    if not links:raise ValueError('Analysis source link missing')
    esc=lambda v:html.escape(str(v),quote=True)
    target=esc(c.get('target') or m.get('TARGNAME') or 'JWST')
    filt=esc(c.get('filter') or m.get('FILTER') or '—')
    inst=esc(m.get('INSTRUME') or 'JWST');date=esc(str(m.get('DATE-OBS') or '—')[:10])
    n=f"{int(s['sample_count']):,}";p=f"{float(s['above_5scatter_percent']):g}"
    extra='';q=s.get('brightest_quadrant_percent')
    if q is not None:
        extra=(f" سهم پُرتراکم‌ترین ربع از این پیکسل‌ها: {float(q):g}٪." if lang=='fa' else f" The most populated quadrant holds {float(q):g}% of these pixels.")
    wave=re.fullmatch(r'F(\d{3})(?:W2|[WMN])',str(c.get('filter') or m.get('FILTER') or ''))
    wavelength=''
    if wave and str(m.get('INSTRUME','')).upper()=='NIRCAM':
        w=f"{int(wave.group(1))/100:g}"
        wavelength=(f" طول موج تقریبی: {w} میکرومتر (فروسرخ نزدیک)." if lang=='fa' else f" Approx. wavelength: {w} µm (near-infrared).")
    if lang=='fa':
        title='راز کیهان | تحلیل داده'
        body=f'از {n} پیکسل معتبرِ نمونه، {p}٪ بیش از پنج برابر پراکندگی مقاوم بالاتر از میانه‌اند.'+extra+wavelength
        note='این سنجه الگوی روشنایی را توصیف می‌کند، نه شمارش ستاره یا کشف جرم.'
        mode='محاسبات FITS؛ انتخاب محور با کمک هوش مصنوعی.' if c.get('ai_assisted') else 'محاسبات مستقیم FITS؛ متن تولیدشده با مدل نیست.'
    else:
        title='COSMIC INSIGHT | Data analysis'
        body=f'Of {n} valid sampled pixels, {p}% exceed the median by more than five robust-scatter units.'+extra+wavelength
        note='This describes brightness patterns, not a star count or a discovery.'
        mode='FITS calculations; AI-assisted focus selection.' if c.get('ai_assisted') else 'Direct FITS calculations; not model-generated prose.'
    text=f'🔬 <b>{title}</b>\n<b>{target}</b> · {inst}/{filt} · {date}\n\n{body}\n\n{note}\n<i>{mode}</i>\n📡 '+ ' · '.join(links)+' · median+5×1.4826×MAD\n\n'+footer
    if visible_units(text)>1024:raise ValueError('Complete album caption exceeds Telegram limit; hold, never split')
    return text
