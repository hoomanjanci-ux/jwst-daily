"""One measured research object, two faithful renderings, zero API dependency.
This is transparently labelled computational analysis, never fake AI prose.
"""
import html
import json
import ai_message
import evidence_analysis

def build_pair(meta,proposal,payload):
    measured=payload.get('measured_image_statistics')
    narratives=evidence_analysis.research(meta,measured)
    pair={}
    for lang,narr in narratives.items():
        target=html.escape(str(meta.get('TARGNAME') or 'JWST'))
        hook=html.escape(narr['hook']);body=html.escape(narr['body']);why=html.escape(narr['why'])
        if lang=='fa':
            title='تحلیل محاسباتی داده — راز کیهان'
            facts=f"ابزار: {html.escape(str(meta.get('INSTRUME') or 'JWST'))} · فیلتر: {html.escape(str(meta.get('FILTER') or '—'))} · تاریخ رصد: {html.escape(str(meta.get('DATE-OBS') or '—'))}"
            label='این تحلیل از محاسبهٔ مستقیم فایل FITS ساخته شده است؛ متنِ تولیدشده با مدل هوش مصنوعی یا ادعای کشف تازه نیست.'
            source='منبع و روش'
        else:
            title='Computational data analysis — COSMIC INSIGHT'
            facts=f"Instrument: {html.escape(str(meta.get('INSTRUME') or 'JWST'))} · filter: {html.escape(str(meta.get('FILTER') or '—'))} · observation: {html.escape(str(meta.get('DATE-OBS') or '—'))}"
            label='Computed directly from the FITS science plane; not model-generated prose or a new-discovery claim.'
            source='Source and method'
        footer=ai_message.build_footer(lang,'ai')
        caption=f'🔭 <b>{ai_message.BRAND[lang]["ai"]}</b>\n{hook}\nMAST/STScI · '+('تحلیل محاسباتی' if lang=='fa' else 'Computational analysis')+'\n'+footer
        text=f'🔬 <b>{title}</b>\n\n{body}\n\n{why}\n\n{facts}\n\n<i>{label}</i>\n\n'
        text+=f'📡 <b>{source}</b>: <a href="https://archive.stsci.edu/proposal-id/{html.escape(str(proposal))}">MAST / STScI</a> · median + 5 × (1.4826 × MAD)\n\n'+footer
        if len(caption)>1024 or len(text)>4096:raise ValueError('Analysis exceeds Telegram limits')
        pair[lang]={'caption':caption,'text':text,'generator':'measured-data-analysis-v3'}
    canonical={'revision':3,'target':meta.get('TARGNAME'),'filter':meta.get('FILTER'),
               'statistics':measured,'method':'regular grid sample; threshold median+5*(1.4826*MAD)',
               'interpretation':'pixel distribution only, not source identification or discovery'}
    return {'canonical':canonical,'translations':pair}
