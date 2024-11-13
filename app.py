import sys
import os
import argparse
from loguru import logger
from core import local_slice_and_upload, remote_upload, Down
from upload_apis import UPLOAD_APIS

# 添加测试文件检查
def ensure_test_file():
    test_file = "1.png"
    if not os.path.exists(test_file):
        # 如果测试文件不存在，创建一个小的测试文件
        with open(test_file, "wb") as f:
            f.write(b"test")

def test_upload_interface(upload_func):
    ensure_test_file()  # 确保测试文件存在
    try:
        with open("1.png", "rb") as file:
            fdata = file.read()
        url = upload_func("1.png", fdata)
        logger.info(f"{upload_func.__name__} 接口可用")
        return True
    except Exception as e:
        logger.warning(f"{upload_func.__name__} 接口不可用: {e}")
        return False

def parse_args():
    parser = argparse.ArgumentParser(description='M3U8视频处理工具')
    
    # 基础参数
    parser.add_argument('-L', '--local', action='store_true', help='本地上传模式')
    parser.add_argument('-R', '--remote', action='store_true', help='远程上传模式')
    parser.add_argument('-new', '--new_upload', action='store_true', help='新上传(清空已有文件)')
    parser.add_argument('-N', '--no_verify', action='store_true', help='不验证接口')
    parser.add_argument('-u', '--upload_api', type=int, choices=[1,2,3,4], help='指定上传接口(1-4)')
    parser.add_argument('-url', '--m3u8_url', type=str, help='M3U8链接(远程模式必需)')
    
    if len(sys.argv) > 1:
        args = parser.parse_args()
        if not (args.local or args.remote):
            parser.error('必须指定模式: -L(本地上传) 或 -R(远程上传)')
        if args.local and args.remote:
            parser.error('不能同时指定本地和远程模式')
        if args.remote and not args.m3u8_url:
            parser.error('远程模式必须提供M3U8链接(-url)')
        return args
    return None

def main():
    args = parse_args()
    
    if args:  # 命令行模式
        if args.local:
            local_slice_and_upload(args)
        elif args.remote:
            remote_upload(args)
    else:  # 交互式模式
        logger.info("开始运行")
        
        # 1. 首先询问是否测试接口
        test_interfaces = input("是否测试接口 (Y/N): ").strip().upper()
        if test_interfaces == 'Y':
            available_uploads = []
            for upload_func in UPLOAD_APIS:
                if test_upload_interface(upload_func):
                    available_uploads.append(upload_func)
            if not available_uploads:
                logger.error("所有接口都不可用")
                return
        
        # 2. 选择模式
        mode = input("请选择模式 (1: 本地切片, 2: 远程上传): ").strip()
        
        if mode == '1':  # 本地切片模式
            # 3a. 选择新切还是续传
            is_new = input("是否新切片 (Y/N): ").strip().upper()
            args = argparse.Namespace()
            args.new_upload = (is_new == 'Y')
            
            # 4a. 选择上传接口
            logger.info("可用接口: " + ", ".join([f"{i+1}. {func.__name__}" for i, func in enumerate(UPLOAD_APIS)]))
            selected_index = int(input("请选择一个接口 (序号): ").strip()) - 1
            if selected_index < 0 or selected_index >= len(UPLOAD_APIS):
                logger.error("选择的接口序号无效")
                return
            args.upload_api = selected_index + 1
            
            # 5a. 执行本地切片
            local_slice_and_upload(args)
            
        elif mode == '2':  # 远程上传模式
            # 3b. 输入m3u8链接
            m3u8_url = input("请输入m3u8链接: ").strip()
            if not m3u8_url:
                logger.error("m3u8链接不能为空")
                return
            
            # 4b. 选择新下载还是续传
            is_new = input("是否新下载 (Y/N): ").strip().upper()
            args = argparse.Namespace()
            args.new_upload = (is_new == 'Y')
            args.m3u8_url = m3u8_url
            args.remote = True  # 修改这里，使用remote替代network
            
            # 5b. 选择上传接口
            logger.info("可用接口: " + ", ".join([f"{i+1}. {func.__name__}" for i, func in enumerate(UPLOAD_APIS)]))
            selected_index = int(input("请选择一个接口 (序号): ").strip()) - 1
            if selected_index < 0 or selected_index >= len(UPLOAD_APIS):
                logger.error("选择的接口序号无效")
                return
            args.upload_api = selected_index + 1
            
            # 6b. 执行远程上传
            remote_upload(args)
            
        else:
            logger.error("无效的选择")

if __name__ == '__main__':
    main()

