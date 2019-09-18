import time
import bs4

def timed_str(data):
    res="-- %s: %s" % (time.ctime(data.tm.sec), data.data.encode('raw-unicode-escape').decode())
    return res

def julius_result(data):
    res=""
    doc = bs4.BeautifulSoup( data.data.encode('raw-unicode-escape').decode(), 'lxml')
    for s in doc.findAll('data'):
        rank = int(s['rank'])
        try:
            score = float(s['score'])
        except:
            score = 0.0
        text = s['text']
        res += "#%i: %s (%f)\n" % (rank, text, score)

    return res