import aiohttp
import asyncio
import time
import time

import argparse
import glob
import os
import shutil
import random
import re
import requests
import sys
from concurrent import futures

import pdfkit
import time
from retrying import retry
from pygments import highlight
from pygments.lexers import guess_lexer, get_lexer_by_name
from pygments.lexers import CppLexer
from pygments.formatters.terminal import TerminalFormatter
from pygments.util import ClassNotFound

from pyquery import PyQuery as pq
from requests.exceptions import ConnectionError
from requests.exceptions import SSLError
import numbers
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

scripFilePath = os.path.split(os.path.realpath(__file__))[0]
PDF_DIR = os.path.join(scripFilePath,'whoamiPDFdir')
CPP_DIR = os.path.join(scripFilePath,'whoamiCPPdir')


class Result(object):
    def __init__(self, host, args):
        self.args = args
        self.host = host
        self._search_url = 'https://www.bing.com/search?q=site:{0}%20{1}'

        self._USER_AGENTS = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:11.0) Gecko/20100101 Firefox/11.0',
                 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100 101 Firefox/22.0',
                 # 'Mozilla/5.0 (Windows NT 6.1; rv:11.0) Gecko/20100101 Firefox/11.0',
               ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_4) AppleWebKit/536.5 (KHTML, like Gecko) '
                'Chrome/19.0.1084.46 Safari/536.5'),
               ('Mozilla/5.0 (Windows; Windows NT 6.1) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.46'
                'Safari/536.5'), )
        self.data = self.whoami()

    def __call__(self, *args, **kwargs):
        return self.show_results()

    def __len__(self):
        return len(self.data)

    def whoami(self):
        self.args['query'] = ' '.join(self.args['query']).replace('?', '')
        try:
            return self.confirm_links() or 'Sorry, couldn\'t find any help with that topic\n'
        except (ConnectionError, SSLError):
            return 'Failed to establish network connection\n'

    def confirm_links(self):
        dic = self._get_dict(self.args['query'])
        if not dic:
            return False
        '''先不检验。。测试多个域名。。'''
        return dic
        # def _is_article(link):
        #     return re.search('article/details/\d+', link)
        # # question_links = [link for link in links if _is_article(link)]
        # # https://blog.csdn.net/u013177568/article/details/62432761
        # confirm_dict = {k: v for k, v in dic.items() if _is_article(v)}
        # return confirm_dict

    def _get_dict(self, query):
        search_url = self._search_url.format(self.host, url_quote(query))
        # search_url :   site:blog.csdn.net 1173 HDU
        result = self._get_result(search_url)
        html = pq(result)
        # return the anser_list
        return self._extract_links(html, 'bing')

    @retry(stop_max_attempt_number=3)
    def _get_result(self, url):
        try:
            return requests.get(url, headers={'User-Agent': random.choice(self._USER_AGENTS)}, ).text
            # verify = VERIFY_SSL_CERTIFICATE).text

        except requests.exceptions.SSLError as e:
            print('[ERROR] Encountered an SSL Error.\n')
            print('[*]retrying again automatically ')
            raise e

    def _extract_links(self, html, search_engine):
        if search_engine == 'bing':
            return self._extract_dict_from_bing(html)
        return None

    @staticmethod
    def _extract_dict_from_bing(html):
        html.remove_namespaces()
        dic = {}
        for a in html('.b_algo')('h2')('a'):
            # name ='[*{0}*] {1}'.format(str(num),a.text)
            name = a.text
            link = a.attrib['href']
            dic[name] = str(link)
            # num+=1
        return dic

    def show_results(self):
        if isinstance(self.data,str):
            print('[!!] ',self.data)
            return
        num = 0
        for k, v in self.data.items():
            print('[*{}*] '.format(str(num)), end='')
            print(k, end=' [*link*] ')
            print(v)
            num += 1


class Blog(Result):
    def __init__(self, host, args):
        super().__init__(host, args)
        self.links = list(self.data.values())

    def show_code(self):
        url = list(self.data.values())[self.args['print']]
        main_page = self._parse_url(url)
        s = self._get_code(main_page, self.args) or 'sorry,this article has no code...'
        print(s)

    def save_to_pdf(self, url):
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

        main_page = self._parse_url(url)
        title = main_page('h1').eq(0).text()
        title = re.sub('[<>\?\\\/:\*\s\[\]\(\)\-]', '.', title)
        html = html_template.format(title='Oliver loves Annabelle forever~', content=main_page.html())
        if not os.path.exists(PDF_DIR):
            os.makedirs(PDF_DIR)
        filePath = os.path.join(PDF_DIR, title + '.pdf')

        if self._test_is_open_if_exists(filePath):
            return
        try:
            print('[*] save to ', filePath)
            self._save_to_pdf(html,filePath)
            print('[*] successfully ')
        except:
            print('[!!]要保存的网页可能有网页冲突')
            print('[注]保存html等语言的文档冲突的几率较大')

            print('[!!]save failed')
            print('[!!]如果事因为图片路径造成的保存失败，文字和代码部分则会正常生成pdf，')
        try:
            # 系统级命令好像try不到。。。
            self.open_after_save(filePath)
        except:
            print('[!!]文件未打开，可能保存时发生IO错误。。')
            print('[!!]请重新生成pdf，或者，该网页的结构不符合生成pdf的标准')
            print('[~~]请见谅。。。。')

    @staticmethod
    def _save_to_pdf(html, filepath):
        wkhtmltopdf_path = scripFilePath + '/wkhtmltox/bin/wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        pdfkit.from_string(html, filepath, configuration=config)

    def open_after_save(self, pdf_path):
        if not self.args['open_pdf']:
            return
        try:
            if len(self.args['save']):
                return False
        except TypeError as e:
            pass
        # if args['pdf'] and PDFpath.split('.')[-1]!='pdf':
        #     PDFpath += '.pdf'
        
        os.popen(pdf_path)

    def _test_is_open_if_exists(self, file_path):
        try:
            if len(self.args['save']):
                return False
        except TypeError as e:
            pass

        if self.args['open_pdf']:
            if os.path.exists(file_path):
                print('文件已经存在，直接打开')
                os.popen(file_path)
                return True
        else:
            return False

    def _parse_url(self, url):
        '''
        :param url:   网页url
        :return: 返回网页的主要区域的pyquery
        '''

        page = self._get_result(url)
        html = pq(page)
        # the main part of the article
        return html('.blog-content-box')

    def _get_code(self, main_page, args):
        '''
        :param   main_page:main_page=_parse_url(url)
        :param   args: args
        :return: str
        '''
        html = main_page('article')('pre')('code') or main_page('article')('pre')
        if not html:
            return None
        ans = []
        ans_split = '\n' + '<==>' * 17 + '\n'
        if args['all_code']:
            for node in html:
                node = pq(node)
                s = node.html()
                #     s=re.sub('</?[^>]+>','',s)
                s = re.sub('<((span)|(code)|(/span)|(/code)){1}.*?>', '', s)
                s = s.replace('&gt;', '>').replace('&lt;', '<')
                ans.append(self._add_color(s, args))
        else:
            node = pq(html[-1])
            s = node.html()
            s = re.sub('<((span)|(code)|(/span)|(/code)){1}.*?>', '', s)
            s = s.replace('&gt;', '>').replace('&lt;', '<')
            ans.append(self._add_color(s, args))
        return ans_split.join(ans)

    @staticmethod
    def _add_color(code, args):
        if not args['color']:
            return code
        lexer = None
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            return code
        return highlight(code, CppLexer(), TerminalFormatter(bg='dark'))

    def save_to_cpp(self):
        ans_split = '\n' + '<==>' * 17 + '\n'
        url = self.links[self.args['number_link']]
        main_page = self._parse_url(url)
        title = main_page('h1').eq(0).text()
        title = re.sub('[<>\?\\\/:\*\s]', '.', title)
        s = self._get_code(main_page, self.args)
        if not s:
            print('sorry , this article has no code...')
            print('please try another...')
            return
        if not os.path.exists(CPP_DIR):
            os.makedirs(CPP_DIR)
        filePath = os.path.join(CPP_DIR, title + '.cpp')

        if self._test_is_open_if_exists(filePath):
            return
        code = s.split(ans_split)[-1]
        with open(filePath, 'w')as f:
            f.write(code)
            print('[*]save successfully...')
        try:
            self.open_after_save(filePath)
        except:
            print('[!!]文件未打开，可能保存时发生IO错误。。')
            print('[!!]open failed')