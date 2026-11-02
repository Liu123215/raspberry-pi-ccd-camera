# Light & Shadow Camera · CCD Camera

[中文说明](README.md) · English

A lightweight Raspberry Pi camera application with live view, a warm CCD-inspired color treatment, and a browser-based photo gallery. Use it on the Raspberry Pi itself or from a phone or computer on the same network.

The CCD look is a software simulation; it does not change the camera sensor. The live-view filter differs from the processing applied to saved photographs, so the two may not look identical.

## Features

- View the camera feed and take photos using the warm CCD tone or original color.
- Save JPEG images locally, request still captures at 2592 × 1944, and view or download up to the most recent 100 photos. Older photos are not deleted when the gallery limit is reached.
- Delete a photo from its preview after confirming. The photo is moved to the Raspberry Pi user's desktop Trash and can be restored from the file manager's Trash before it is emptied.
- Use a responsive interface on phones, computers, or the Raspberry Pi desktop.
- Record, play back, and download MP4 video. Video uses original colors and does not include audio.
- The album shows photos and videos together; deleted videos are moved to the desktop Trash.

## Privacy and access

**The camera service listens on all network interfaces on port 8091 and has no login or HTTPS encryption.** Anyone who can reach it may be able to see the live feed and photos, take photographs, and move photos to Trash. Use it only on a trusted local network; do not expose the port to the internet. Browser confirmation and origin checks are not a substitute for authentication.

The service holds the camera while running. Other camera applications may not be able to use it simultaneously. The live view can pause briefly when the application switches to the still-image mode.

## Requirements

- A Raspberry Pi camera supported by libcamera and Picamera2, connected with the correct cable.
- Raspberry Pi OS or a compatible Debian environment, Python 3, Picamera2, Pillow, and a modern browser. A desktop is optional if you connect over SSH and use another device's browser.
- Enough storage for JPEG images. Capture resolution depends on the camera and driver.

The project has been tested with an OV5647 camera on one Raspberry Pi running Debian 13. Other boards, systems, and camera models have not all been tested. If a camera does not support the configured sizes, adjust the configuration in `app.py` and test it with that device.

## Installation

Run these commands in a terminal on the Raspberry Pi, or connect to it over SSH first.

1. Confirm that the camera is detected:

   ```bash
   rpicam-hello --list-cameras
   ```

   Some older systems use `libcamera-hello --list-cameras`. If no camera is listed, check the cable, power, camera configuration, and the installed camera utilities.

2. Install the required system packages:

   ```bash
   sudo apt update
   sudo apt install -y git python3 python3-picamera2 python3-pil
   python3 -c "from picamera2 import Picamera2; from PIL import Image; print('Dependencies available')"
   ```

   System Python and system packages are recommended. A normal virtual environment may not be able to import the system Picamera2 package without additional configuration.

3. Clone and start the project:

   ```bash
   git clone https://github.com/Liu123215/raspberry-pi-ccd-camera.git ~/ccd-camera
   cd ~/ccd-camera
   python3 app.py
   ```

   Leave the terminal running. Camera initialization can take a few seconds. Press `Ctrl+C` to stop the server and release the camera.

## Use the camera

On the Raspberry Pi, open `http://127.0.0.1:8091/` in a browser. To connect from another device, run `hostname -I` on the Raspberry Pi and open `http://<raspberry-pi-local-ip>:8091/` from a device on the same trusted, mutually accessible network.

Select a tone, press the shutter, and wait for the save confirmation. Open a gallery thumbnail to view the photo; use the download control to save it to the device you are using. The delete control asks for confirmation and moves the image to the Raspberry Pi user's Trash. To recover it, open the Raspberry Pi file manager's Trash, find the photo, and choose its restore action. Photos are not permanently removed until the Trash is emptied or cleaned by another mechanism.

The original JPEG files are stored under `~/Pictures/CCD Camera/` for the user running the service. The directory is created automatically; filenames contain the Raspberry Pi's system time and a random suffix. Keep separate backups of photos you want to retain.

Videos are saved in the project's `videos/` directory. Stop recording before taking a photo, keep the device powered on, and monitor available storage during recording.

## Optional: run as a user service

The example assumes the project is in `~/ccd-camera`:

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

```bash
systemctl --user status ccd-camera.service
journalctl --user -u ccd-camera.service -f
systemctl --user restart ccd-camera.service
systemctl --user stop ccd-camera.service
```

To enable startup with the user service manager, run `systemctl --user enable ccd-camera.service`. User services depend on system and login configuration; enabling the service alone does not guarantee startup without a user login. Disable startup with `systemctl --user disable ccd-camera.service`; stop an already running service separately.

## Troubleshooting

- **No camera or preview:** check `rpicam-hello --list-cameras`, cabling, power, and permissions. Stop other camera applications and inspect the terminal or `journalctl --user -u ccd-camera.service -n 100 --no-pager`.
- **Phone cannot connect:** check that the service is running, use the correct local address and port 8091, and ensure the network permits devices to reach each other. Guest Wi-Fi may isolate clients.
- **Port already in use:** inspect `ss -ltnp | grep ':8091'`. Stop a duplicate instance or, after considering the effects, change the port in `app.py` and restart.
- **Photo cannot be saved or trashed:** check write permissions, available space with `df -h ~`, and service logs. Verify that the desktop Trash is available to the service's user.
- **Capture fails on another camera:** the configured preview is 960 × 720 and still capture is 2592 × 1944. Check supported modes and adjust the configuration as needed.

## Files

- `app.py` — camera capture, image processing, storage, and HTTP service.
- `index.html` — responsive camera and gallery interface.
- `README.md` / `README.en.md` — Chinese and English documentation.

The backend uses Python's standard HTTP library, Picamera2, and Pillow. The live feed is MJPEG and saved photos are JPEG.

