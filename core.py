import os
import re
import json
import time
import shutil
import requests
import threading
import subprocess
import math
from loguru import logger
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import random

from upload_apis import UPLOAD_APIS, prefix

requests.packages.urllib3.disable_warnings()

def test_upload_interface(upload_func):
    try:
        with open("1.png", "rb") as file:
            fdata = file.read()
        url = upload_func("1.png", fdata)
        logger.info(f"{upload_func.__name__} 接口可用")
        return True
    except Exception as e:
        logger.warning(f"{upload_func.__name__} 接口不可用: {e}")
        return False

def request_get(url, headers, session=requests):
    for i in range(3):
        try:
            with session.get(url=url, headers=headers) as resp:
                resp.raise_for_status()
                content = resp.content
                return content
        except Exception as e:
            logger.warning(f"Get出错 {url} 报错内容 {e}")
            time.sleep(2)

    raise Exception(f"{url} 请求失败")

class Down:
    def __init__(self, filename=None, m3u8link=None):
        self.session = requests.session()
        self.vinfo = {
            "filename": filename,
            "m3u8link": m3u8link,
            "key": b"",
            "iv": b"",
            "ts": [],
        }
        self.upload_s3 = None
        self.failed_uploads = []
        self.lock = threading.Lock()

    def load_m3u8(self, url=None):
        m3u8link = url or self.vinfo["m3u8link"]
        self.vinfo["m3u8link"] = m3u8link
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "Accept-Encoding": "gzip, deflate, br",
        }
        logger.info(f'M3U8 Downloading {m3u8link}')
        content = request_get(m3u8link, headers, self.session).decode()
        
        # 检查是否需要重定向
        if '#EXT-X-STREAM-INF' in content:
            logger.info('检测到多码率m3u8，正在解析真实地址...')
            # 解析所有可码率
            available_streams = []
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF:'):
                    stream_info = line
                    stream_url = lines[i + 1] if i + 1 < len(lines) else None
                    if stream_url and not stream_url.startswith('#'):
                        # 解析码率信息
                        bandwidth = re.search(r'BANDWIDTH=(\d+)', stream_info)
                        resolution = re.search(r'RESOLUTION=(\d+x\d+)', stream_info)
                        bandwidth = int(bandwidth.group(1)) if bandwidth else 0
                        resolution = resolution.group(1) if resolution else 'unknown'
                        available_streams.append({
                            'bandwidth': bandwidth,
                            'resolution': resolution,
                            'url': stream_url.strip()
                        })
            
            if not available_streams:
                raise Exception('未找到可用的媒体流')
            
            # 选择码率最高的流
            selected_stream = max(available_streams, key=lambda x: x['bandwidth'])
            logger.info(f'选择码率: {selected_stream["bandwidth"]}, 分辨率: {selected_stream["resolution"]}')
            
            # 构建新的m3u8地址
            if selected_stream['url'].startswith('http'):
                real_m3u8_url = selected_stream['url']
            else:
                # 使用urljoin处理相对路径
                real_m3u8_url = urljoin(m3u8link, selected_stream['url'])
            
            logger.info(f'重定向到真实m3u8: {real_m3u8_url}')
            # 递归调用加载真实的m3u8
            return self.load_m3u8(real_m3u8_url)
        
        # 处理实际的m3u8内容
        if not self.vinfo["filename"]:
            self.vinfo["filename"] = os.path.basename(m3u8link).split("?")[0].split(".m3u8")[0]
        _content = content.split("\n").__iter__()
        while True:
            try:
                _ = _content.__next__()
                if "#EXTINF" in _:
                    while True:
                        _2 = _content.__next__()
                        if not _2 or _2.startswith("#"):
                            continue
                        else:
                            self.vinfo["ts"].append(urljoin(m3u8link, _2))
                            break
            except StopIteration:
                break
        del _content
        
        # 处理加密相关信息
        keyurl = (re.findall(r"URI=\"(.*)\"", content) or [''])[0]
        if keyurl:
            iv = bytes.fromhex((re.findall(r"IV=(.*)", content) or ['12'])[0][2:])
            self.vinfo["iv"] = iv or b'\x00' * 16
            logger.info(f'IV {iv}')
            keyurl = keyurl if keyurl.startswith("http") else urljoin(m3u8link, keyurl)
            logger.info(f'KEY Downloading {keyurl}')
            self.vinfo["key"] = request_get(keyurl, dict(headers, **{"Host": keyurl.split("/")[2]}), self.session)
        
        # 保存文件
        if not os.path.exists(self.vinfo['filename']):
            os.makedirs(self.vinfo['filename'], exist_ok=True)
        logger.info("保存raw.m3u8到本地")
        with open(f'{self.vinfo["filename"]}/raw.m3u8', "w") as fp:
            fp.write(content)
        logger.info("保存meta.json到本地")
        with open(f'{self.vinfo["filename"]}/meta.json', "w") as fp:
            fp.write(json.dumps(dict(self.vinfo, **{
                "key": self.vinfo["key"].hex(),
                "iv": self.vinfo["iv"].hex()
            })))

    def load_ts(self, index, handle, local_files=None):
        max_retries = 3
        for retry in range(max_retries):
            try:
                if local_files:
                    ts_file = local_files[int(index)]
                    with open(ts_file, "rb") as file:
                        content = file.read()
                else:
                    ts_url = self.vinfo["ts"][int(index)]
                    if not ts_url.startswith('http'):
                        ts_url = urljoin(self.vinfo["m3u8link"], ts_url)
                    headers = {
                        "Host": ts_url.split("/")[2],
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
                    }
                    logger.info(f'TS{index} Downloading')
                    content = request_get(ts_url, headers, self.session)

                filesize = len(content)
                s3_ts_url = random.choice(self.upload_s3)(f"{index}.ts", content)
                with self.lock:
                    handle.write(f"{index}@@{filesize}@@{s3_ts_url}\n")
                logger.info(f'TS{index} Saving to URL')
                return index
            except Exception as e:
                if retry < max_retries - 1:
                    logger.warning(f"TS{index} 上传失败，将在 {(retry+1)*2} 秒后重试: {e}")
                    time.sleep((retry+1)*2)
                else:
                    raise

    def retry_failed_uploads(self, handle):
        if not self.failed_uploads:
            return
        
        logger.info(f"开始重试 {len(self.failed_uploads)} 个失败的上传")
        retry_list = self.failed_uploads.copy()
        self.failed_uploads.clear()
        
        for index, decrypted_ts, filesize in retry_list:
            max_retries = 3
            upload_func = self.upload_s3[0]
            
            for retry in range(max_retries):
                try:
                    s3_ts_url = upload_func(f"{index}.ts", decrypted_ts)
                    with self.lock:
                        handle.write(f"{index}@@{filesize}@@{s3_ts_url}\n")
                        handle.flush()
                    logger.info(f'TS{index} 重试上传成功')
                    break
                except Exception as e:
                    retry_sleep = 5 * (retry + 1)
                    if retry < max_retries - 1:
                        logger.warning(f'TS{index} 重试上传失败，{retry_sleep}秒后重试 ({retry + 1}/{max_retries}): {str(e)}')
                        time.sleep(retry_sleep)
                    else:
                        logger.error(f'TS{index} 重试上传失败: {str(e)}')
                        with self.lock:
                            self.failed_uploads.append((index, decrypted_ts, filesize))

    def verify_m3u8_content(self, content):
        """验证m3u8文件内容是否符合格式要求"""
        lines = content.split('\n')
        if not lines[0].strip() == '#EXTM3U':
            logger.error("M3U8文件必须以#EXTM3U开头")
            return False
        if not lines[1].strip() == '#EXT-X-VERSION:4':
            logger.error("M3U8文件版本必须为4")
            return False
        return True

    def save_m3u8(self):
        try:
            # 读取原始m3u8文件获取头部信息
            with open(f'{self.vinfo["filename"]}/raw.m3u8', "r") as fp:
                m3u8_text = fp.read()
            
            # 提取所有头部标签（以#开头的行，直到第一个非头部内容）
            headers = []
            for line in m3u8_text.split('\n'):
                if line.startswith('#') and not line.startswith('#EXTINF'):
                    headers.append(line)
                elif not line.startswith('#'):
                    break
            
            # 读取上传后的ts文件信息并排序
            try:
                with open(f'{self.vinfo["filename"]}/temp', "r") as fp:
                    content = fp.read().strip("\n")
                    if content:  # 如果temp文件不为空
                        data = []
                        for line in content.split("\n"):
                            index, filesize, url = line.split("@@")
                            data.append((int(index), filesize, url))
                        data.sort(key=lambda x: x[0])
                    else:
                        data = []  # temp文件为空时使用空列表
            except FileNotFoundError:
                logger.warning("temp文件不存在，将只保存m3u8头部信息")
                data = []

            # 提取EXTINF信息
            extinf = re.findall(r"#EXTINF:.*,", m3u8_text)

            # 构建新的m3u8内容，使用原始头部
            m3u8_list = headers.copy()

            # 按照排序后的顺序添加分片信息
            if data:  # 如果有上传的文件信息
                for i, (_, _, url) in enumerate(data):
                    if i < len(extinf):  # 确保不会超出extinf的范围
                        m3u8_list.append(extinf[i])
                        m3u8_list.append(url)
            m3u8_list.append("#EXT-X-ENDLIST")
            
            # 写入新的m3u8文件
            content = "\n".join(m3u8_list)
            with open(f'{self.vinfo["filename"]}/new_raw.m3u8', "w", encoding='utf-8') as fp:
                fp.write(content)
            
        except Exception as e:
            logger.error(f"保存m3u8文件时出错: {e}")
            raise

def local_slice_and_upload(args=None):
    input_folder = "input"
    output_folder = "output"
    
    # 清空output文件夹
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder)
    
    if not os.path.exists(input_folder):
        logger.error(f"输入文件夹 {input_folder} 不存在")
        return

    for filename in os.listdir(input_folder):
        if filename.endswith(".mp4"):
            input_file = os.path.join(input_folder, filename)
            output_file = os.path.join(output_folder, "playlist.m3u8")
            segment_file = os.path.join(output_folder, "%05d.ts")
            
            # 本地切片模式，使用完整的转码参数
            cmd = [
                'ffmpeg',
                '-re',
                '-i', input_file,
                '-codec:v', 'libx264',
                '-codec:a', 'aac',
                '-s', '1280x720',
                '-map', '0',
                '-f', 'hls',
                '-hls_time', '5',
                '-hls_list_size', '0',
                '-hls_segment_filename', segment_file,
                output_file
            ]
            
            try:
                subprocess.run(cmd, check=True)
                logger.info(f"成功切割视频: {filename}")
            except subprocess.CalledProcessError as e:
                logger.error(f"切割视频失败 {filename}: {e}")
                continue

    # 获取所有ts文件并排序
    local_files = [os.path.join(output_folder, f) for f in os.listdir(output_folder) if f.endswith(".ts")]
    local_files.sort()

    # 读取原始m3u8文件
    with open(os.path.join(output_folder, "playlist.m3u8"), 'r') as f:
        original_m3u8 = f.read()
    
    # 复制原始m3u8为raw.m3u8
    with open(f'{output_folder}/raw.m3u8', 'w', encoding='utf-8') as f:
        f.write(original_m3u8)

    down = Down(filename=output_folder)
    down.upload_s3 = UPLOAD_APIS

    if args and args.upload_api:
        down.upload_s3 = [UPLOAD_APIS[args.upload_api - 1]]
    elif args and args.no_verify:
        logger.info("可用接口: " + ", ".join([f"{i+1}. {func.__name__}" for i, func in enumerate(UPLOAD_APIS)]))
        selected_index = int(input("请选择一个接口 (序号): ").strip()) - 1
        if selected_index < 0 or selected_index >= len(UPLOAD_APIS):
            logger.error("选择的接口序号无效")
            return
        down.upload_s3 = [UPLOAD_APIS[selected_index]]
    else:
        available_uploads = []
        for upload_func in UPLOAD_APIS:
            if test_upload_interface(upload_func):
                available_uploads.append(upload_func)

        if not available_uploads:
            logger.error("所有接口都不可用")
            return

        logger.info("可用接口: " + ", ".join([f"{i+1}. {func.__name__}" for i, func in enumerate(available_uploads)]))
        selected_index = int(input("请选择一个可用接口 (序号): ").strip()) - 1
        if selected_index < 0 or selected_index >= len(available_uploads):
            logger.error("选择的接口序号无效")
            return
        down.upload_s3 = [available_uploads[selected_index]]

    workers = 10
    with open(f'{output_folder}/temp', "a", encoding='utf-8') as handle:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(down.load_ts, f"{index:04}", handle, local_files): index 
                      for index in range(len(local_files))}
            for future in futures:
                try:
                    future.result()
                except Exception:
                    continue

        if down.failed_uploads:
            logger.info("等待30秒后开始重试失败的上传...")
            time.sleep(30)
            down.retry_failed_uploads(handle)
        
        while down.failed_uploads:
            failed_indexes = [str(item[0]) for item in down.failed_uploads]
            logger.error(f"以下分片上传失败: {', '.join(failed_indexes)}")
            retry = input("是否要重试失败的上传? (Y/N): ").strip().upper()
            if retry == 'Y':
                logger.info("等待10秒后开始重试...")
                time.sleep(10)
                down.retry_failed_uploads(handle)
            else:
                break

    logger.info(f"{output_folder} 载完成")
    down.save_m3u8()
    print("任务完成")

def remote_upload(args):
    # 修改输出文件夹名称为Urloutput
    base_dir = "Urloutput"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    if args.new_upload and os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        os.makedirs(base_dir)
        
    if os.path.exists(os.path.join(base_dir, "temp")) and not args.new_upload:
        # 如果是续传，使用已有的文件
        down = Down(filename=base_dir)
        down.vinfo["m3u8link"] = args.m3u8_url
        with open(os.path.join(base_dir, "meta.json"), "r") as f:
            meta = json.load(f)
            down.vinfo.update(meta)
            down.vinfo["key"] = bytes.fromhex(meta["key"]) if meta["key"] else b""
            down.vinfo["iv"] = bytes.fromhex(meta["iv"]) if meta["iv"] else b""
    else:
        # 如果是新下载
        down = Down(filename=base_dir)

    down.upload_s3 = UPLOAD_APIS
    if args.upload_api:
        down.upload_s3 = [UPLOAD_APIS[args.upload_api - 1]]
    elif not args.no_verify:
        available_uploads = []
        for upload_func in UPLOAD_APIS:
            if test_upload_interface(upload_func):
                available_uploads.append(upload_func)
        if not available_uploads:
            logger.error("所有接口都不可用")
            return
        logger.info("可用接口: " + ", ".join([f"{i+1}. {func.__name__}" for i, func in enumerate(available_uploads)]))
        selected_index = int(input("请选择一个可用接口 (序号): ").strip()) - 1
        if selected_index < 0 or selected_index >= len(available_uploads):
            logger.error("选择的接口序号无效")
            return
        down.upload_s3 = [available_uploads[selected_index]]
    else:
        logger.info("可用接口: " + ", ".join([f"{i+1}. {func.__name__}" for i, func in enumerate(UPLOAD_APIS)]))
        selected_index = int(input("请选择一个接口 (序号): ").strip()) - 1
        if selected_index < 0 or selected_index >= len(UPLOAD_APIS):
            logger.error("选择的接口序号无效")
            return
        down.upload_s3 = [UPLOAD_APIS[selected_index]]

    # 直接加载m3u8，不需要先用ffmpeg下载
    if not down.vinfo["ts"]:
        # 强制设置filename为base_dir
        down.vinfo["filename"] = base_dir
        down.load_m3u8(args.m3u8_url)
        # 确保load_m3u8后filename仍然是base_dir
        down.vinfo["filename"] = base_dir

    if os.path.exists(os.path.join(base_dir, "temp")):
        with open(os.path.join(base_dir, "temp"), "r") as fp:
            uploaded_files = fp.read().strip("\n").split("\n")
            uploaded_indices = [i.split("@@")[0] for i in uploaded_files]
    else:
        uploaded_indices = []

    remaining_indices = [f"{i:04}" for i in range(len(down.vinfo["ts"])) 
                       if f"{i:04}" not in uploaded_indices]

    if not remaining_indices:
        logger.info("所有文件已上传完成")
        if not os.path.exists(os.path.join(base_dir, "temp")):
            with open(os.path.join(base_dir, "temp"), "w") as f:
                pass
        down.save_m3u8()
        print("任务完成")
        return

    logger.info(f"开始上传 {len(remaining_indices)} 个文件")
    workers = 10
    
    with open(os.path.join(base_dir, "temp"), "a", encoding='utf-8') as handle:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(down.load_ts, index, handle): index 
                      for index in remaining_indices}
            for future in futures:
                try:
                    future.result()
                except Exception:
                    continue

        if down.failed_uploads:
            logger.info("等待30秒后开始重试失败的上传...")
            time.sleep(30)
            down.retry_failed_uploads(handle)
        
        while down.failed_uploads:
            failed_indexes = [str(item[0]) for item in down.failed_uploads]
            logger.error(f"以下分片上传失败: {', '.join(failed_indexes)}")
            retry = input("是否要重试失败的上传? (Y/N): ").strip().upper()
            if retry == 'Y':
                logger.info("等待10秒后开始重试...")
                time.sleep(10)
                down.retry_failed_uploads(handle)
            else:
                break

    logger.info(f"{base_dir} 下载完成")
    down.save_m3u8()
    print("任务完成")