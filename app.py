#!/usr/bin/env python3
"""Simple Raspberry Pi camera server. Run with: python3 app.py"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, quote
from datetime import datetime
from io import BytesIO
import json
import os
import re
import errno
import shutil
import stat
import threading
import time
import uuid

from PIL import Image, ImageEnhance
from picamera2 import Picamera2

ROOT = Path(__file__).resolve().parent
PHOTO_DIR = Path.home() / 'Pictures' / 'CCD Camera'
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_LOCK = threading.Lock()
FRAME_CONDITION = threading.Condition()
LATEST_FRAME = None
FRAME_VERSION = 0
CAMERA = None
STILL_CONFIG = None
READY = False
ERROR = '摄像头正在启动'
PHOTO_NAME = re.compile(r'CCD_[0-9]{8}_[0-9]{6}_[0-9a-f]{6}\.jpg\Z')
TRASH_LOCK = threading.Lock()


def set_error(message):
    global ERROR
    ERROR = str(message)


def camera_worker():
    global CAMERA, STILL_CONFIG, READY, LATEST_FRAME, FRAME_VERSION
    try:
        CAMERA = Picamera2()
        preview = CAMERA.create_preview_configuration(main={'size': (960, 720), 'format': 'RGB888'}, buffer_count=4)
        STILL_CONFIG = CAMERA.create_still_configuration(main={'size': (2592, 1944), 'format': 'RGB888'})
        CAMERA.configure(preview)
        CAMERA.start()
        READY = True
        set_error('')
        while True:
            started = time.monotonic()
            try:
                with CAMERA_LOCK:
                    frame = CAMERA.capture_image('main')
                output = BytesIO()
                frame.convert('RGB').save(output, format='JPEG', quality=78)
                with FRAME_CONDITION:
                    LATEST_FRAME = output.getvalue()
                    FRAME_VERSION += 1
                    FRAME_CONDITION.notify_all()
                set_error('')
            except Exception as exc:
                set_error('预览失败：' + str(exc))
                time.sleep(1)
            time.sleep(max(0, 0.12 - (time.monotonic() - started)))
    except Exception as exc:
        READY = False
        set_error('摄像头无法启动：' + str(exc))
        print(ERROR, flush=True)


def ccd_effect(image):
    # A gentle warm, low-contrast film-like look; this is software simulation.
    image = image.convert('RGB')
    image = ImageEnhance.Contrast(image).enhance(0.94)
    image = ImageEnhance.Color(image).enhance(0.94)
    red, green, blue = image.split()
    red = red.point([min(255, round(i * 1.025 + 3)) for i in range(256)])
    green = green.point([min(255, round(i * 1.005 + 1)) for i in range(256)])
    blue = blue.point([max(0, min(255, round(i * 0.965))) for i in range(256)])
    return Image.merge('RGB', (red, green, blue))


def take_photo(effect):
    if not READY or CAMERA is None:
        raise RuntimeError(ERROR or '摄像头尚未就绪')
    with CAMERA_LOCK:
        image = CAMERA.switch_mode_and_capture_image(STILL_CONFIG, 'main')
    image = ccd_effect(image) if effect == 'ccd' else image.convert('RGB')
    name = 'CCD_' + datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:6] + '.jpg'
    path = PHOTO_DIR / name
    temp = PHOTO_DIR / ('.' + name + '.tmp')
    try:
        image.save(temp, format='JPEG', quality=93, optimize=True)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return '/photos/' + quote(name)


def trash_photo(name):
    """Move one regular photo into the user's desktop Trash without overwriting."""
    if not PHOTO_NAME.fullmatch(name):
        raise FileNotFoundError(name)
    data_home = os.environ.get('XDG_DATA_HOME', '')
    data_home = Path(data_home) if data_home and os.path.isabs(data_home) else Path.home() / '.local' / 'share'
    trash = data_home / 'Trash'
    files, info = trash / 'files', trash / 'info'
    with TRASH_LOCK:
        for folder in (trash, files, info):
            if folder.is_symlink():
                raise OSError('回收站目录不能是符号链接')
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        source_dir = os.open(PHOTO_DIR, flags)
        try:
            try:
                source = os.open(name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0), dir_fd=source_dir)
            except OSError as exc:
                if exc.errno in (errno.ENOENT, errno.ELOOP):
                    raise FileNotFoundError(name) from exc
                raise
            try:
                original = os.fstat(source)
                if not stat.S_ISREG(original.st_mode):
                    raise FileNotFoundError(name)
                dest_dir = os.open(files, flags)
                try:
                    # A random name and exclusive metadata/destination creation prevent overwrite.
                    trash_name = name[:-4] + '-' + uuid.uuid4().hex + '.jpg'
                    metadata = info / (trash_name + '.trashinfo')
                    metadata_fd = os.open(metadata, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                    created = False
                    try:
                        with os.fdopen(metadata_fd, 'w', encoding='utf-8') as f:
                            f.write('[Trash Info]\nPath=' + quote(str(PHOTO_DIR.absolute() / name), safe='/') +
                                    '\nDeletionDate=' + datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '\n')
                            f.flush()
                            os.fsync(f.fileno())
                        try:
                            os.link(name, trash_name, src_dir_fd=source_dir, dst_dir_fd=dest_dir, follow_symlinks=False)
                            created = True
                            linked = os.stat(trash_name, dir_fd=dest_dir, follow_symlinks=False)
                            if (linked.st_dev, linked.st_ino) != (original.st_dev, original.st_ino) or not stat.S_ISREG(linked.st_mode):
                                raise OSError('照片在删除时发生变化，请重试')
                        except OSError as exc:
                            if exc.errno != errno.EXDEV:
                                raise
                            target = os.open(trash_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600, dir_fd=dest_dir)
                            created = True
                            with os.fdopen(target, 'wb') as out, os.fdopen(os.dup(source), 'rb') as inp:
                                shutil.copyfileobj(inp, out)
                                out.flush()
                                os.fsync(out.fileno())
                        current = os.stat(name, dir_fd=source_dir, follow_symlinks=False)
                        if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino) or not stat.S_ISREG(current.st_mode):
                            raise OSError('照片在删除时发生变化，请重试')
                        os.unlink(name, dir_fd=source_dir)
                    except BaseException:
                        if created:
                            try:
                                os.unlink(trash_name, dir_fd=dest_dir)
                            except FileNotFoundError:
                                pass
                        metadata.unlink(missing_ok=True)
                        raise
                finally:
                    os.close(dest_dir)
            finally:
                os.close(source)
        finally:
            os.close(source_dir)


class Handler(BaseHTTPRequestHandler):
    server_version = 'CCDCamera/1.0'

    def respond(self, status, body, content_type, headers=()):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status, obj):
        self.respond(status, json.dumps(obj, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8', [('Cache-Control', 'no-store')])

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            try:
                self.respond(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8', [('Cache-Control', 'no-store')])
            except OSError:
                self.send_error(500, 'Interface file unavailable')
        elif path == '/api/status':
            self.json_response(200, {'ready': READY, 'error': ERROR})
        elif path == '/api/photos':
            photos = sorted(PHOTO_DIR.glob('CCD_*.jpg'), key=lambda p: p.name, reverse=True)[:100]
            self.json_response(200, {'photos': [{'name': p.name, 'url': '/photos/' + quote(p.name)} for p in photos]})
        elif path == '/stream':
            if not READY:
                self.json_response(503, {'error': ERROR or '摄像头尚未就绪'})
                return
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Connection', 'close')
            self.end_headers()
            version = -1
            try:
                while True:
                    with FRAME_CONDITION:
                        FRAME_CONDITION.wait_for(lambda: FRAME_VERSION != version, timeout=10)
                        frame, version = LATEST_FRAME, FRAME_VERSION
                    if not frame:
                        continue
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError, OSError):
                pass
        elif path.startswith('/photos/'):
            name = unquote(path[len('/photos/'):])
            if not re.fullmatch(r'CCD_[0-9]{8}_[0-9]{6}_[0-9a-f]{6}\.jpg', name):
                self.send_error(404)
                return
            try:
                data = (PHOTO_DIR / name).read_bytes()
                self.respond(200, data, 'image/jpeg', [('Cache-Control', 'private, max-age=3600')])
            except FileNotFoundError:
                self.send_error(404)
        elif path == '/favicon.ico':
            self.respond(204, b'', 'image/x-icon')
        else:
            self.send_error(404)

    def do_POST(self):
        if urlsplit(self.path).path != '/api/capture':
            self.send_error(404)
            return
        # Reject browser requests from other origins on the same network.
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.json_response(403, {'error': '请求来源不受信任'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 1024:
                self.json_response(413, {'error': '请求过大'})
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            effect = data.get('effect', 'ccd')
            if effect not in ('ccd', 'original'):
                self.json_response(400, {'error': '未知的照片效果'})
                return
            url = take_photo(effect)
            self.json_response(200, {'url': url})
        except (ValueError, TypeError, AttributeError):
            self.json_response(400, {'error': '请求格式不正确'})
        except Exception as exc:
            self.json_response(500, {'error': '拍照失败：' + str(exc)})

    def do_DELETE(self):
        path = urlsplit(self.path).path
        if not path.startswith('/api/photos/'):
            self.json_response(404, {'error': '未找到照片'})
            return
        origin = self.headers.get('Origin', '')
        parsed = urlsplit(origin)
        if parsed.scheme not in ('http', 'https') or parsed.netloc != self.headers.get('Host'):
            self.json_response(403, {'error': '请求来源不受信任'})
            return
        name = unquote(path[len('/api/photos/'):])
        try:
            trash_photo(name)
            self.json_response(200, {'ok': True})
        except FileNotFoundError:
            self.json_response(404, {'error': '照片不存在或不能删除'})
        except OSError:
            self.json_response(500, {'error': '无法移动照片到回收站，请检查存储和权限'})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    threading.Thread(target=camera_worker, daemon=True).start()
    server = Server(('0.0.0.0', 8091), Handler)
    print('CCD Camera: http://0.0.0.0:8091', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if CAMERA is not None:
            CAMERA.stop()
            CAMERA.close()

