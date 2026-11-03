"""Manually checked biographical date evidence for the content analysis.

This is a targeted evidence set, not an exhaustive author authority file.
Aliases map existing credits for analysis only; monthly records are unchanged.
"""
AUTHORS = []

def add(name, aliases, birth, death, sources, note=''):
    AUTHORS.append(dict(name=name, aliases=[name]+aliases, birth=birth, death=death,
                        sources=sources, note=note))

add('鲍勃·迪伦', ['鮑勃·迪伦','鲍勃．迪伦'], '1941-05-24', None,
    ['https://www.nobelprize.org/uploads/2018/06/bio-bibl-11.pdf'])
add('川端康成', [], '1899-06-14', '1972-04-16',
    ['https://www.ndl.go.jp/portrait/e/datas/6086/'], '生日按日本国立国会图书馆采用的 6 月 14 日；其他资料可能出现 6 月 11 日，不混用。')
add('巴勃罗·聂鲁达', ['聂鲁达'], '1904-07-12', None,
    ['https://poets.org/poet/pablo-neruda'], '本次只核验生日，未录入忌日。')
add('拉宾德拉纳特·泰戈尔', ['泰戈尔'], '1861-05-07', '1941-08-07',
    ['https://www.nobelprize.org/laureate/583%26lang%3Den'])
add('王小波', [], '1952-05-13', '1997-04-11',
    ['https://cuhk.edu.hk/ics/21c/media/articles/c042-199706023.pdf'])
add('沈从文', [], '1902-12-28', '1988-05-10',
    ['https://www.chinawriter.com.cn/xdzj/347.shtml'])
add('张爱玲', [], '1920-09-30', None,
    ['https://lib.hku.hk/files/general/research/guides/Zhang_Ailing_brochure.pdf','https://wui.nwupl.edu.cn/202302/lijingyi/zhangailing.html'],
    '9 月 8 日为常用逝世纪念日期，亦为被发现逝世日期；单列，不作为精确死亡日统计。')
add('简·奥斯汀', ['简奥斯汀','简．奥斯汀'], '1775-12-16', '1817-07-18',
    ['https://janeaustensociety.org.uk/jane-austen/biography/'])
add('约翰·济慈', ['济慈','约翰-济慈'], '1795-10-31', '1821-02-23',
    ['https://poets.org/poet/john-keats'])
add('乔治·奥威尔', ['奥威尔'], '1903-06-25', '1950-01-21',
    ['https://www.orwellfoundation.com/the-orwell-foundation/orwell/biography/'])
add('查尔斯·狄更斯', ['查尔斯·约翰·赫芬姆·狄更斯','狄更斯'], '1812-02-07', '1870-06-09',
    ['https://dickensmuseum.com/blogs/charles-dickens-museum/a-very-dickens-birthday','https://www.collections.dickensmuseum.com/pro874'])
add('詹姆斯·乔伊斯', ['詹姆斯-乔伊斯'], '1882-02-02', '1941-01-13',
    ['https://jamesjoyce.ie/james-joyce/'])
add('马塞尔·普鲁斯特', ['普鲁斯特','马赛尔·普鲁斯特'], '1871-07-10', '1922-11-18',
    ['https://catalogue.bnf.fr/ark%3A/12148/cb119207126.public'])
add('维克多·雨果', ['维克多雨果','雨果'], '1802-02-26', '1885-05-22',
    ['https://www.maisonsvictorhugo.paris.fr/paris/collections/les-photographies/victor-hugo-26-fevrier-1802-22-mai-1885'])
add('阿瑟·柯南·道尔', [], '1859-05-22', None,
    ['https://conandoyleestate.com/the-family'], '本次只核验生日，未录入忌日。')
add('村上春树', [], '1949-01-12', None,
    ['https://www.waseda.jp/top/assets/uploads/2025/01/7d7998fc09c0d7027b9f19010920e2be.pdf'])
add('今敏', [], '1963-10-12', '2010-08-24',
    ['https://konstone.s-kon.net/modules/works/index.php?content_id=1&page=print','https://konstone.s-kon.net/modules/info/index.php?page=article&storyid=66'])
add('威廉·巴特勒·叶芝', ['叶芝'], '1865-06-13', '1939-01-28',
    ['https://www.nobelprize.org/laureate/593'])
add('威廉·福克纳', [], '1897-09-25', '1962-07-06',
    ['https://www.nobelprize.org/prizes/literature/1949/faulkner/facts/?source=post_page---------------------------'])
add('阿尔贝·加缪', ['加缪','阿尔贝-加缪','阿尔贝．加缪'], '1913-11-07', '1960-01-04',
    ['https://www.nobelprize.org/prizes/literature/1957/camus/facts/?related=1'])
add('加西亚·马尔克斯', ['加夫列尔·加西亚·马尔克斯','马尔克斯'], '1927-03-06', '2014-04-17',
    ['https://centrogabo.org/gabo/contemos-gabo/quien-fue-gabriel-garcia-marquez'])
add('欧内斯特·海明威', ['欧内斯特-海明威','欧内斯特·米勒·海明威','欧内斯特·米勒尔·海明威','海明威'], '1899-07-21', '1961-07-02',
    ['https://www.jfklibrary.org/sites/default/files/2018-07/EHScrapbook1.pdf','https://www.nobelprize.org/prizes/literature/1954/hemingway/biographical/?vm=r'])
add('奥克塔维奥·帕斯', [], '1914-03-31', '1998-04-19',
    ['https://poets.org/poet/octavio-paz'])
add('苏珊·桑塔格', ['苏珊-桑塔格','苏珊．桑塔格'], '1933-01-16', '2004-12-28',
    ['https://susansontag.com/SusanSontag/index.shtml'])
add('阿希尔-克劳德·德彪西', [], '1862-08-22', '1918-03-25',
    ['https://catalogue.bnf.fr/ark%3A/12148/cb13893072d'])
add('威廉·莎士比亚', ['莎士比亚'], None, '1616-05-03',
    ['https://www.folger.edu/blogs/shakespeare-and-beyond/shakespeare-and-cervantes-400-years/','https://www.folger.edu/explore/shakespeares-life/'],
    '死亡日公历换算为 5 月 3 日，传统纪念日为儒略历 4 月 23 日；生日仅有推定，不计入精确生日统计。')

SPECIAL_DATES = [
    dict(name='张爱玲', md='09-08', kind='逝世纪念／发现日期', source='https://wui.nwupl.edu.cn/202302/lijingyi/zhangailing.html'),
    dict(name='威廉·莎士比亚', md='04-23', kind='传统忌日（儒略历）', source='https://www.shakespeare.org.uk/explore-shakespeare/shakespedia/william-shakespeare/when-did-shakespeare-die/'),
]
