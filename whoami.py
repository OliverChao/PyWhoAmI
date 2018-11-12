######################################################
#
# PyWhoAmI - Oliver Loves Annabelle 
# written by Oliver (fei.chao.1009@gmail.com)
# inspired by  Annabelle
#
######################################################
import argparse
import glob
import os
import shutil
import random
import re
import requests
import requests_cache
import sys
import __init__
from concurrent import futures

import pdfkit
import time
##############################################################
#reference:howdoi written by Benjamin Gleitzman (gleitz@mit.edu)
##############################################################
from retrying import retry
from pygments import highlight
from pygments.lexers import guess_lexer, get_lexer_by_name
from pygments.lexers import CppLexer
from pygments.formatters.terminal import TerminalFormatter
from pygments.util import ClassNotFound

from pyquery import PyQuery as pq
from requests.exceptions import ConnectionError
from requests.exceptions import SSLError

'''变量命名参照优质开源项目 howdoi 的基本风格'''
# Handle imports for Python 2 and 3
if sys.version < '3':
    import codecs
    from urllib import quote as url_quote
    from urllib import getproxies

    # Handling Unicode: http://stackoverflow.com/a/6633040/305414
    def u(x):
        return codecs.unicode_escape_decode(x)[0]
else:
    from urllib.request import getproxies
    from urllib.parse import quote as url_quote
    def u(x):
        return x

URL = 'blog.csdn.net'

USER_AGENTS = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:11.0) Gecko/20100101 Firefox/11.0',
               'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100 101 Firefox/22.0',
               'Mozilla/5.0 (Windows NT 6.1; rv:11.0) Gecko/20100101 Firefox/11.0',
               ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/536.5 (KHTML, like Gecko) '
                'Chrome/19.0.1084.46 Safari/536.5'),
               ('Mozilla/5.0 (Windows; Windows NT 6.1) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.46'
                'Safari/536.5'), )

# SCHEME = "https://"
# VERIFY_SSL_CERTIFICATE = True

if os.getenv('WHOAMI_DISABLE_SSL'):  # Set http instead of https
    SCHEME = 'http://'
    VERIFY_SSL_CERTIFICATE = False
else:
    SCHEME = 'https://'
    VERIFY_SSL_CERTIFICATE = True


SEARCH_URLS = {
    'bing': SCHEME + 'www.bing.com/search?q=site:{0}%20{1}',
    'google': SCHEME + 'www.google.com/search?q=site:{0}%20{1}'
}

STAR_HEADER = u('\u2605')
ANSWER_HEADER = u('{2}  Answer from {0} {2}\n{1}')
NO_ANSWER_MSG = '< no answer given >'

XDG_CACHE_DIR = os.environ.get('XDG_CACHE_HOME',
                               os.path.join(os.path.expanduser('~'), '.cache'))
# 设置存缓
CACHE_DIR = os.path.join(XDG_CACHE_DIR, 'whoami')
CACHE_FILE = os.path.join(CACHE_DIR, 'cache{0}'.format(
    sys.version_info[0] if sys.version_info[0] == 3 else ''))

# PDF files dir
scripFilePath = os.path.split(os.path.realpath(__file__))[0]
PDF_DIR = os.path.join(scripFilePath,'whoamiPDFdir')
CPP_DIR = os.path.join(scripFilePath,'whoamiCPPdir')
'''
很尴尬，不知道为什么，对于自己定义的session对象，在用到requests_cache时，
必须定义和执行两遍（多遍）才能生成相应的cache文件
但是，看源代码，install_cache,是可以对所有Requests有效的
Installs cache for all ``Requests`` requests by monkey-patching ``Session``
直接所以 直接用 requests.get()请求，不再生成session对象
'''
# whoami_session = requests.session()

'''放弃使用全局列表'''
# links=[]

# def _meg_query(query_list):
#     return ' '.join(quert_list).replace('?','')


def _enable_cache():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    requests_cache.install_cache(CACHE_FILE)


def _clear_dir(dir):
    if os.path.exists(dir):
        # os.removedirs(PDF_DIR)
        try:
            shutil.rmtree(dir)
        except OSError as e:
            print('[!!]delete error!')
            raise e


def _clear_cache():
    for cache in glob.iglob('{0}*'.format(CACHE_FILE)):
        os.remove(cache)


def show_result_dict(result):
    num = 0
    for k, v in result.items():
        print('[*{}*] '.format(str(num)),end='')
        print(k, end=' [*link*] ')
        print(v)
        num += 1


def show_code(args, result):
    url = list(result.values())[args['print']]
    main_page = _parse_url(url)
    s = _get_code(main_page, args) or 'sorry,this article has no code...'
    print(s)


def _extract_dict_from_bing(html):
    html.remove_namespaces()
    # global links
    # links = [a.attrib['href'] for a in html('.b_algo')('h2')('a')]
    # return [a.attrib['href'] for a in html('.b_algo')('h2')('a')]
    '''10/24/2018
    把原来的只返回links，改成现在的，
    返回{[*num*]name：link}字典形式
    唉，，要改好多函数名，
    '''
    dic={}
    for a in html('.b_algo')('h2')('a'):
        # name ='[*{0}*] {1}'.format(str(num),a.text)
        name = a.text
        link = a.attrib['href']
        dic[name] = str(link)
        # num+=1
    return dic


#  暂时不设置代理，google 先放一下
def _extract_dict_from_google(html):
    return [a.attrib['href'] for a in html('.l')] or \
        [a.attrib['href'] for a in html('.r')('a')]


def _extract_links(html, search_engine):
    if search_engine == 'bing':
        return _extract_dict_from_bing(html)
    return _extract_dict_from_google(html)


@retry(stop_max_attempt_number=3)
def _get_result(url):
    try:
        # return whoami_session.get(url, headers={'User-Agent': random.choice(USER_AGENTS)}, proxies=get_proxies()).text
        return requests.get(url, headers={'User-Agent': random.choice(USER_AGENTS)},).text
        # verify = VERIFY_SSL_CERTIFICATE).text

    except requests.exceptions.SSLError as e:
        print('[ERROR] Encountered an SSL Error.\n')
        print('[*]retrying again automatically ')
        raise e


def _get_dict(query):
    search_url = SEARCH_URLS.get('bing', 'google')
    search_url = search_url.format(URL, url_quote(query))
    # search_url :   site:blog.csdn.net 1173 HDU
    result = _get_result(search_url)
    html = pq(result)
    # return the anser_list
    return _extract_links(html, 'bing')


def confirm_links(args):
    '''
    进一步确认网页的提取的
    :param args:
    :return:       dict
    '''
    dic = _get_dict(args['query'])
    if not dic:
        return False

    def _is_article(link):
        return re.search('article/details/\d+', link)

    # question_links = [link for link in links if _is_article(link)]
    # https://blog.csdn.net/u013177568/article/details/62432761
    confirm_dict = {k: v for k, v in dic.items() if _is_article(v)}
    return confirm_dict


def whoami(args):
    args['query'] = ' '.join(args['query']).replace('?', '')
    try:
        return confirm_links(args) or 'Sorry, couldn\'t find any help with that topic\n'
    except (ConnectionError, SSLError):
        return 'Failed to establish network connection\n'


def _parse_url(url):
    '''

    :param url:   网页url
    :return: 返回网页的主要区域的pyquery
    '''
    page = _get_result(url)
    html = pq(page)
    # the main part of the article
    return html('.blog-content-box')


def _add_color(code,args):
    if not args['color']:
        return code
    lexer = None
    try:
        lexer = guess_lexer(code)
    except ClassNotFound:
        return code
    return highlight(code, CppLexer(), TerminalFormatter(bg='dark'))


# *********************
# 代码格式化显示
def _get_code(main_page,args):
    '''
    :param   main_page:main_page=_parse_url(url)
    :param   args: args
    :return: str
    '''
    html = main_page('article')('pre')('code') or main_page('article')('pre')
    if not html:
        return None
    ans=[]
    ans_split = '\n' + '<==>' * 17 + '\n'
    if args['all_code']:
        for node in html:
            node = pq(node)
            s = node.html()
            #     s=re.sub('</?[^>]+>','',s)
            s = re.sub('<((span)|(code)|(/span)|(/code)){1}.*?>', '', s)
            s = s.replace('&gt;', '>').replace('&lt;', '<')
            ans.append(_add_color(s,args))
    else:
        node = pq(html[-1])
        s = node.html()
        s = re.sub('<((span)|(code)|(/span)|(/code)){1}.*?>', '', s)
        s = s.replace('&gt;', '>').replace('&lt;', '<')
        ans.append(_add_color(s,args))
    return ans_split.join(ans)


def get_parser():
    parser = argparse.ArgumentParser(description='show or save what you want via the command line')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--pdf', help='save answer to PDF', action='store_true')
    group.add_argument('--cpp', help='save code to a cpp file', action='store_true')
    group2 = parser.add_mutually_exclusive_group()
    group2.add_argument('--rmpdf', help='delete the PDF_DIR',
                        action='store_true')
    group2.add_argument('--rmcpp', help='delete the CPP_DIR',
                        action='store_true')
    parser.add_argument('query', metavar='QUERY', type=str, nargs='*',
                        help='the article you want to get')
    parser.add_argument('-o', '--open-pdf', help='open the pdf or cpp after save the pdf or cpp', action='store_true')
    parser.add_argument('-s', '--save', help='save some pdfs ',
                        type=int, nargs='*')
    parser.add_argument('-c', '--color', help='colorized output',
                        action='store_true')
    parser.add_argument('-p', '--print', help='print the perfect code',
                        type=int, default=0)
    parser.add_argument('-t', '--translate', help='translate output',
                        action='store_true')
    
    parser.add_argument('-a', '--all-code', help='display all the code of one article', action='store_true')
    parser.add_argument('-n', '--number-link',
                        help='select answer in specified position (default: 0) uesed by --pdf or --cpp',
                        default=0, type=int)
    parser.add_argument('-v', '--version', help='displays the current version of howdoi', action='store_true')
    parser.add_argument('-l', '--list', help='list the dict on the basis of name:link ', action='store_true')

    parser.add_argument('-C', '--clear-cache', help='clear the cache',
                        action='store_true')
    return parser


def save_to_cpp(args, result):
    ans_split = '\n' + '<==>' * 17 + '\n'
    url = list(result.values())[args['number_link']]
    main_page = _parse_url(url)
    title = main_page('h1').eq(0).text()
    title = re.sub('[<>\?\\\/:\*\s]', '.', title)
    s = _get_code(main_page, args)
    if not s:
        print('sorry , this article has no code...')
        print('please try another...')
        return
    if not os.path.exists(CPP_DIR):
        os.makedirs(CPP_DIR)
    filePath = os.path.join(CPP_DIR,title+'.cpp')

    if _test_is_open_if_exists(args,filePath):
        return     

    code = s.split(ans_split)[-1]
    with open(filePath,'w')as f:
        f.write(code)
        print('[*]save successfully...')
    try:
        open_after_save(args,filePath)
    except:
        print('[!!]文件未打开，可能保存时发生IO错误。。')
        print('[!!]open failed')


def open_after_save(args, PDFpath):
    if not args['open_pdf']:
        return
    try:
        if len(args['save']):
            return False
    except TypeError as e:
        pass
    # if args['pdf'] and PDFpath.split('.')[-1]!='pdf':
    #     PDFpath += '.pdf'
    else:
        os.popen(PDFpath)


def _test_is_open_if_exists(args,filePath):
    try:
        if len(args['save']):
            return False
    except TypeError as e:
        pass

    if args['open_pdf']:
        if os.path.exists(filePath):
            print('文件已经存在，直接打开')
            os.popen(filePath)
            return True
    else:
        return False


def save_to_pdf(url,args):

    html_template = u"""
    <!DOCTYPE html>

    <html>
        <head>
            <meta charset="utf-8" />
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        </head>
        <body>
            <!-- <center><h1>{title}</h1></center> -->
            {content}
        </body>
    </html>
    """
    options = {
        'page-size': 'Letter',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': "UTF-8",
        'custom-header': [
            ('Accept-Encoding', 'gzip')
        ],
        'cookie': [
            ('cookie-name1', 'cookie-value1'),
            ('cookie-name2', 'cookie-value2'),
        ],
        'outline-depth': 10,
    }

    main_page = _parse_url(url)
    title = main_page('h1').eq(0).text()
    title = re.sub('[<>\?\\\/:\*\s\[\]\(\)\-]', '.', title)
    html = html_template.format(title='Oliver loves Annabelle forever~', content=main_page.html())
    
    # wkhtmltopdf_path = r'C:\Users\Oliver\Desktop\wkhtmltox\bin\wkhtmltopdf.exe')
    wkhtmltopdf_path = os.getcwd()+'/wkhtmltox/bin/wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

    if not os.path.exists(PDF_DIR):
        os.makedirs(PDF_DIR)
    filePath = os.path.join(PDF_DIR, title+'.pdf')

    # 提前检验是否要打开并检验文件是否存在
    # 10/28/2018 5：43pm 优化
    if _test_is_open_if_exists(args,filePath):
        return 
    try:
        print('[*] save to ', filePath)
        pdfkit.from_string(html, filePath, configuration=config)
        print('[*] successfully ')
        # open_PDF_after_save(args,filePath)
    except:
        print('[!!]要保存的网页可能有网页冲突')
        print('[注]保存html等语言的文档冲突的几率较大')

        print('[!!]save failed')
        print('[!!]如果事因为图片路径造成的保存失败，文字和代码部分则会正常生成pdf，')
    try:
        open_after_save(args, filePath)
    except:
        print('[!!]文件未打开，可能保存时发生IO错误。。')
        print('[!!]请重新生成pdf，或者，该网页的结构不符合生成pdf的标准')
        print('[~~]请见谅。。。。')


def translate():
    '''
    想加入
    '''
    url = 'http://fy.iciba.com/ajax.php?a=fy'
    content = input('Please enter what you want to translate, and be careful not to have line breaks:')
    data = {
     'f': 'auto',
     't': 'auto',
     'w': content
    }
    headers= {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.92 Safari/537.36'}
    response = requests.post(url, data=data, headers=headers)
    # print(response.json())
    # print(response.json()['content']['out'])
    trans = '翻译出错'
    try:
        trans=response.json()['content']['word_mean'][0]
    except KeyError:
        trans = response.json()['content']['out']
    finally:
        print(trans)


def save_many_pdf(s, args):
    '''
    11/11/2018 写入，异步爬取多个文件，进行保存
    :param s: 总 文案列表
    :param args:
    :return: None
    '''
    start = time.time()
    workers = min(len(args['save']), 20)
    links = [s[i] for i in args['save']]
    # print(links)
    with futures.ThreadPoolExecutor(workers) as executor:
        to_do_map={}
        for url in links:
            future = executor.submit(save_to_pdf(url,args))
            to_do_map[future] = url
        done_iter = futures.as_completed(to_do_map)
        # executor.map(save_to_pdf, links, args)
    print('time ',time.time()-start)

def run():
    parser = get_parser()
    args = vars(parser.parse_args())
    if args['version']:
        # 暂时先这么写
        print('whoami version :: ',__init__.__version__)
        print('author : Oliver ')
        print('One more thing, Oliver loves Annabelle.')
        return
    if args['clear_cache']:
        _clear_cache()
        print('Cache cleared successfully')
        return
    if args['rmcpp']:
        _clear_dir(CPP_DIR)
        print('CPP_DIR cleared successfully')
        return
    if args['rmpdf']:
        _clear_dir(PDF_DIR)
        print('PDF_DIR cleared successfully')
        return

    if args['translate']:
        translate()
        return 
        
    if not args['query']:
        print(parser.print_help())
        return
    if not os.getenv('WHOAMI_DISABLE_CACHE'):
        _enable_cache()

    start = time.time()
    # result对换域名来说影响很小
    result = whoami(args)
    end = time.time()
    print('[**]the total time ,', end-start)

    # no result link
    if isinstance(result, str):
        print('[!!!] ', result)
        return
    print('<==>' * 17)
    # 以上代码对换域名来说影响很小  ,只不过改变博客列表而已

    if args['list']:
        show_result_dict(result)
        return

    if args['pdf']:
        # print(list(result.values())[args['number_link']])
        if args['save']:
            save_many_pdf(list(result.values()), args)
            return
        if args['number_link'] < 0 or args['number_link'] > 9:
            print('文章编号不正确')
            raise IndexError
        save_to_pdf(list(result.values())[args['number_link']], args)
        return

    if args['cpp']:
        save_to_cpp(args, result)
        return

    show_code(args, result)


if __name__ == '__main__':
    run()
