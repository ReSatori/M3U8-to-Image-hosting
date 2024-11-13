# M3U8 Video Processor
修改自[M3U8-Uploader](https://github.com/239144498/M3U8-Uploader)

一个用于处理和上传M3U8视频的Python工具。支持本地视频切片和远程M3U8下载上传。

## 功能特点

- 支持本地视频切片并上传
- 支持远程M3U8下载并上传
- 支持多个图床接口
- 支持断点续传
- 支持命令行和交互式操作

## 环境要求

- Python 3.7+
- FFmpeg

## 依赖安装 
```bash 
pip install -r requirements.txt
```
## 使用方法

### 交互式模式(推荐)

直接运行程序：
```bash
python app.py
```

按照提示进行操作：
1. 选择是否测试接口
2. 选择操作模式（本地切片/远程上传）
3. 根据选择的模式进行相应操作

### 命令行模式

1. 本地视频切片：
```bash
python app.py -L -new -u 1
```
2. 远程M3U8下载：
```bash
python app.py -R -url "your_m3u8_url" -new -u 1
```

参数说明：
- `-L/--local`: 本地上传模式
- `-R/--remote`: 远程上传模式
- `-new/--new_upload`: 新上传(清空已有文件)
- `-N/--no_verify`: 不验证接口
- `-u/--upload_api`: 指定上传接口(1-3)
- `-url/--m3u8_url`: M3U8链接(远程模式必需)


## 注意事项

1. 使用前请确保已安装FFmpeg并添加到系统环境变量
2. 本地视频请放在input目录下
3. 上传接口可能会有限制，请注意文件大小
4. 建议先测试接口可用性再使用

## License

MIT License @ heilo.cn

## 鸣谢

[M3U8-Uploader](https://github.com/239144498/M3U8-Uploader)

## 免责声明

本工具仅供学习交流使用，请勿用于非法用途。使用本工具所产生的一切后果由使用者自行承担。