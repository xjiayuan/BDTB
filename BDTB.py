# -*- coding:utf-8 -*-

import urllib2
import re
import MySQLdb
import time

#处理页面标签类
class TOOL:
    #去除img标签
    remove_img = re.compile('<img.*?>')
    #去除超链接标签
    remove_addr = re.compile('<a.*?>')
    #把换行符换成\n
    replace_line = re.compile('<tr>|<div>|</div>|</p>')
    #将<td>替换成\t
    replace_td = re.compile('<td>')
    #把段落开头换为\n和俩空格
    replace_para = re.compile('<p.*?>')
    #将换行符替换成\n
    replace_br = re.compile('<br><br>|<br>')
    #将其余标签剔除
    remove_extra_tag = re.compile('<.*?>')

    def replace(self, x):
        x = re.sub(self.remove_img, "", x)
        x = re.sub(self.remove_addr, "", x)
        x = re.sub(self.replace_line, "\n", x)
        x = re.sub(self.replace_td, "\t", x)
        x = re.sub(self.replace_para, "\n", x)
        x = re.sub(self.replace_br, "\n", x)
        x = re.sub(self.remove_extra_tag, "", x)
        return x.strip()


class BDTB:
    #初始化
    def __init__(self, base_url, see_lz, floor_tag):
        self.base_url = base_url
        #是否只看楼主
        self.see_lz = '?see_lz=' + str(see_lz)
        #HTML标签剔除工具类对象
        self.tool = TOOL()
        #全局file变量，文件写入操作对象
        self.file = None
        #楼层标号
        self.floor = 1
        #默认标题
        self.default_title = u'百度贴吧'
        #是否写入楼分隔符的标记
        self.floor_tag = floor_tag
        self.mysql = MYSQL()

    #获取该页帖子代码
    def get_page(self, page_num):
        try:
            url = self.base_url + self.see_lz + '&pn=' + str(page_num)
            request = urllib2.Request(url)
            response = urllib2.urlopen(request)
            #返回UTF-8格式编码的内容
            page_code = response.read().decode('utf-8')
            return page_code
        except urllib2.URLError as e:
            if hasattr(e, "reason"):
                print "连接百度贴吧失败，错误原因", e.reason, e.code
                return None

    #获取帖子标题
    def get_title(self, page):
        pattern = re.compile('core_title_txt.*?>(.*?)</h3>', re.S)
        result = re.search(pattern, page)
        if result:
            return result.group(1).strip()
        else:
            return None

    #获取帖子总页数
    def get_page_num(self, page):
        pattern = re.compile('class="red">(.*?)</span>', re.S)
        result = re.search(pattern, page)
        if result:
            return result.group(1).strip()
        else:
            return None

    #获取每层楼的内容
    def get_content(self, page):
        pattern = re.compile('id="post_content.*?>(.*?)</div>', re.S)
        items = re.findall(pattern, page)
        contents = []
        for item in items:
            content = '\n' + self.tool.replace(item) + '\n'
            #删掉空楼层
            if content != '\n\n':
            #写入文件时需要将unicode转换成str
                contents.append(content.encode('utf-8'))
        return contents

    #设置文件名
    def set_file_title(self, title):
        #如果标题不是None，即成功获取到标题
        if title:
            self.file = open(title + '.txt', 'w+')
        else:
            self.file = open(self.default_title + '.txt', 'w+')

    def write_data(self, contents):
        #写入每一楼的信息
        for item in contents:
            if self.floor_tag == '1':
                #楼之间的分隔符
                floor_line = '\n' + str(self.floor) + '楼--------------------\n'
                self.file.write(floor_line)
            #self.file.write(item)
            #保存到数据库中
            self.mysql.insert_data('bdtb', self.floor, item)
            self.floor += 1

    def start(self):
        index_page = self.get_page(1)
        page_num = self.get_page_num(index_page)
        title = self.get_title(index_page)
        self.set_file_title(title)
        if page_num == None:
            print "URL已失效，请重试"
            return
        try:
            print "该帖子共有" + str(page_num) + '页'
            for i in range(1, int(page_num)+1):
                page = self.get_page(i)
                contents = self.get_content(page)
                self.write_data(contents)
        except IOError as e:
            print "写入异常，原因是" + e.message
        finally:
            print "写入完毕"


#数据库操作
#创建 MySql 的表时，表名和字段名外面的符号 ` 不是单引号，而是英文输入法状态下的反单引号
#反引号是为了区分 MySql 关键字与普通字符而引入的符号，一般的，表名与字段名都使用反引号。
class MYSQL:

    def get_time(self):
        return time.strftime('[%Y-%m-%d %H:%M:%S]', time.localtime())
        
    def __init__(self):
        try:
            #指定客户端的编码是utf8
            self.db = MySQLdb.connect('localhost', 'root', 'wjy9649', 'spider', charset='utf8')
            #获取操作游标
            self.cur = self.db.cursor()
        except MySQLdb.Error as e:
            print self.get_time(), "连接数据库失败，原因%d: %s" % (e.args[0], e.args[1])
            
    def insert_data(self, table, num, content):
        try:
            sql = "INSERT INTO %s VALUES (%d, %s)" % (table, num, '"'+content+'"')
            try:
                result = self.cur.execute(sql)
                insert_id = self.db.insert_id()
                self.db.commit()
                print "%s   第%d层内容已保存" % (self.get_time(), num)
            except MySQLdb.Error as e:
                #发生错误时回滚
                self.db.rollback()
                #主键唯一，无法插入
                if "key 'PRIMARY'" in e.args[1]:
                    print self.get_time(), "数据已存在，未插入"
                else:
                    print self.get_time(), "插入数据失败， 原因%d: %s" % (e.args[0],e.args[1])
        except MySQLdb.Error as e:
            print self.get_time(), "数据库错误，原因%d： %s" % (e.args[0], e.args[1])
            
            
if __name__ == '__main__':
    print "请输入帖子代号"
    base_url = "https://tieba.baidu.com/p/" + str(raw_input())
    see_lz = raw_input("是否只看楼主，是输入1，否输入0\n")
    floor_tag = raw_input("是否写入楼层信息，是输入1，否输入0\n")
    bdtb = BDTB(base_url, see_lz, floor_tag)
    bdtb.start()
