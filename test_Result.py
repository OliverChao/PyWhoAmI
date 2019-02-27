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



def show_code(args, result):
    url = list(result.values())[args['print']]
    main_page = _parse_url(url)
    s = _get_code(main_page, args) or 'sorry,this article has no code...'
    print(s)


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
    test asynvio 
    '''
    start = time.time()
    links = [s[i] for i in args['save']]
    # print(links)
    a = SavePDF(links)
    # print(a.result)
    a.save()
    print('time ',time.time()-start)


from Blog import *  
from aiohttpSave import HtmlResult,SavePDF
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
    URL = {'csdn': 'blog.csdn.net',
       'cnblogs': 'cnblogs.com'}
    test = Blog(URL['csdn'],args)
    print('[time  ]',time.time()-start)
    test.show_results()
    # test.show_code()
    test.save_to_cpp()
    # print(test.data.values())
    # print(len(test))


    if args['pdf']:
        # print(list(result.values())[args['number_link']])
        if args['save']:
            save_many_pdf(test.links, args)
            return
        if args['number_link'] < 0 or args['number_link'] > len(test)-1:
            print('文章编号不正确')
            raise IndexError

        try: 
            link = test.links[args['number_link']]
        except IndexError :
            raise IndexError('文章编号不正确')

        test.save_to_pdf(link)
        return



if __name__ == '__main__':
    run()
