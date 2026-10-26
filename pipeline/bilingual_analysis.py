"""One measured research object, two faithful renderings.
AI can select evidence-backed analysis focus from a closed schema. It cannot
invent claims. API failure falls back to honestly labelled computational analysis.
"""
import html
import json
import ai_message
import evidence_analysis

def select_focus(meta,stats):
    allowed=['bright_tail','sampling_quality']
    if 'p99_above_median_scatter' in stats:allowed.append('distribution')
    if stats.get('brightest_quadrant_percent') is not None:allowed.append('spatial_concentration')
    if evidence_analysis.wavelength(meta.get('FILTER')):allowed.append('wavelength')
    default=['spatial_concentration'] if 'spatial_concentration' in allowed else ['distribution'] if 'distribution' in allowed else ['bright_tail']
    prompt='Choose the two most informative measured-image analysis focuses. Do not classify the target or invent discoveries. Return JSON only: {"primary":"allowed_id","secondary":"allowed_id"}. Allowed IDs: '+','.join(allowed)
    try:
        content=ai_message._qai_chat([{'role':'system','content':prompt},
            {'role':'user','content':json.dumps({'instrument':meta.get('INSTRUME'),'filter':meta.get('FILTER'),'measurements':stats})}],timeout=(5,12),max_tokens=120)
        plan=ai_message._lenient_json(content)
        if not isinstance(plan,dict) or plan.get('primary') not in allowed:return default,False
        focus=list(dict.fromkeys(x for x in [plan['primary'],plan.get('secondary')] if x in allowed))
        return focus,True
    except Exception:
        return default,False


def build_pair(meta,proposal,payload):
    measured=payload.get('measured_image_statistics')
    if not measured:raise ValueError('Measured evidence required')
    focus,assisted=select_focus(meta,measured)
    narratives=evidence_analysis.research(meta,measured,focus)
    pair={}
    for lang,narr in narratives.items():
        target=html.escape(str(meta.get('TARGNAME') or 'JWST'))
        hook=html.escape(narr['hook']);body=html.escape(narr['body']);why=html.escape(narr['why'])
        if lang=='fa':
            title=('تحلیل داده با کمک هوش مصنوعی' if assisted else 'تحلیل محاسباتی داده')+' — راز کیهان'
            facts=f"ابزار: {html.escape(str(meta.get('INSTRUME') or 'JWST'))} · فیلتر: {html.escape(str(meta.get('FILTER') or '—'))} · تاریخ رصد: {html.escape(str(meta.get('DATE-OBS') or '—'))}"
            label=('محاسبات مستقیم فایل FITS؛ انتخاب محور بررسی با کمک هوش مصنوعی. متنِ دو زبان از همان اندازه‌گیری‌ها ساخته شده است؛ ادعای کشف تازه نیست.' if assisted else 'این تحلیل از محاسبهٔ مستقیم فایل FITS ساخته شده است؛ متنِ تولیدشده با مدل هوش مصنوعی یا ادعای کشف تازه نیست.')
            source='منبع و روش'
        else:
            title=('AI-assisted data analysis' if assisted else 'Computational data analysis')+' — COSMIC INSIGHT'
            facts=f"Instrument: {html.escape(str(meta.get('INSTRUME') or 'JWST'))} · filter: {html.escape(str(meta.get('FILTER') or '—'))} · observation: {html.escape(str(meta.get('DATE-OBS') or '—'))}"
            label=('Direct FITS measurements, with AI-assisted focus selection. Both languages render the same evidence; not a new-discovery claim.' if assisted else 'Computed directly from the FITS science plane; not model-generated prose or a new-discovery claim.')
            source='Source and method'
        footer=ai_message.build_footer(lang,'ai')
        caption=f'🔭 <b>{ai_message.BRAND[lang]["ai"]}</b>\n{hook}\nMAST/STScI · '+(('بررسی با کمک هوش مصنوعی' if assisted else 'تحلیل محاسباتی') if lang=='fa' else ('AI-assisted analysis' if assisted else 'Computational analysis'))+'\n'+footer
        text=f'🔬 <b>{title}</b>\n\n{body}\n\n{why}\n\n{facts}\n\n<i>{label}</i>\n\n'
        text+=f'📡 <b>{source}</b>: <a href="https://archive.stsci.edu/proposal-id/{html.escape(str(proposal))}">MAST / STScI</a> · median + 5 × (1.4826 × MAD)\n\n'+footer
        if len(caption)>1024 or len(text)>4096:raise ValueError('Analysis exceeds Telegram limits')
        pair[lang]={'caption':caption,'text':text,'generator':'measured-data-analysis-v3'}
    canonical={'revision':3,'target':meta.get('TARGNAME'),'filter':meta.get('FILTER'),
               'statistics':measured,'analysis_focus':focus,'ai_assisted':assisted,'method':'regular grid sample; threshold median+5*(1.4826*MAD)',
               'interpretation':'pixel distribution only, not source identification or discovery'}
    return {'canonical':canonical,'translations':pair}
