# 光影相机 · CCD Camera

一个运行在树莓派上的轻量级相机应用。用树莓派连接的摄像头实时取景，选择自然偏暖的 CCD 模拟色调或原色拍照，并在浏览器里查看和下载照片。界面适配树莓派桌面、电脑和手机。

> CCD 色调由软件处理模拟，摄像头传感器不会因此变成 CCD。浏览器中的取景滤镜和保存照片时的处理方式不同，预览与成片可能略有差异。

## 功能

- 实时取景：在网页查看树莓派摄像头的画面。
- 两种色调：自然偏暖的 CCD 模拟效果，以及未经该效果处理的原色。
- 高清拍照：默认请求 2592 × 1944 的照片，实际支持情况取决于摄像头和驱动。
- 照片相册：查看最近最多 100 张照片，打开大图并下载；已有照片不会因超过 100 张而被删除。
- 跨设备访问：在树莓派本机浏览器，或同一局域网内的手机、电脑浏览器中使用。
- 照片保存在树莓派本地，不依赖云服务。

## 使用前请注意

**服务默认监听所有网络接口的 8091 端口，没有登录验证，也没有 HTTPS 加密。** 能访问该端口的人可能查看实时画面和照片、触发拍摄。请仅在可信局域网内使用；不要将端口映射到公网，也不要直接部署在不可信网络中。若需要公网访问，请先自行配置可靠的身份认证和加密访问。

运行期间应用会占用摄像头，其他程序可能无法同时使用。拍照时会暂时切换到高分辨率模式，取景画面可能短暂停顿。

## 硬件与软件要求

- 支持 libcamera / Picamera2 的树莓派摄像头及正确连接的排线。
- 带图形桌面的 Raspberry Pi OS 或兼容的 Debian 系统；也可以通过 SSH 在无桌面环境中运行，再用局域网内的浏览器访问。
- Python 3、Picamera2、Pillow，以及现代浏览器。
- 足够的磁盘空间，用于保存 JPEG 照片。

本项目已在 Debian 13 的树莓派环境和 OV5647 摄像头上进行过试拍。其他设备、系统版本与摄像头尚未全部验证；若其不支持默认分辨率，可能需要调整 `app.py` 中的相机配置。

## 安装

以下命令在树莓派的终端中执行。如果通过 SSH 操作，请先登录树莓派。

### 1. 检查摄像头

确认排线已连接、摄像头已被识别：

```bash
rpicam-hello --list-cameras
```

部分旧版本系统使用 `libcamera-hello --list-cameras`。如果命令不存在，请先按系统提供的方式安装相机应用；如果没有列出摄像头，请检查连接、供电和系统相机配置。

### 2. 安装依赖

在 Raspberry Pi OS / Debian 上，使用系统包安装：

```bash
sudo apt update
sudo apt install -y git python3 python3-picamera2 python3-pil
```

验证 Python 能导入相机和图像处理模块：

```bash
python3 -c "from picamera2 import Picamera2; from PIL import Image; print('依赖已就绪')"
```

建议使用系统的 `python3` 和系统包。普通虚拟环境默认可能看不到系统安装的 Picamera2；如果使用虚拟环境，需要自行确保其能访问系统包和相机相关依赖。

### 3. 获取项目

克隆本仓库到树莓派：

```bash
git clone https://github.com/Liu123215/raspberry-pi-ccd-camera.git ~/ccd-camera
cd ~/ccd-camera
```

### 4. 启动

```bash
cd ~/ccd-camera
python3 app.py
```

保持这个终端窗口打开。首次启动时，相机初始化可能需要几秒钟。在终端中按 `Ctrl+C` 可停止服务并释放摄像头。

## 打开相机

**树莓派本机：**在浏览器中访问 `http://127.0.0.1:8091/`。

**手机或其他电脑：**先在树莓派终端查询局域网地址：

```bash
hostname -I
```

找到与手机或电脑处于同一局域网的地址，然后在该设备的浏览器中输入 `http://树莓派的局域网IP:8091/`。如果显示多个地址，请选择当前网络对应的地址。手机应与树莓派处于可互相访问的网络中。

## 拍照与照片管理

1. 页面显示“摄像头已连接，可以拍照”后，确认实时取景画面。
2. 选择 **CCD** 或 **原色**，点击圆形快门按钮。
3. 等待页面提示保存成功；照片会出现在“最近的照片”中。
4. 点击缩略图查看大图，点击“下载”保存到当前使用的设备。

照片以 JPEG 格式保存在运行程序的用户目录下：

```text
~/Pictures/CCD Camera/
```

应用会在首次启动时创建该文件夹。照片名称包含时间和随机后缀；时间取决于树莓派的系统时间。网页不提供删除功能，可在树莓派上通过文件管理器自行管理照片。

## 可选：使用 systemd 用户服务

以下步骤适合希望在后台运行或随用户服务启动的用户。请先完成上面的安装，并确认项目位于 `~/ccd-camera`。服务以当前用户身份运行，照片也保存在该用户的目录中。

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/ccd-camera.service <<'EOF'
[Unit]
Description=CCD Camera

[Service]
Type=simple
WorkingDirectory=%h/ccd-camera
ExecStart=/usr/bin/python3 %h/ccd-camera/app.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user start ccd-camera.service
```

常用管理命令：

```bash
# 查看运行状态
systemctl --user status ccd-camera.service

# 查看日志
journalctl --user -u ccd-camera.service -f

# 停止并释放摄像头
systemctl --user stop ccd-camera.service

# 重新启动
systemctl --user restart ccd-camera.service
```

如需在用户服务管理器启动时自动运行，可执行：

```bash
systemctl --user enable ccd-camera.service
```

用户服务何时启动取决于系统和登录状态；仅启用此服务不保证设备在无人登录时启动。自动运行会占用摄像头，并使相机页面在局域网可访问，请根据实际需要选择。关闭自动启动可执行 `systemctl --user disable ccd-camera.service`，这不会停止已运行的服务；需要时再执行上面的 `stop` 命令。

## 常见问题

**页面提示摄像头不可用或没有取景画面**

先用 `rpicam-hello --list-cameras` 检查识别情况，再检查排线、电源与系统设置。确认其他相机程序已停止；如使用用户服务，可通过 `journalctl --user -u ccd-camera.service -n 100 --no-pager` 查看错误信息。摄像头连接或权限问题修复后，重启应用。

**手机打不开页面**

确认相机服务正在运行，手机和树莓派连接的网络允许设备互相访问；检查输入的局域网 IP 和 `8091` 端口。部分访客 Wi-Fi 会隔离设备，需要调整网络或换用可信局域网。可在树莓派本机访问 `http://127.0.0.1:8091/` 先排除服务故障。

**启动时提示端口已被占用**

检查是否已启动另一个实例，或是否有其他应用使用 8091：

```bash
ss -ltnp | grep ':8091'
```

停止多余的相机实例，或在了解影响后修改 `app.py` 中的监听端口并重启，再使用新端口访问。

**照片没有保存或加载失败**

检查运行用户对 `~/Pictures/CCD Camera/` 的写入权限和剩余空间（`df -h ~`），并查看终端或服务日志。服务或手机的下载不会自动备份照片，请按需要自行备份。

**切换分辨率或更换摄像头后无法拍照**

项目默认使用 960 × 720 预览、2592 × 1944 拍照。不同摄像头支持的模式不同，可先查看 `rpicam-hello --list-cameras` 的输出，再按设备支持的尺寸调整 `app.py` 的预览和拍照配置并重启。修改后需自行验证效果和稳定性。

## 项目结构

```text
.
├── app.py       # 相机采集、照片处理、保存和 HTTP 服务
├── index.html   # 响应式取景、拍照和相册界面
└── README.md
```

后端使用 Python 标准库提供 HTTP 服务，Picamera2 负责相机采集，Pillow 负责照片处理。实时画面使用 MJPEG；照片以 JPEG 保存。

