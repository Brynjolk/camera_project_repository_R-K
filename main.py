import cv2
import os
import time
import threading
import json
import zipfile
import requests
import socket
import shutil
from datetime import datetime
from flask import Flask, render_template, send_from_directory, send_file, jsonify, Response

app = Flask(__name__)

# ================= НАСТРОЙКИ =================
# ⚠️ ВНИМАНИЕ: Убедитесь, что здесь указан актуальный IP вашей ESP32 (смотрите в Thonny)
ESP32_IP = "10.140.13.67" # ⚠️ ОБЯЗАТЕЛЬНО УКАЖИТЕ IP-АДРЕС ВАШЕГО ESP32 ЗДЕСЬ
ESP32_PORT = 8080

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
PHOTO_DIR = os.path.join(STATIC_DIR, "photos")
VIDEO_DIR = os.path.join(STATIC_DIR, "videos")
ARCHIVE_DIR = os.path.join(STATIC_DIR, "archives")
RECENTLY_DELETED_DIR = os.path.join(STATIC_DIR, "recently_deleted")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

for d in [PHOTO_DIR, VIDEO_DIR, ARCHIVE_DIR, RECENTLY_DELETED_DIR, TEMPLATES_DIR]:
    os.makedirs(d, exist_ok=True)

history = []

# ================= ИИ: РАСПОЗНАВАНИЕ ЛИЦ =================
# Используем встроенный путь OpenCV, чтобы не искать xml файл вручную
cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
face_cascade = cv2.CascadeClassifier(cascade_path)
if face_cascade.empty():
    print("❌ Ошибка: Не удалось загрузить модель распознавания лиц!")
else:
    print("✅ Модель распознавания лиц (Haar Cascade) успешно загружена.")

# ================= КАМЕРА =================
cap = None
is_camera_ready = False
camera_lock = threading.Lock()
latest_frame = None

def init_camera():
    global cap, is_camera_ready
    for idx in [0, 1, 2]:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            for _ in range(5): cap.read()
            print(f"✅ Camera initialized on index {idx}: 1280x720 @ 30 FPS")
            is_camera_ready = True
            return True
        cap.release()
    print("⚠️ Camera not found!")
    is_camera_ready = False
    return False

init_camera()

def camera_read_loop():
    global latest_frame
    while True:
        if not is_camera_ready:
            time.sleep(1)
            continue
        ret, frame = cap.read()
        if ret:
            with camera_lock:
                latest_frame = frame.copy()
        else:
            time.sleep(0.03)

if is_camera_ready:
    threading.Thread(target=camera_read_loop, daemon=True).start()

def get_frame():
    with camera_lock:
        return latest_frame.copy() if latest_frame is not None else None

# ================= LIVE СТРИМ =================
def generate_frames():
    while True:
        frame = get_frame()
        if frame is None:
            time.sleep(0.03)
            continue
        try:
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret: continue
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        except Exception:
            time.sleep(0.03)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ================= УПРАВЛЕНИЕ ESP32 =================
def trigger_esp_alarm():
    try:
        requests.get(f"http://{ESP32_IP}:{ESP32_PORT}/alarm", timeout=2)
        print("🔊 ALARM SENT")
    except Exception as e:
        print(f"❌ ESP32 ERR: {e}")

def stop_esp_alarm():
    try:
        requests.get(f"http://{ESP32_IP}:{ESP32_PORT}/stop", timeout=2)
        print("🔇 STOP SENT")
    except Exception as e:
        print(f"❌ ESP32 STOP ERR: {e}")

# ================= ИСТОРИЯ (С ЗАЩИТОЙ ОТ ПРОБЕЛОВ) =================
def load_history():
    global history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                history = []
                for item in raw_data:
                    clean = {}
                    for k, v in item.items():
                        ck = k.strip() # Убираем пробелы из ключей
                        if isinstance(v, list):
                            clean[ck] = [str(x).strip() for x in v if x]
                        elif isinstance(v, str):
                            clean[ck] = v.strip()
                        else:
                            clean[ck] = v
                    history.append(clean)
        except Exception as e:
            print(f"Ошибка загрузки истории: {e}")
            history = []

def save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

# ================= СОХРАНЕНИЕ СОБЫТИЯ =================
def capture_event(trigger_frame):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    human_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    photos_saved = []
    p1 = f"motion_{timestamp}_1.jpg"
    cv2.imwrite(os.path.join(PHOTO_DIR, p1), trigger_frame)
    photos_saved.append(f"photos/{p1}")
    for i in range(2, 4):
        time.sleep(0.4)
        frm = get_frame()
        if frm is not None:
            fname = f"motion_{timestamp}_{i}.jpg"
            cv2.imwrite(os.path.join(PHOTO_DIR, fname), frm)
            photos_saved.append(f"photos/{fname}")

    video_filename = f"motion_{timestamp}.mp4"
    video_path = os.path.join(VIDEO_DIR, video_filename)

    # Берем реальные размеры кадра, чтобы видео не ломалось
    h, w = trigger_frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 20.0, (w, h))

    start = time.time()
    while time.time() - start < 10:
        frm = get_frame()
        if frm is not None:
            if frm.shape[1] != w or frm.shape[0] != h:
                frm = cv2.resize(frm, (w, h))
            out.write(frm)
        time.sleep(0.04)
    out.release()

    event = {"timestamp": human_time, "photos": photos_saved, "video": f"videos/{video_filename}", "video_file": video_filename}
    history.insert(0, event)
    if len(history) > 50: history.pop()
    save_history()
    print(f"✅ Event saved: {human_time}")

# ================= ДЕТЕКЦИЯ ДВИЖЕНИЯ + ЛИЦА =================
def motion_detection_loop():
    prev_gray = None
    motion_start_time = None
    last_motion_time = None
    peak_area = 0
    alarm_active = False

    # Настройки чувствительности
    MIN_MOTION_DURATION = 0.8  # Быстрая реакция
    MOTION_TIMEOUT = 2.0       # Таймаут, чтобы не сбивалось при паузах
    MIN_MOTION_AREA = 1500     # Площадь для движения
    WARMUP_FRAMES = 30
    frame_count = 0

    print("👁️ Motion & Face detection loop started...")

    while True:
        frame = get_frame()
        if frame is None:
            time.sleep(0.03)
            continue

        frame_count += 1
        if frame_count < WARMUP_FRAMES:
            time.sleep(0.03)
            continue

        current_time = time.time()

        # Уменьшаем кадр для быстрого анализа
        small = cv2.resize(frame, (480, 270))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (15, 15), 0)

        motion_detected = False
        current_area = 0

        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray)
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            thresh = cv2.dilate(thresh, kernel, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid_contours = [c for c in contours if cv2.contourArea(c) > 400]
            current_area = sum(cv2.contourArea(c) for c in valid_contours)
            motion_detected = current_area > MIN_MOTION_AREA

        # 🧠 ИИ: Детекция лиц (Работает даже если человек стоит на месте!)
        face_detected = False
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        if len(faces) > 0:
            face_detected = True
            # Рисуем рамку вокруг лица на оригинальном кадре
            scale_x = frame.shape[1] / 480
            scale_y = frame.shape[0] / 270
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (int(x*scale_x), int(y*scale_y)), (int((x+w)*scale_x), int((y+h)*scale_y)), (0, 255, 0), 2)
                cv2.putText(frame, "FACE", (int(x*scale_x), int(y*scale_y)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 🟢 ГЛАВНАЯ ЛОГИКА: Сирена звенит, если есть движение ИЛИ лицо
        should_ring = motion_detected or face_detected

        if should_ring:
            if motion_start_time is None:
                motion_start_time = current_time
                last_motion_time = current_time
                peak_area = current_area
                reason = "Face" if face_detected else f"Motion (Area: {current_area:.0f})"
                print(f"👀 Trigger started ({reason})")
            else:
                last_motion_time = current_time
                peak_area = max(peak_area, current_area)

            # Включаем сирену
            if not alarm_active and (current_time - motion_start_time) >= MIN_MOTION_DURATION:
                alarm_active = True
                print(f"🚨 ALARM TRIGGERED (Peak Area: {peak_area:.0f})")
                threading.Thread(target=capture_event, args=(frame.copy(),), daemon=True).start()
                trigger_esp_alarm()
        else:
            if motion_start_time is not None:
                if current_time - last_motion_time >= MOTION_TIMEOUT:
                    print("👀 Trigger ended")
                    if alarm_active:
                        print("🔇 ALARM STOPPED")
                        stop_esp_alarm()
                        alarm_active = False
                    motion_start_time = None
                    last_motion_time = None
                    peak_area = 0

        prev_gray = gray
        time.sleep(0.03)

# ================= ВЕБ-МАРШРУТЫ =================
@app.route("/")
def index():
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except: pass
    return render_template("index.html", events=history, esp_ip=ESP32_IP, esp_port=ESP32_PORT, local_ip=local_ip)

@app.route("/download/<path:filepath>")
def download_file(filepath):
    return send_from_directory("static", filepath, as_attachment=False)

@app.route("/download_all")
def download_all():
    zip_name = f"all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = os.path.join(ARCHIVE_DIR, zip_name)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in os.listdir(PHOTO_DIR):
            if f.endswith(".jpg"): zf.write(os.path.join(PHOTO_DIR, f), f"photos/{f}")
        for f in os.listdir(VIDEO_DIR):
            if f.endswith(".mp4"): zf.write(os.path.join(VIDEO_DIR, f), f"videos/{f}")
    return send_file(zip_path, as_attachment=True, download_name=zip_name)

@app.route("/event_archive/<int:idx>")
def event_archive(idx):
    if not (0 <= idx < len(history)): return "Not found", 404
    ev = history[idx]
    zip_name = f"event_{idx}_{datetime.now().strftime('%Y%m%d')}.zip"
    zip_path = os.path.join(ARCHIVE_DIR, zip_name)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in ev.get("photos", []):
            fp = os.path.join(STATIC_DIR, p)
            if os.path.exists(fp): zf.write(fp, os.path.basename(fp))
        if ev.get("video_file"):
            fp = os.path.join(STATIC_DIR, "videos", ev["video_file"])
            if os.path.exists(fp): zf.write(fp, ev["video_file"])
    return send_file(zip_path, as_attachment=True, download_name=zip_name)

@app.route("/delete_photo/<filename>", methods=["POST"])
def delete_photo(filename):
    filepath = os.path.join(PHOTO_DIR, filename)
    if os.path.exists(filepath):
        shutil.move(filepath, os.path.join(RECENTLY_DELETED_DIR, filename))
        for ev in history:
            path = f"photos/{filename}"
            if path in ev.get("photos", []): ev["photos"].remove(path)
        save_history()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route("/delete_video/<filename>", methods=["POST"])
def delete_video(filename):
    filepath = os.path.join(VIDEO_DIR, filename)
    if os.path.exists(filepath):
        shutil.move(filepath, os.path.join(RECENTLY_DELETED_DIR, filename))
        for ev in history:
            if ev.get("video_file") == filename: ev["video"] = ""; ev["video_file"] = ""
        save_history()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route("/delete_event/<int:idx>", methods=["POST"])
def delete_event(idx):
    if 0 <= idx < len(history):
        ev = history[idx]
        for p in ev.get("photos", []):
            fp = os.path.join(PHOTO_DIR, os.path.basename(p))
            if os.path.exists(fp): shutil.move(fp, os.path.join(RECENTLY_DELETED_DIR, os.path.basename(p)))
        if ev.get("video_file"):
            fp = os.path.join(VIDEO_DIR, ev["video_file"])
            if os.path.exists(fp): shutil.move(fp, os.path.join(RECENTLY_DELETED_DIR, ev["video_file"]))
        history.pop(idx)
        save_history()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route("/delete_all", methods=["POST"])
def delete_all_history():
    for f in os.listdir(PHOTO_DIR):
        if f.endswith(".jpg"): shutil.move(os.path.join(PHOTO_DIR, f), os.path.join(RECENTLY_DELETED_DIR, f))
    for f in os.listdir(VIDEO_DIR):
        if f.endswith(".mp4"): shutil.move(os.path.join(VIDEO_DIR, f), os.path.join(RECENTLY_DELETED_DIR, f))
    history.clear()
    save_history()
    return jsonify({"success": True})

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("🚀 Starting SmartGuard AI Security System...")
    load_history()
    if not is_camera_ready:
        print("⚠️ Camera failed.")
    threading.Thread(target=motion_detection_loop, daemon=True).start()
    print(f"🌐 Web server: http://127.0.0.1:5000")
    print(f"📹 Live stream: /video_feed")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
