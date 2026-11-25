import cv2

# IP-адрес вашей ESP32-CAM (замените на свой!)
# Убедитесь, что путь заканчивается именно на /stream
stream_url = "http://192.168.1.100/stream"

print(f"Подключение к потоку: {stream_url}")

# Открываем видеопоток
cap = cv2.VideoCapture(stream_url)

if not cap.isOpened():
    print("Ошибка: Не удалось подключиться к потоку. Проверьте IP-адрес и Wi-Fi.")
    exit()

print("Успешно! Нажмите 'q' в окне видео для выхода.")

while True:
    # Читаем кадр из потока
    ret, frame = cap.read()

    if not ret or frame is None:
        print("Потеря соединения или пустой кадр. Переподключение...")
        cap.release()
        cap = cv2.VideoCapture(stream_url)
        continue

    # === ЗДЕСЬ МОЖНО ДОБАВИТЬ ОБРАБОТКУ ===
    # Например, перевести в черно-белый: frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Или добавить текст: cv2.putText(frame, "ESP32-CAM Live", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Показываем кадр в окне
    cv2.imshow("ESP32-CAM Local Stream", frame)

    # Выход из программы при нажатии клавиши 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Освобождаем ресурсы
cap.release()
cv2.destroyAllWindows()
