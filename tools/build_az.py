"""Build a static version of american-zoo.com from the downloaded pages.

usage: python3 -I build_az.py <chapters_dir> <home_html> <o_nas_html> <out_dir> <css_from>
"""
import html
import json
import os
import re
import shutil
import sys

CH, HOME, ONAS, OUT, CSS = sys.argv[1:6]

m = json.load(open(os.path.join(CH, "map.json")))


def slug_of(href):
    s = href.strip("/").split("/")[-1]
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def nice(t):
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip().strip("-").strip()
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) > 0.8 * len(letters):
        # lowercase Cyrillic words, keep Latin ones (POD, Canteen, Parole) as written
        words = [w if re.search(r"[A-Za-z]", w) else w.lower() for w in t.split(" ")]
        t = " ".join(words)
        t = re.sub(r"(^|[.!?]\s+)([^A-Za-zА-Яа-яЁё]*)([а-яё])", lambda x: x.group(1) + x.group(2) + x.group(3).upper(), t)
        t = re.sub(r"\b([A-Z])([A-Z]+)\b", lambda x: x.group(0) if len(x.group(0)) <= 3 or "POD" in x.group(0) else x.group(1) + x.group(2).lower(), t)
    return t.replace("Check OFF THE Block", "Check off the block")


def clean(body):
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S | re.I)
    body = re.sub(r"<(/?)(p|br|em|strong|b|i|ul|ol|li|h3|h4)\b[^>]*?/?>", lambda x: "<%s%s>" % (x.group(1), x.group(2).lower()), body, flags=re.I)
    body = re.sub(r"<(?!/?(p|br|em|strong|b|i|ul|ol|li|h3|h4)>)[^>]+>", "", body)
    body = body.replace("&nbsp;", " ")
    body = re.sub(r"<p>\s*</p>", "", body)
    body = re.sub(r"(<br>\s*){2,}", "<br>", body)
    return body.strip()


chapters = {}
for href, fn in m.items():
    s = open(fn, encoding="utf-8", errors="replace").read()
    t = re.search(r'<h1 class="text-heading">(.*?)</h1>', s, re.S)
    title = nice(t.group(1)) if t else ""
    prev = re.search(r'book_prev_page">Ранее: <a href="([^"]+)"', s)
    nxt = re.search(r'book_next_page">Далее: <a href="([^"]+)"', s)
    locked = "доступна для прочтения всем зарегистрированным" in s
    body = ""
    if t and not locked:
        start = t.end()
        end = s.find('<br clear="all">', start)
        body = clean(s[start:end])
    chapters[href] = {"href": href, "slug": slug_of(href), "title": title, "locked": locked or not body,
                      "prev": prev.group(1) if prev else None, "next": nxt.group(1) if nxt else None, "body": body}

# untitled chapter: name it from its address
for c in chapters.values():
    if not c["title"]:
        c["title"] = "Животная война"

# reading order: follow "Далее" from the preface; fill gaps with "Ранее" links
by_prev = {c["prev"]: h for h, c in chapters.items() if c["prev"]}
order, cur = [], "book/predislovie/"
while cur and cur in chapters and cur not in order:
    order.append(cur)
    cur = chapters[cur]["next"] or by_prev.get(cur)
for h in chapters:  # anything not reached keeps the site's listing order
    if h not in order:
        order.append(h)

if os.path.exists(OUT):
    for f in os.listdir(OUT):
        if f != ".git":
            p = os.path.join(OUT, f)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
os.makedirs(os.path.join(OUT, "ch"), exist_ok=True)
os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
shutil.copy(CSS, os.path.join(OUT, "assets", "style.css"))
with open(os.path.join(OUT, "assets", "style.css"), "a") as f:
    f.write("""
/* american-zoo */
body::before { display: none; }
.hero { padding: 0; }
.hero .wrap { padding-top: 88px; padding-bottom: 72px; }
.hero .sub { color: var(--muted); font-size: 1.1rem; margin: 0 auto; max-width: 560px; }
.hero .btns { margin-top: 28px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.toc { list-style: none; padding: 0; margin: 0; counter-reset: ch; }
.toc li { counter-increment: ch; display: flex; gap: 14px; align-items: baseline; padding: 12px 4px; border-bottom: 1px solid var(--line); }
.toc li::before { content: counter(ch); color: var(--muted); font-variant-numeric: tabular-nums; min-width: 2ch; text-align: right; }
.toc a { text-decoration: none; font-weight: 600; }
.toc .lock { color: var(--muted); }
.toc .lock small { margin-left: 8px; font-size: .8rem; }
.chapter { font-size: 1.08rem; line-height: 1.75; }
.chapter p { margin: 0 0 1.1em; }
.pn { display: flex; justify-content: space-between; gap: 16px; border-top: 1px solid var(--line); padding-top: 18px; margin-top: 36px; }
.pn a { text-decoration: none; max-width: 48%; }
.voices { display: grid; gap: 12px; }
.voice { background: var(--soft); border-radius: var(--radius); padding: 18px 20px; }
.voice .meta { color: var(--muted); font-size: .85rem; margin-bottom: 6px; }
.voice p { margin: 0; }
""")

NAV = [("index.html", "Главная"), ("book.html", "Книга"), ("people.html", "Люди"), ("about.html", "О проекте и авторе")]


def page(title, desc, body, current, depth=0):
    up = "../" * depth
    nav = "\n".join('      <a href="%s%s"%s>%s</a>' % (up, h, ' aria-current="page"' if h == current else "", n) for h, n in NAV)
    return """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap&subset=cyrillic" rel="stylesheet">
<link rel="stylesheet" href="%sassets/style.css">
</head>
<body>
<header class="site-head">
  <div class="wrap-wide">
    <a class="brand" href="%sindex.html">American Zoo</a>
    <button class="nav-toggle" aria-expanded="false" aria-controls="nav">Меню</button>
    <nav class="nav" id="nav">
%s
    </nav>
  </div>
</header>
%s
<footer class="site-foot">
  <div class="wrap-wide">
    <span>© 2021–2026 Arlen Sunday</span>
    <span><a href="https://arlensunday.com">arlensunday.com</a> · <a href="https://sundaypoetry.com">sundaypoetry.com</a> · <a href="https://theworldconstitution.org">theworldconstitution.org</a></span>
  </div>
</footer>
<script>
(function(){var b=document.querySelector('.nav-toggle'),n=document.querySelector('.nav');if(b&&n)b.addEventListener('click',function(){b.setAttribute('aria-expanded',n.classList.toggle('open')?'true':'false')});})();
</script>
</body>
</html>
""" % (html.escape(title), html.escape(desc), up, up, nav, body)


def esc(s):
    return html.escape(s)


open_list = [chapters[h] for h in order if not chapters[h]["locked"]]

# chapter pages (open ones); prev/next walk the open chapters
for i, c in enumerate(open_list):
    p = open_list[i - 1] if i else None
    n = open_list[i + 1] if i + 1 < len(open_list) else None
    pn = '<nav class="pn">%s%s</nav>' % (
        '<a href="%s.html">← %s</a>' % (p["slug"], esc(p["title"])) if p else '<a href="../book.html">← Оглавление</a>',
        '<a href="%s.html">%s →</a>' % (n["slug"], esc(n["title"])) if n else '<a href="../book.html">Оглавление →</a>')
    num = order.index(c["href"]) + 1
    body = """<main class="wrap">
  <div class="page-head"><div class="kicker">Глава %d · <a href="../book.html">Оглавление</a></div><h1>%s</h1></div>
  <div class="chapter">
%s
  </div>
  %s
</main>""" % (num, esc(c["title"]), c["body"], pn)
    desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c["body"])))[:150]
    open(os.path.join(OUT, "ch", c["slug"] + ".html"), "w").write(page("%s — Американский зоопарк" % c["title"], desc, body, "book.html", 1))

# table of contents
items = []
for h in order:
    c = chapters[h]
    if c["locked"]:
        items.append('<li class="lock">%s<small>скоро</small></li>' % esc(c["title"]))
    else:
        items.append('<li><a href="ch/%s.html">%s</a></li>' % (c["slug"], esc(c["title"])))
toc = """<main class="wrap">
  <div class="page-head"><div class="kicker">Книга</div><h1>Оглавление</h1>
  <p class="lead">%d глав. Сейчас открыты %d — остальные появятся позже.</p>
  <p class="note"><span class="todo">Решить с Арленом: вся книга открыта или часть по подписке; прислать рукопись.</span></p></div>
  <ol class="toc">
%s
  </ol>
</main>""" % (len(order), len(open_list), "\n".join(items))
open(os.path.join(OUT, "book.html"), "w").write(page("Оглавление — Американский зоопарк", "Оглавление повести «Американский зоопарк».", toc, "book.html"))

# people: archive of demands, proposals and questions
s = open(HOME, encoding="utf-8", errors="replace").read()
tabs = [("nav-home", "Требуют"), ("nav-profile", "Предлагают"), ("nav-contact", "Спрашивают")]
blocks = []
for tid, label in tabs:
    a = s.find('id="%s"' % tid, s.find('id="nav-tabContent"'))
    b = min([x for x in (s.find('class="tab-pane', a + 10), s.find("</section>", a)) if x > 0])
    part = s[a:b]
    vs = []
    for date, user, text in re.findall(r'fa-calendar"></i>\s*([\d.]+)</a></li>\s*<li><a[^>]*><i class="fa fa-user"></i>\s*([^<]+)</a>.*?<p><span>(.*?)</span></p>', part, re.S):
        vs.append('<div class="voice"><div class="meta">%s · %s</div><p>%s</p></div>' % (date, esc(user.strip()), esc(html.unescape(re.sub(r"<[^>]+>", "", text)).strip())))
    blocks.append("<h2>%s</h2>\n<div class=\"voices\">\n%s\n</div>" % (label, "\n".join(vs)))
people = """<main class="wrap">
  <div class="page-head"><div class="kicker">Люди</div><h1>Требуют, предлагают, спрашивают</h1>
  <p class="lead">Что читатели книги писали на сайте в 2021 году. Многие из этих мыслей потом вошли в черновик <a href="https://theworldconstitution.org">Всемирной конституции</a>.</p></div>
%s
</main>""" % "\n".join(blocks)
open(os.path.join(OUT, "people.html"), "w").write(page("Люди — Американский зоопарк", "Требования, предложения и вопросы читателей.", people, "people.html"))

# about: project (original text) + author (Arlen's own account)
o = open(ONAS, encoding="utf-8", errors="replace").read()
t = re.search(r'<h1[^>]*>.*?</h1>', o, re.S)
onas = ""
if t:
    end = o.find("</section>", t.end())
    onas = clean(o[t.end():end])
about = """<main class="wrap">
  <div class="page-head"><div class="kicker">О проекте</div><h1>Зачем эта книга</h1></div>
  <div class="chapter">
%s
  </div>
  <h2>Об авторе</h2>
  <div class="chapter">
<p>Родился в Ленинграде 8 ноября 1966 года; родители учились в Ленинградской консерватории. В два месяца был отправлен в Одессу, к бабушке и дедушке по материнской линии, в шесть лет переехал в Москву к маме.</p>
<p>Из школы был исключён в конце второго класса за отказ вступать в пионеры и другие советские организации. С четвёртого по восьмой класс — интернат для трудновоспитуемых подростков, потом — «вольный странник» по Советскому Союзу.</p>
<p>В 18 лет призван в армию: Байконур, рота контроля оборудования на площадке, где готовили к старту «Буран». После службы — Ашхабад, пять лет в институте искусств на отделении вокала. В 1991 году вернулся в Москву и занялся концертным бизнесом.</p>
<p>В 1997 году переехал в Бостон; 6 августа того же года родился сын Максимилиан. В 2000 году оформил корпорацию Ocean Fresh, Inc. — разноплановый бизнес, в основном помощь русскоговорящим людям с жильём, работой и адаптацией в США.</p>
<p>В 2008 году, получая американское гражданство, сменил фамилию Атаханов на Sunday и начал менять жизнь к лучшему: каждое воскресенье убирать из будней что-то негативное, когда-то приобретённое неосознанно.</p>
  </div>
  <p><a class="btn" href="https://arlensunday.com">Подробнее — arlensunday.com →</a></p>
</main>""" % onas
open(os.path.join(OUT, "about.html"), "w").write(page("О проекте и авторе — Американский зоопарк", "О книге «Американский зоопарк» и её авторе Arlen Sunday.", about, "about.html"))

# home
first = open_list[0]
opened = "\n".join('<a class="card" href="ch/%s.html"><h3>%s</h3><p>%s</p></a>' % (
    c["slug"], esc(c["title"]),
    esc(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c["body"]))).strip()[:140]) + "…") for c in open_list)
home = """<div class="hero">
  <div class="wrap">
    <h1>Американский зоопарк</h1>
    <p class="sub">Повесть о тюрьме в Биллерике, штат Массачусетс — написанная изнутри. Arlen Sunday.</p>
    <div class="btns"><a class="btn" href="ch/%s.html">Читать с начала</a><a class="btn btn-ghost" href="book.html">Оглавление</a></div>
  </div>
</div>
<main class="wrap">
  <section>
    <p class="lead">Кто сидит в американской тюрьме, кто её охраняет, как устроен день и что система делает с людьми по обе стороны решётки. Имена изменены. Тон — без прикрас.</p>
  </section>
  <section>
    <h2>Открытые главы</h2>
    <div class="cards">
%s
    </div>
    <p style="margin-top:16px"><a href="book.html">Все %d глав →</a></p>
  </section>
  <section>
    <h2>Люди</h2>
    <p>Читатели книги писали, чего они требуют, что предлагают и о чём спрашивают. <a href="people.html">Читать →</a></p>
  </section>
</main>""" % (first["slug"], opened, len(order))
open(os.path.join(OUT, "index.html"), "w").write(page("Американский зоопарк — повесть Arlen Sunday", "Повесть Arlen Sunday о тюрьме в Биллерике, Массачусетс.", home, "index.html"))
open(os.path.join(OUT, ".nojekyll"), "w").close()

print("chapters", len(order), "open", [c["title"] for c in open_list])
