import random
import time
import requests
from loguru import logger
from base64 import b64decode

# PNG文件头的base64编码
prefix = b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=".encode())

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Edge/120.0.0.0",
]

def upload1(filename, fdata):
    file = prefix + fdata  # 添加PNG文件头
    url = "https://pic.2xb.cn/uppic.php?type=qq"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    data = {"file": (f"{int(time.time())}.png", file, "image/png")}
    for i in range(3):
        try:
            with requests.post(url=url, headers=headers, files=data, verify=False) as resp:
                data = resp.json()
            return data["url"]
        except Exception as e:
            logger.warning(f"上传TS请求出错 {e}")
            time.sleep(2)

    raise Exception(f"{filename} TS 上传失败")

def upload2(filename, fdata):
    url = "https://api.vviptuangou.com/api/upload"
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
        'Sign': 'e346dedcb06bace9cd7ccc6688dd7ca1',
        'Token': 'b3bc3a220db6317d4a08284c6119d136',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    }
    file = prefix + fdata  # size < 50MB
    data = {"file": (f"{int(time.time())}.png", file, "image/png")}
    for i in range(3):
        try:
            with requests.post(url=url, headers=headers, files=data, verify=False) as resp:
                data = resp.json()
            return f"https://assets.vviptuangou.com/{data['imgurl']}"
        except Exception as e:
            logger.warning(f"上传TS请求出错 {e}")
            time.sleep(2)
    raise Exception(f"{filename} TS 上传失败")

def upload3(filename, fdata):
    url = "https://api.da8m.cn/api/upload"
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
        'Sign': 'e346dedcb06bace9cd7ccc6688dd7ca1',
        'Token': '4ca04a3ff8ca3b8f0f8cfa01899ddf8e',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    }
    file = prefix + fdata  # size < 50MB
    data = {"file": (f"{int(time.time())}.png", file, "image/png")}
    for i in range(3):
        try:
            with requests.post(url=url, headers=headers, files=data, verify=False) as resp:
                data = resp.json()
            return f"https://assets.da8m.cn/{data['imgurl']}"
        except Exception as e:
            logger.warning(f"上传TS请求出错 {e}")
            time.sleep(2)
    raise Exception(f"{filename} TS 上传失败")

    # 假设 auth_token 是一个固定的字符串，比如 "your_auth_token"
def upload4(filename, fdata, auth_token="token"):
    url = "https://i.111666.best/image"
    headers = {
        'Auth-Token': auth_token,  # 使用默认的 Auth-Token
    }
    file = prefix + fdata  # 加上 PNG 文件头
    data = {"image": (f"{int(time.time())}.png", file, "image/png")}
    
    for i in range(3):
        try:
            with requests.post(url=url, headers=headers, files=data, verify=False) as resp:
                if resp.status_code == 200:
                    data = resp.json()
                    return f"https://i.111666.best/image/{data['src']}"
                else:
                    logger.warning(f"上传请求失败，状态码: {resp.status_code}")
        except Exception as e:
            logger.warning(f"上传请求出错 {e}")
            time.sleep(2)

    raise Exception(f"{filename} 上传失败")


# 导出所有上传接口
UPLOAD_APIS = [upload1, upload2, upload3, upload4]
