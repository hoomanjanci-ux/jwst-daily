"""Read-only live verification: fetch, translate, render; NEVER sends Telegram."""
import json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import news_rss as news
items=[]
for feed in news.FEEDS:
    try:
        for item in news.fetch_feed(feed['url']):
            if news.on_topic(item) and item.get('dt'):
                item.update(source=feed['source'],source_fa=feed['source_fa'])
                items.append(item)
        if items:break
    except Exception:continue
if not items:raise RuntimeError('No official source available for live verification')
item=max(items,key=lambda x:x['dt'])
translated=news._fa_rewrite(item)
if not news._valid_fa_rewrite(translated):raise RuntimeError('Persian generation unavailable; safe hold works, but live translation not verified')
post=news._post_text(item,'fa',False,translated)
assert item['link'].replace('&','&amp;') in post
# Exercise real backup while the AI provider is unavailable, without any send call.
with patch.object(news.ai_message,'_qai_chat',return_value=None):
    backup=news._fa_rewrite(item)
if not news._valid_fa_rewrite(backup):raise RuntimeError('Live backup translation failed')
result={'source_title':item['title'],'source_url':item['link'],'source_date':item['date'],
        'persian':translated,'persian_post':post,'backup':backup,
        'checks':{'persian_title_and_body':True,'source_link_retained':True,'backup_live_passed':True,'telegram_sends':0}}
Path('persian-news-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
