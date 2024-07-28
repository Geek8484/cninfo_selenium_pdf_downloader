from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import pdfplumber
import pandas as pd
from pathlib import Path
import time
import re
from lxml import etree

class CninfoDownloader(object):
    """
    在巨潮网cninfo上市公司公告页面下载指定关键词的pdf文件
    输入：
    str：基础url,基本是用固定默认的
    str：查询关键词，例如公司名称等
    str：查询时间段，只设置了四个-->今日，本周，本月，本年
    输出：
    下载的pdf文件的path的list
    操作：
    将pdf文件下载到本地固定路径，根据需要调整
    目前是：'D:/python_explore_2024/crawler_2024/演示文件夹/demo/'
    """
    def __init__(self, keyword, period, url='http://www.cninfo.com.cn/new/fulltextSearch'):
        self.url = url
        self.keyword = keyword
        self.period = period
    
    def get_mainpage_data(self):
        """
        通过webdriver驱动edge浏览器获取主页面数据：
        dataid_list，文件在目标系统的里的编号
        time_list，文件上传的时间 
        filenname_list，文件名称
        url_list, 所有要下载的pdf的url地址的list，需要根据以上数据拼接得到。分析下载页面得到的规律。
        返回：
        filename_list, pdf_origin_url_list
        """
        # 设置webdriver驱动，进入主页面
        driver = webdriver.Edge()
        driver.get(self.url)

        # 设置等待时间和等待对象
        wait = WebDriverWait(driver, timeout=10)

        # 等待搜索框出现，用xpath定位搜索框，输入关键词
        try:
            el_searchbox = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="fulltext-search"]/div[1]/div[2]/div/input')))
            el_searchbox.send_keys(self.keyword)
        except:
            print('没有找到搜索框')

        # 等待搜索按钮出现，并且用xpath定位+点击
        try:
            el_searchbutton = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="fulltext-search"]/div[1]/button/span')))
            # 应为交互渲染的原因，按钮被遮挡了，需要JavaScript执行点击
            driver.execute_script("arguments[0].click();", el_searchbutton)
        except Exception as e:
            print('没有找到搜索按钮:')
            print(e)
        
        # 从输入时间要求，判断筛选的时间段,赋值相应的按钮xpath路径
        if self.period == '今日':
            xpath_string = '//*[@id="fulltext-search"]/div[1]/div[4]/div[1]/div[1]/label[1]/span[1]/span'
        elif self.period == '本周':
            xpath_string = '//*[@id="fulltext-search"]/div[1]/div[4]/div[1]/div[1]/label[3]/span[1]/span'
        elif self.period == '本月':
            xpath_string = '//*[@id="fulltext-search"]/div[1]/div[4]/div[1]/div[1]/label[4]/span[1]/span'
        elif self.period == '本年':
            xpath_string = '//*[@id="fulltext-search"]/div[1]/div[4]/div[1]/div[1]/label[5]/span[1]/span'
        else:
            xpath_string = ''

        # 等待时间段选择框出现，用xpath定位并且点击
        try:
            el_period = wait.until(EC.presence_of_element_located((By.XPATH, xpath_string)))
            driver.execute_script("arguments[0].click();", el_period)
        except:
            print('没有找到时间段选择框')

        # 等待三秒后，获取主页源代码，然后关闭webdriver
        # 这里为了简单，只获取第一个页面的信息，一般当日，本周，甚至本月的数据就够用了
        # 如果想要一年的所有的pdf，就需要继续驱动webdriver去点击下一页，把每一页的源码获取后拼接在一起
        time.sleep(3)
        page_source = driver.page_source
        driver.close()


        # 将源代码通过lxml的etree的HTML类实例化一个element对象，为xpath找数据做准备。也可以用bs4，re等放法。
        html = etree.HTML(page_source)
        # 获取主页面中每个跳转页码的dataid，为后面拼接做准备
        dataid_list = html.xpath('//tr[@class="el-table__row"]/td[2]//a/@data-id')
        # 获取主页面每个公告的发布时间，为后面拼接准备
        time_list = html.xpath('//tr[@class="el-table__row"]/td[3]//span/text()')
        # 获取的格式需要处理成xxxx-xx-xx格式，直接通过字符串截取
        time_list = [each.strip()[0:10] for each in time_list]

        # 刚开始是想从这个一步步找下载页面，最后到下载页面发现url拼凑的规则不需要中间这两个
        # # 找到源代码中要跳转页面不完整url，得到list
        # url_part_list = html.xpath('//tr[@class="el-table__row"]/td[2]//a/@href')
        # # 根据规则将不完成url拼接成第一个跳转页面，注意这个页面不是文件所在页面，需要在这个页面上继续跳转
        # url_jump_list = ['http://www.cninfo.com.cn' + url for url in url_part_list]
        
        # 根据上面的信息后下载页面的规则，拼接下载一面的url，全部放在pdf_origin_url_list中
        pdf_origin_url_list = []
        for i in range(len(time_list)):
            url = f'http://static.cninfo.com.cn/finalpage/{time_list[i]}/{dataid_list[i]}.PDF'
            pdf_origin_url_list.append(url)

        # 本来以为xpath定位能获取公司名称，分析后发现xpath定位到最后的时候，公司名称被拆分开了，不能一次性获取，还影响list长度。
        # 所以改为用正则表达式获取file名称列表
        p_name = '<span class="tileSecName-content">(.*?)</span>'
        pdf_file_name_list = re.findall(p_name, page_source)
        # 清洗元数据，去掉中间的其他字符
        pdf_file_name_list = [each.replace('<em>', '').replace('</em>', '') for each in pdf_file_name_list]

        # 返回所有文件名的list，所有文件下载地址的list
        return pdf_file_name_list, pdf_origin_url_list

    def download_pdf(self, pdf_file_name_list, pdf_origin_url_list):
        # 用requests下载pdf文件，保存在本地的固定路径下，返回所有pdf文件的本地路径的path对象list
        pdf_local_path_list = []
        for i in range(len(pdf_origin_url_list)):
            filename = 'D:/python_explore_2024/crawler_2024/演示文件夹/demo/'  + self.keyword + pdf_file_name_list[i] + '.pdf'
            pdf_local_path_list.append(Path(filename))
            with open(filename, 'wb') as f:
                f.write(requests.get(pdf_origin_url_list[i]).content)      
        return pdf_local_path_list

    # def show():

    #     for i in range(len(url_list)):
    #         print(str(i+1) + '.' + company_name[i] + ':' + filename_list[i] + '-' + time_list[i])
    #         print(url_list[i])
    def file_move(self):
        path = Path(r"C:\Users\FELIX\Downloads")
        pdf_path_list =[]
        for file in path.glob('*.PDF'):
            pdf_path_list.append(file)
            print(file.name)
        
        return pdf_path_list

if __name__ == '__main__':
    # 根据想要查询的关键词or公司名称，修改keyword赋值
    keyword = '美的集团'
    # period设置了四个可点击的时间段，根据需求修改period赋值
    period = '本年'
    # 实例化巨潮网下载器，初始化两个关键词
    cninfodownloader=CninfoDownloader(keyword=keyword, period=period)
    # 调用对象的get_mainpage_data方法，获取主页面数据，返回两个list
    pdf_file_name_list, pdf_origin_url_list = cninfodownloader.get_mainpage_data()
    # 调用对象的download_pdf方法，下载pdf文件，返回一个list
    # 这里默认的下载路径是'D:/python_explore_2024/crawler_2024/演示文件夹/demo/'，根据自己的需要修改源代码。
    pdf_local_path_list = cninfodownloader.download_pdf(pdf_file_name_list, pdf_origin_url_list)

    for each in pdf_local_path_list:
        print(each)

