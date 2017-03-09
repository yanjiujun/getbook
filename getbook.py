#! /usr/local/bin/python3
# @author yanjiujun@gmail.com
# @time 2017-2-14
#
# 网页是针对 http://www.biquge.com 的，只要在这个网站上给出目录的url就可以开始下载了。
#
# 改成多线程版本，比较麻烦的是不知道计算下一章的url。有些是有规律的，有些就不一定了。
# 对于有规律可循的，可以自动增加尾号等方式，预测下一章节，然后使用多线程来并发加载。
#
# 想错了，可以直接获取目录章节，这里面有所有章节的url，可以开启多线程处理。
#

import urllib.request
import urllib.error
import re
import sys
import multiprocessing
import time
import traceback
import socket
import os

def get_charset(content):
    '''
        获取网页编码字符集
        @param content 网页内容，bytes
        @return 返回字符集编码名字
    '''
    # 不太懂html，我google了一下如果没有设置charset默认是ISO-8859-1，但实际测试了几个网站发现会报错
    # utf8解码就正常
    # html4 <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
    # html5 <meta charset="utf-8">
    byte_search = str.encode('charset=')
    index = content.find(byte_search)
    if index == -1:
        return 'utf-8' #'ISO-8859-1'
    
    index = index + len(byte_search)
    if index >= len(content):
        return 'utf-8'

    if content[index] == str.encode('"')[0]:
        index = index + 1

    end = content.find(str.encode('"'),index)
    if end == -1:
        return 'utf-8' #'ISO-8859-1'

    return content[index:end].decode()

def load_url(url,timeout = None):
    '''
        加载url，成功返回网页内容，失败返回None
        @param url 要加载的url
        @return 返回网页内容，一般是gbk编码
    '''
    user_agent = 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
    headers = { 'User-Agent' : user_agent }
    req = urllib.request.Request(url,headers = headers)
    try:
        if timeout:
            resp = urllib.request.urlopen(req,timeout = timeout)
        else :
            resp = urllib.request.urlopen(req)
        
        if not resp:
            return None
    
        content = resp.read()
        if not content:
            return None
    
        content = content.decode(get_charset(content))

    except urllib.error.URLError as e:
        if hasattr(e, 'code'):
            print(e.code)
        if hasattr(e, 'reason'):
            print(e.reason)
        return None
    except urllib.error.HTTPError as e:
        print("Http错误 %s"%(e.reason))
        return None
    except socket.timeout:
        print("超时")
        return None
#    except :
#        print("未知的异常")
#        return None

    return content

def get_chapter(url):
    '''
        获取某一章，并存入文件中
        @param url 要加载的url。
        @param file 要存入的文件句柄
        @return 如果有下一页则返回下一页的URL，没有则返回None
    '''
    
    content = load_url(url,2)
    if not content:
        return None

    # 正文
    result = ""
    text = re.findall("&nbsp;&nbsp;&nbsp;&nbsp;(.*?)<br/><br/>",content)
    for t in text:
        result = result + t + "\n"

    return result

def get_directory(content):
    '''
        从网页内容中获取目录，如果有返回数组，里面是所有章节以及url
        @param content 网页内容
        @return 成功返回目录数组，失败返回None
    '''
    body = content.find("正文</dt>")
    if body == -1:
        print("没有找到正文")
        return None
    content = content[body:]

    # 正文之后的所有章节都需要的
    arr = re.findall('<dd> <a href="(.*?)">(.*?)</a></dd>',content)
    if not arr:
        print("没有目录")

    return arr

def get_title(content):
    '''
        从网页内容中获取书名
        @param content 文件内容
        @return 成功返回书名，失败返回None
    '''
    arr = re.findall('<meta property="og:title" content="(.*?)"/>',content)
    print(arr)
    if not arr:
        return None
    return arr[0]

def multiprocess_load(argv):
    '''
        开启多线程加载
    '''
    global web_site
    global qu
    
    num = 0
    while num < 3:
        content = get_chapter(web_site + argv[0])
        if content:
            print("加载成功",argv[1])
            break
        num = num + 3

    if not content:
        print("加载失败---------",argv[1])
        content = ""

    # 添加到队列中
    qu.put([argv[2],content],False)

def get_book(url,multi = True):
    '''
        爬取小说。
        @param url 目录的url
        @param multi 是否开启多线程加载
        @return 成功返回0，失败返回索引表示存了多少章
    '''
    content = load_url(url)
    if not content:
        print("无法获取url",url)
        return 1
    
    title = get_title(content)
    if not title:
        return 2

    arr = get_directory(content)
    if not arr:
        print("获取目录失败",url)
        return 4

    # 为了支持多进程，要给arr加一点参数
    num = 0
    chapters = []
    for item in arr:
        chapters.append([item[0],item[1],num])
        num = num + 1

    global qu
    qu = multiprocessing.Queue()
    global web_site
    qu = multiprocessing.Queue()
    index = url.find("/",8)
    if index == -1:
        return 0
    web_site = url[0:index]

    # windows系统上多进程无法工作，这里强制转成单线程
    if sys.platform == "win32" or sys.platform == "cygwin":
        multi = False

    if multi:
        # 所有要加载的章节全部存在arr中,这里开20个线程加载,如果网络不错，可以开200个。
        pool = multiprocessing.Pool(20)
        pool.map_async(multiprocess_load,chapters)
        pool.close()
    else :
        num = 0
        length = len(chapters)
        while True:
            multiprocess_load(chapters[num])
            num = num + 1
            if num == length:
                break;

    # 蛮奇怪的，如果任务太多会卡死在join上。如果不加在url就不会卡死，按照我的测试，任务数量超过11就卡死了
    # 而且还和线程数量无关，开8个线程和开20个线程都一样卡死。
    # 这里就不在依赖join，
    #pool.join()

    num = 0
    length = len(chapters)
    while True:
        item = qu.get()
        chapters[item[0]].append(item[1])
        num = num + 1
        print(num,length)
        if num == length:
            break

    # 按照章节顺序存储
    f = open(title + ".txt","wt")
    if not f:
        print("打开文件失败",file_name)
        return 3
    for item in chapters:
        f.write(item[1])
        f.write("\n")
        f.write(item[3])
        f.write("\n")
    f.close()

    return 0

def search_book(name):
    '''
        根据名字搜索，如果找到，则返回目录
        @param name 书名
        @return 成功返回目录url，失败返回None
    '''
    content = load_url('http://zhannei.baidu.com/cse/search?s=287293036948159515&q=' + urllib.parse.quote(name))
    if not content:
        return None
    
    arr = re.findall('<a cpos="title" href="(.*?)" title="(.*?)" class="result-game-item-title-link" target="_blank">',content)
    if not arr:
        return None

    return arr[0][0]

def main(str):
    '''
        主函数，如果str是书名则搜索该书籍，并下载第一个搜索结果，如果是url则直接下载。
    '''
    if str.find("http://") == -1 :
        url = search_book(str)
        if not url:
            print("没有找到书籍",str)
            return
    else :
        url = str

    if get_book(url):
        print("获取书籍失败！")
    else:
        print("获取书籍成功，就在当前目录下")

if __name__ == "__main__":
    main(sys.argv[1])
