"""One canonical research narrative, one faithful translation. AI channels only.
The existing news writer is not changed; this module is used only by analyses.
"""
import html
import json
import ai_message


def build_pair(meta, proposal, payload):
    canonical = ai_message._lenient_json(ai_message._qai_chat([{'role':'user','content':
        ai_message.WRITER_PROMPT_EN +
        ' Write complete sentences. This is the single canonical analysis; the Persian '
        'version will be a translation of this exact content. Do not emit HTML.\n' +
        json.dumps(payload,ensure_ascii=False)[:5000]}],max_tokens=1200))
    if canonical and all(canonical.get(k) for k in ('hook','body')):
        canonical['generator']='ai' 
    if not canonical or canonical.get('generator')!='ai':
        raise ValueError('Canonical analysis unavailable; no placeholder publication')
    original={k:canonical.get(k,'') for k in ('hook','body','why')}
    translated=None
    for attempt in range(2):
        try:
            translated=ai_message._lenient_json(ai_message._qai_chat([{'role':'user','content':
                'Translate this ONE research narrative faithfully into natural Persian. '
                'Do not research, add, omit or change claims, numbers or uncertainties. '
                'Preserve target identifiers. Return JSON with exactly hook, body, why, '
                'plain text, no HTML. Complete sentences, no truncation.\n'+
                json.dumps(original,ensure_ascii=False)}],max_tokens=1200))
            if translated and all(isinstance(translated.get(k),str) and translated[k].strip()
                                  for k in ('hook','body')):break
        except Exception:
            translated=None
    if not translated or not all(translated.get(k) for k in ('hook','body')) or (original.get('why') and not translated.get('why')):
        raise ValueError('Persian translation unavailable; neither language is ready')
    pair={}
    for lang,narr in [('en',original),('fa',translated)]:
        # Escape model text: HTML markup belongs to the renderer, not the model.
        safe={k:html.escape(str(narr.get(k) or '')) for k in ('hook','body','why')}
        if safe['why']:safe['body']+=' '+safe['why']
        safe['generator']='shared-research+translation'
        _,text,_=ai_message.build_post(meta,proposal,payload,'ai',lang,narrative=safe)
        label='تحلیل هوش مصنوعی' if lang=='fa' else 'AI-assisted analysis'
        caption=(f'🔭 <b>{ai_message.BRAND[lang]["ai"]}</b>\n{safe["hook"]}\n'
                 f'🎯 {html.escape(str(meta.get("TARGNAME") or "JWST"))}\n'
                 f'{label} · MAST/STScI\n'+ai_message.build_footer(lang,'ai'))
        if len(caption)>1024 or len(text)>4096:
            raise ValueError('Pair exceeds Telegram size limits; never truncate HTML')
        pair[lang]={'caption':caption,'text':text,'generator':safe['generator']}
    return {'canonical':original,'translations':pair}
