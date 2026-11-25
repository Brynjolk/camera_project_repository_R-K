import network, socket, time
from machine import Pin

WIFI_SSID = "Track"
WIFI_PASS = "TrackDet123"
BUZZER_PIN = 4
PORT = 8080

buzzer = Pin(BUZZER_PIN, Pin.OUT)
buzzer.value(0)

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    print("WiFi connecting...")
    for _ in range(20):
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            print("WiFi OK:", ip)
            return ip
        time.sleep(0.5)
    return None

def start_server(ip):
    addr = socket.getaddrinfo('0.0.0.0', PORT)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    print("Server:", ip, PORT)
    while True:
        cl = None
        try:
            cl, _ = s.accept()
            cl.settimeout(2.0)
            req = cl.recv(512).decode('utf-8')
            if '/alarm' in req:
                buzzer.value(1)
                print("ALARM ON")
                cl.send(b"HTTP/1.1 200 OK\r\n\r\nOK")
            elif '/stop' in req:
                buzzer.value(0)
                print("ALARM OFF")
                cl.send(b"HTTP/1.1 200 OK\r\n\r\nOK")
            else:
                cl.send(b"HTTP/1.1 200 OK\r\n\r\nReady")
        except Exception as e:
            print("Err:", e)
        finally:
            if cl: cl.close()

ip = connect_wifi()
if ip: start_server(ip)
