from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Главная страница сайта
@app.get("/")
def index():
    return render_template("index.html")


# Проверка, что сервер запущен
@app.get("/api/status")
def status():
    return jsonify({
        "project": "SmartGuard AI",
        "status": "online",
        "version": "1.0"
    })


# Пример приёма тестового события от устройства
@app.post("/api/event")
def receive_event():
    data = request.get_json(silent=True) or {}

    event = {
        "type": data.get("type", "motion"),
        "device": data.get("device", "ESP32"),
        "message": data.get("message", "Обнаружено событие")
    }

    # Здесь можно добавить сохранение фотографии,
    # отправку уведомления или запись события в базу данных.
    app.logger.info("Получено событие: %s", event)

    return jsonify({
        "success": True,
        "event": event
    }), 201


if __name__ == "__main__":
    app.run(debug=True) 
