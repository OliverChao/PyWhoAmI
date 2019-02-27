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
from pyquery import PyQuery as pq
import pdfkit
import time
import concurrent.futures

scripFilePath = os.path.split(os.path.realpath(__file__))[0]
PDF_DIR = os.path.join(scripFilePath,'whoamiPDFdir')
html_template = u"""
    <!DOCTYPE html>

    <html>
        <head>
            <meta charset="utf-8" />
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
        </head>
        <body>
            <!-- <center><h1></h1></center> -->
            {content}
        </body>
    </html>
    """

class HtmlResult(object):
    def __init__(self, links):
        self.links = links
        self.result = []
        self.semaphore = asyncio.Semaphore(value=21)
        self.eventloop()
        

    @staticmethod
    def _parse_url(page):
        html = pq(page)
        # the main part of the article
        return html('.blog-content-box')

    async def _get_result(self, url):
        async with aiohttp.request('GET', url) as r:
            page = await r.read()
        # response = await aiohttp.request('GET', url)
        # page = await response.read()
        return self._parse_url(page)
        pass

    async def save_one(self, url):
        with await self.semaphore:
            main_page = await self._get_result(url)
            self.result.append(main_page)
        pass

    def eventloop(self):
        start = time.time()
        loop = asyncio.get_event_loop()
        tasks = [self.save_one(url) for url in self.links]
        loop.run_until_complete(asyncio.gather(*tasks))
        # print(time.time()-start)
        # self.cost_time = time.time() - start

    def __len__(self):
        return len(self.result)

    def __iter__(self):
        return iter(self.result)


class SavePDF(HtmlResult):
    def __init__(self, links):
        super(SavePDF, self).__init__(links)
        self._time = 'no save pdfs, no timing'

    @property
    def time(self):
        return 'saving pdfs costing time {}...'.format(self._time)

    @staticmethod
    def _save_one(page):
        title = page('h1').eq(0).text()
        title = re.sub('[<>\?\\\/:\*\s\[\]\(\)\-]', '.', title)
        config = pdfkit.configuration(wkhtmltopdf=r'C:\Users\Oliver\Desktop\wkhtmltox\bin\wkhtmltopdf.exe')
        filePath = os.path.join(PDF_DIR, title+'.pdf')
        # filePath='C:/Users/Oliver/Desktop/asyn_test_script/whoamiPDFdir/'+title+'.pdf'
        # print('test'*20)
        pdfkit.from_string(html_template.format(content=page.html()),filePath,
                           configuration=config)

    def save(self):
        start = time.time()
        workors = min(len(self.result), 21)
        with concurrent.futures.ThreadPoolExecutor(workors) as executor:
            executor.map(self._save_one, self.result)
        self._time = time.time() - start
